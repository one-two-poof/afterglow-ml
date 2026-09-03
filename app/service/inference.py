import datetime
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.schemas.recommendation import (
    PlaceType,
    RecommendationRequest,
    RecommendationResponse,
    RecommendedCourse,
    TreatmentResponse,
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
    # Application-level orchestrator: repositories load records, rule modules
    # score/filter them, and course.py assembles the response. HTTP and commit
    # concerns intentionally remain in api/recommendation.py.
    place_repo = PlaceRepository(db)
    db_places = place_repo.get_all()

    if not db_places:
        raise ValueError("데이터베이스에 등록된 장소 후보 데이터가 없습니다.")

    # StartLocationRepository를 통해 출발지 데이터 전체 조회
    start_repo = StartLocationRepository(db)
    db_start_locations = start_repo.get_all()

    if not db_start_locations:
        raise ValueError("데이터베이스에 등록된 출발지 데이터가 없습니다.")

    # 조회한 출발지/관광지 리스트를 빠르게 검색하기 위해 딕셔너리로 매핑 (id 기준)
    start_places_dict = {int(loc.id): loc for loc in db_start_locations}
    places_dict = {int(place.id): place for place in db_places}

    # DB에서 가져온 후보 장소 데이터를 기존 로직이 요구하는 딕셔너리 구조로 매핑
    candidate_places: Dict[int, Dict[str, Any]] = {}
    
    for place in db_places:
        place_id = int(place.id)
        
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

    # rank별로 날짜별 일정을 모으기 위한 구조
    rank_aggregated_data: Dict[int, Dict[str, Any]] = {}
    used_by_rank: Dict[int, set[int]] = {1: set(), 2: set(), 3: set()}

    # 시작일부터 종료일까지 하루씩 순회
    delta = request.trip_end_date - request.trip_start_date
    for i in range(delta.days + 1):
        current_date = request.trip_start_date + datetime.timedelta(days=i)
        
        # 해당 날짜의 출발점 정보 찾기
        start_info = next(
            (item for item in request.daily_startList if item.date == current_date),
            None,
        )
        if start_info is None:
            raise ValueError(f"{current_date} 날짜의 출발점 정보가 없습니다.")

        place_type = start_info.place_type
        if place_type == PlaceType.ATTRACTION:
            start_loc_obj = places_dict.get(start_info.start_id)
            if not start_loc_obj:
                raise ValueError(
                    f"ID가 {start_info.start_id}인 ATTRACTION 출발지 정보를 "
                    "데이터베이스에서 찾을 수 없습니다."
                )
        else:
            start_loc_obj = start_places_dict.get(start_info.start_id)
            if not start_loc_obj:
                raise ValueError(
                    f"ID가 {start_info.start_id}인 {place_type.value} 출발지 정보를 "
                    "데이터베이스에서 찾을 수 없습니다."
                )

        # DB의 출발지 데이터에 mapX, mapY 가져오기(결측치가 있다면 임시로 0.0으로 설정)
        start_name = start_loc_obj.place_name
        start_lat = float(start_loc_obj.map_y) if start_loc_obj.map_y else 0.0
        start_lng = float(start_loc_obj.map_x) if start_loc_obj.map_x else 0.0
        
        # 매일 리셋되는 후보군 복사본 생성
        candidates_copy = {k: v.copy() for k, v in candidate_places.items()}
        if place_type == PlaceType.ATTRACTION:
            candidates_copy.pop(start_info.start_id, None)
        
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
        daily_schedules = generate_courses(
            scored_candidates=scored_candidates,
            current_date=current_date,
            start_lat=start_lat,
            start_lng=start_lng,
            start_name=start_name,
            used_by_rank=used_by_rank,
            user_walk_preference=request.user_walk_preference,
            user_purpose=request.user_purpose,
        )

        if len(daily_schedules) != 3:
            raise ValueError(
                "중복되지 않는 장소가 부족하여 추천 코스 3개를 만들 수 없습니다."
            )

        # 순위별(인덱스 기준 0->1위, 1->2위...)로 스케줄 및 거리 누적
        for rank_idx, schedule in enumerate(daily_schedules):
            current_rank = rank_idx + 1 # 1위, 2위, 3위
            
            if current_rank not in rank_aggregated_data:
                rank_aggregated_data[current_rank] = {
                    "total_distance": 0.0,
                    "daily_schedules": []
                }
            
            # 해당 일정의 총 거리 계산 (place들의 dist_to_prev_km 합산)
            day_distance = sum(p.dist_to_prev_km for p in schedule.places)
            rank_aggregated_data[current_rank]["total_distance"] += day_distance
            rank_aggregated_data[current_rank]["daily_schedules"].append(schedule)

    # 최종 추천 응답 생성 (RecommendedCourse 스키마 준수)
    daily_recommendations = []
    for rank, data in rank_aggregated_data.items():
        recommended_course = RecommendedCourse(
            recommended_course_id=0,
            rank=rank,
            course_id="",
            treatment=[
                TreatmentResponse.model_validate(item.model_dump())
                for item in request.treatmentList
            ],
            total_distance_km=round(data["total_distance"], 2),
            daily_schedules=data["daily_schedules"]
        )
        daily_recommendations.append(recommended_course)

    return RecommendationResponse(daily_recommendations=daily_recommendations)
