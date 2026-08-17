import datetime
from typing import List

from app.api.recommendation import PlaceItem, RecommendedCourse
from app.utils.distance import calculate_haversine_distance

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