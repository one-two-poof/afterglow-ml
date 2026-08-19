import datetime
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.schemas.recommendation import (
    DailySchedule,
    RecommendationRequest,
    RecommendationResponse,
    RecommendedCourse,
    StartLocation,
)
from app.repositories.place import PlaceRepository
from app.repositories.start_location import StartLocationRepository
from app.rule.category import apply_category_rule
from app.rule.distance import apply_distance_rule
from app.rule.treatment import apply_treatment_rule
from app.rule.walk_preference import apply_walk_preference_rule
from app.service.course import generate_courses

def apply_rule(request: RecommendationRequest, db: Session) -> RecommendationResponse:
    """
    사용자 request와 외부에서 주입받은 DB 세션을 받아 
    후보 장소와 출발지 정보를 모두 DB에서 조회하여 Rule을 적용시키는 함수
    """
    # PlaceRepository를 통해 후보 장소 데이터 전체 조회
    place_repo = PlaceRepository(db)
    db_places = place_repo.get_all()

    if not db_places:
        raise ValueError("데이터베이스에 등록된 장소 후보 데이터가 없습니다.")

    # StartLocationRepository를 통해 출발지 데이터 전체 조회
    start_repo = StartLocationRepository(db)
    db_start_locations = start_repo.get_all()

    if not db_start_locations:
        raise ValueError("데이터베이스에 등록된 출발지 데이터가 없습니다.")

    # 조회한 출발지 리스트를 빠르게 검색하기 위해 딕셔너리로 매핑 (kakao_place_id 기준)
    start_places_dict = {int(loc.kakao_place_id): loc for loc in db_start_locations}

    # DB에서 가져온 후보 장소 데이터를 기존 로직이 요구하는 딕셔너리 구조로 매핑
    candidate_places: Dict[int, Dict[str, Any]] = {}
    
    for place in db_places:
        place_id = int(place.kakao_place_id)
        
        candidate_places[place_id] = {
            "place_name": place.place_name,
            "place_category": place.primary_type_name or "기타",
            "category_detail": place.category_name or "",
            "mapX": float(place.map_y) if place.map_y else 0.0,  # 하버사인 계산용 위도(lat) 매핑
            "mapY": float(place.map_x) if place.map_x else 0.0,  # 하버사인 계산용 경도(lng) 매핑
            "is_indoor": int(place.is_indoor) if place.is_indoor is not None else 0,
            "walk_hard": int(place.walk_hard) if place.walk_hard is not None else 1,
            "is_heat_source": int(place.is_heat_source) if place.is_heat_source is not None else 0,
            "is_massage_spot": int(place.is_massage_spot) if place.is_massage_spot is not None else 0,
            "score": 0.0  # 규칙을 거치며 누적될 초기 점수
        }

    daily_recommendations = []

    # == 카테고리 룰 적용 ==
    candidate_places = apply_category_rule(request.user_purpose, candidate_places)

    # == 도보 선호도 룰 적용 ==
    candidate_places =  apply_walk_preference_rule(request.user_walk_preference, candidate_places)

    aggregated_courses: Dict[str, Dict[str, Any]] = {}

    # 시작일부터 종료일까지 하루씩 순회
    delta = request.trip_end_date - request.trip_start_date
    for i in range(delta.days + 1):
        current_date = request.trip_start_date + datetime.timedelta(days=i)
        
        # 해당 날짜의 출발점 정보 찾기
        start_info = next(item for item in request.daily_startList if item.date == current_date)

        # DB를 통해 만든 dict에서 id를 통해 장소 정보 얻기
        start_loc_obj = start_places_dict.get(start_info.start_id)
        if not start_loc_obj:
            raise ValueError(f"ID가 {start_info.start_id}인 출발지 정보를 데이터베이스에서 찾을 수 없습니다.")

        # DB의 출발지 데이터에 mapX, mapY 가져오기(결측치가 있다면 임시로 0.0으로 설정)
        start_name = start_loc_obj.place_name
        start_lat = float(start_loc_obj.map_y) if start_loc_obj.map_y else 0.0
        start_lng = float(start_loc_obj.map_x) if start_loc_obj.map_x else 0.0
        
        # 매일 리셋되는 후보군 복사본 생성
        candidates_copy = {k: v.copy() for k, v in candidate_places.items()}
        
        # == 거리 룰 적용 ==
        scored_candidates = apply_distance_rule(
            start_lat=start_lat,
            start_lng=start_lng,
            user_walk_preference=request.user_walk_preference,
            candidates=candidates_copy
        )

        # == 시술 룰 적용 ==
        scored_candidates = apply_treatment_rule(
            request.treatmentList, 
            current_date, 
            scored_candidates
        )
        
        # 규칙 적용된 장소 후보군을 통해 코스 생성
        daily_generated_courses = generate_courses(scored_candidates, current_date, start_lat, start_lng)

        # 생성된 코스들을 순회하며 최상단 구조(코스 기준)에 맞게 병합
        for course in daily_generated_courses:
            course_id = course.course_id
            
            # 만약 아직 등록되지 않은 코스 ID라면 기본 틀 생성
            if course_id not in aggregated_courses:
                aggregated_courses[course_id] = {
                    "rank": course.rank,
                    "course_id": course_id,
                    "total_distance_km": 0.0,
                    "daily_schedules": []
                }
            
            # 총 거리 누적
            aggregated_courses[course_id]["total_distance_km"] += course.total_distance_km

            # 해당 날짜의 일정 객체 생성
            daily_schedule = DailySchedule(
                date=current_date,
                start_location=StartLocation(name=start_name, mapX=start_lat, mapY=start_lng),
                treatment=request.treatmentList,  # 필요시 해당 날짜에 맞는 시술만 필터링해서 넣을 수도 있습니다
                places=course.places
            )
            
            # 해당 코스의 일자에 추가
            aggregated_courses[course_id]["daily_schedules"].append(daily_schedule)

    # 최종 Pydantic 모델 리스트로 변환
    recommended_courses = [
        RecommendedCourse(
            rank=data["rank"],
            course_id=data["course_id"],
            total_distance_km=round(data["total_distance_km"], 2),
            daily_schedules=data["daily_schedules"]
        )
        for data in aggregated_courses.values()
    ]

    return RecommendationResponse(recommended_courses=recommended_courses)