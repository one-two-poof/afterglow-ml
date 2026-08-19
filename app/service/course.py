import datetime
from typing import List

from app.api.recommendation import PlaceItem, DailySchedule, StartLocation  # 필요한 모델 임포트
from app.utils.distance import calculate_haversine_distance

def generate_courses(scored_candidates: dict, current_date: datetime.date, start_lat: float, start_lng: float) -> list:
    """
    점수가 반영된 후보 장소들을 바탕으로 특정 날짜의 코스 후보군을 생성하는 함수
    """
    sorted_places = sorted(
        scored_candidates.values(), 
        key=lambda x: x["score"], 
        reverse=True
    )

    daily_generated_courses = []
    
    for rank in range(1, 4): # 코스 생성 루프
        course_id = f"course-{rank}"  # 날짜를 제외한 공통 코스 ID로 관리하거나 그대로 유지
        place_items = []
        total_distance = 0.0
        used_categories_in_course = set()
        
        for idx in range(1, 4): # 코스 내 장소 선별 루프
            selected_place = None

            for p in sorted_places:
                if p["place_category"] not in used_categories_in_course:
                    selected_place = p
                    break
            
            if not selected_place and sorted_places:
                for p in sorted_places:
                    if p["place_name"] not in [item.place_name for item in place_items]:
                        selected_place = p
                        break
            
            if not selected_place:
                break
                
            if selected_place:
                used_categories_in_course.add(selected_place["place_category"])

                if idx == 1:
                    prev_lat, prev_lng = start_lat, start_lng
                else:
                    prev_lat = place_items[-1].mapX
                    prev_lng = place_items[-1].mapY
                
                dist_to_prev = calculate_haversine_distance(prev_lat, prev_lng, selected_place["mapX"], selected_place["mapY"])
                total_distance += dist_to_prev

                place_item = PlaceItem(
                    visit_order=len(place_items) + 1,
                    place_name=selected_place["place_name"],
                    place_category=selected_place["place_category"],
                    mapX=selected_place["mapX"],
                    mapY=selected_place["mapY"],
                    is_indoor=selected_place["is_indoor"],
                    walk_hard=selected_place["walk_hard"],
                    dist_to_prev_km=round(dist_to_prev, 2)
                )
                place_items.append(place_item)
                
                sorted_places.remove(selected_place)

        # 장소가 2개 미만이면 이 코스는 스킵
        if len(place_items) < 2:
            continue

        # 임시로 해당 날짜의 코스 정보를 딕셔너리 형태로 반환 (apply_rule에서 병합하기 쉽게)
        daily_generated_courses.append({
            "rank": rank,
            "course_id": f"C{str(rank).zfill(5)}",  # 예: C00001, C00002 등
            "total_distance_km": round(total_distance, 2),
            "places": place_items
        })

    return daily_generated_courses