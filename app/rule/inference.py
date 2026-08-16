from typing import List, Dict, Any
import datetime
import pandas as pd
from sqlalchemy.orm import Session

from app.api.recommendation import (
    RecommendationRequest,
    RecommendationResponse,
    DailyRecommendation,
    RecommendedCourse,
    PlaceItem, 
    StartLocation
)
from app.rule.distance import apply_distance_rule
from app.rule.category import apply_category_rule
from app.utils.distance import calculate_haversine_distance

from app.repositories.place import PlaceRepository
from app.repositories.start_location import StartLocationRepository

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
            "score": 0.0  # 규칙을 거치며 누적될 초기 점수
        }
        
    daily_recommendations = []

    # 카테고리 룰 적용
    candidate_places = apply_category_rule(request.user_purpose, candidate_places)
    
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
        
        # 거리 룰 적용
        scored_candidates = apply_distance_rule(
            start_lat=start_lat,
            start_lng=start_lng,
            user_walk_preference=request.user_walk_preference,
            candidates=candidates_copy
        )
        
        # 규칙 적용된 장소 후보군을 통해 코스 생성
        recommended_courses = generate_courses(scored_candidates, current_date, start_lat, start_lng)

        # 날짜별 결과 누적
        daily_rec = DailyRecommendation(
            date=current_date,
            start_location=StartLocation(name=start_name, mapX=start_lat, mapY=start_lng),
            treatment=request.treatmentList,
            recommended_courses=recommended_courses
        )
        daily_recommendations.append(daily_rec)

    return RecommendationResponse(daily_recommendations=daily_recommendations)

def generate_courses(scored_candidates: dict, current_date: datetime.date, start_lat: float, start_lng: float) -> List[RecommendedCourse]:
    """
    점수가 반영된 후보 장소들을 바탕으로 코스를 생성하되,
    후보 장소가 턱없이 부족할 경우 빈 리스트를 반환하여 휴식을 유도하는 함수
    """
    sorted_places = sorted(
        scored_candidates.values(), 
        key=lambda x: x["score"], 
        reverse=True
    )

    recommended_courses = []
    
    for rank in range(1, 4): # 코스 생성 루프
        course_id = f"{current_date.strftime('%Y%m%d')}-course-{rank}"
        place_items = []
        total_distance = 0.0
        used_categories_in_course = set() # 같은 카테고리의 장소가 여러번 추천 되는 것 방지
        
        for idx in range(1, 4): # 코스 내 장소 선별 루프
            selected_place = None # 선택된 장소

            # set에 없는 새로운 카테고리의 장소를 우선 탐색
            for p in sorted_places:
                if p["place_category"] not in used_categories_in_course:
                    selected_place = p
                    break
            
            # 만약 새로운 카테고리가 없다면, 카테고리는 겹치지만 "아직 이 코스에 안 들어온 장소" 중 가장 점수 높은 것 선택
            if not selected_place and sorted_places:
                for p in sorted_places:
                    # 이번 코스에 이미 포함된 장소 이름과 겹치지 않는지 확인
                    if p["place_name"] not in [item.place_name for item in place_items]:
                        selected_place = p
                        break
            
            # 그것조차 없다면(정말 후보가 바닥났다면) 루프 탈출
            if not selected_place:
                break
                
            if selected_place:
                # 선택된 장소의 카테고리를 기록
                used_categories_in_course.add(selected_place["place_category"])

                if idx == 1:
                    prev_lat, prev_lng = start_lat, start_lng
                else:
                    prev_lat = place_items[-1].mapX  # 직전 장소의 위도
                    prev_lng = place_items[-1].mapY  # 직전 장소의 경도
                
                # 거리 계산 함수 호출 (km 단위 반환)
                dist_to_prev = calculate_haversine_distance(prev_lat, prev_lng, selected_place["mapX"], selected_place["mapY"])
                total_distance += dist_to_prev

                place_item = PlaceItem(
                    visit_order=len(place_items) + 1, # 실제 들어간 순서대로 번호 부여
                    place_name=selected_place["place_name"],
                    place_category=selected_place["place_category"],
                    mapX=selected_place["mapX"],
                    mapY=selected_place["mapY"],
                    is_indoor=selected_place["is_indoor"],
                    walk_hard=selected_place["walk_hard"],
                    dist_to_prev_km=round(dist_to_prev, 2)
                )
                place_items.append(place_item)
                
                # [핵심] 다음 코스나 다음 순번에서 중복 선택되는 것을 막기 위해 전체 후보군에서 제거
                sorted_places.remove(selected_place)

        # 만약 장소 부족으로 인해 이 코스에 장소가 1개도 안 담겼다면 코스 생성 중단
        if not place_items:
            break

        course = RecommendedCourse(
            rank=rank,
            course_id=course_id,
            total_distance_km=round(total_distance, 2),
            places=place_items
        )
        recommended_courses.append(course)

    for course in recommended_courses:
        # 만약 장소 부족으로 인해 이 코스에 장소가 2개 미만으로 담겼다면 이 코스는 폐기
        if len(place_items) < 2:
            continue  # 이번 rank 코스는 스킵하고 다음 코스로

    return recommended_courses