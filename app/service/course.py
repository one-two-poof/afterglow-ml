import datetime
from typing import List

from app.schemas.recommendation import PlaceItem, DailySchedule, StartLocation
from app.utils.distance import calculate_haversine_distance

def generate_courses(
    scored_candidates: dict, 
    current_date: datetime.date, 
    start_lat: float, 
    start_lng: float,
    start_name: str,
    trip_used_place_ids: set[int],
) -> List[DailySchedule]:
    """
    점수가 반영된 후보 장소들을 바탕으로 특정 날짜의 DailySchedule 리스트를 생성하는 함수
    """
    sorted_places = sorted(
        scored_candidates.items(),
        key=lambda item: item[1]["score"],
        reverse=True
    )

    daily_schedules = []
    
    for rank in range(1, 4): # 코스 생성 루프 (1위, 2위, 3위 코스 대응)
        place_items = []
        selected_place_ids = set()
        used_category_details = set()
        used_place_categories = set()
        has_drugstore = False
        
        for idx in range(1, 4): # 코스 내 장소 선별 루프
            is_last_place = idx == 3
            selected_place = None
            selected_place_id = None

            for place_id, place in sorted_places:
                if place_id in trip_used_place_ids:
                    continue

                place_category = place["place_category"]
                category_detail = place.get("category_detail") or ""
                is_drugstore = place_category == "드럭스토어"

                if place_id in selected_place_ids:
                    continue
                if is_drugstore and has_drugstore:
                    continue
                if category_detail and category_detail in used_category_details:
                    continue
                if (
                    is_last_place
                    and len(used_place_categories) < 2
                    and place_category in used_place_categories
                ):
                    continue

                selected_place_id = place_id
                selected_place = place
                break

            if not selected_place:
                break
                
            selected_category = selected_place["place_category"]
            selected_detail = selected_place.get("category_detail") or ""
            selected_place_ids.add(selected_place_id)
            used_place_categories.add(selected_category)
            if selected_detail:
                used_category_details.add(selected_detail)
            if selected_category == "드럭스토어":
                has_drugstore = True

            if idx == 1:
                prev_lat, prev_lng = start_lat, start_lng
            else:
                prev_lat = place_items[-1].mapX
                prev_lng = place_items[-1].mapY

            dist_to_prev = calculate_haversine_distance(prev_lat, prev_lng, selected_place["mapX"], selected_place["mapY"])

            place_item = PlaceItem(
                visit_order=len(place_items) + 1,
                place_name=selected_place["place_name"],
                place_category=selected_category,
                mapX=selected_place["mapX"],
                mapY=selected_place["mapY"],
                is_indoor=selected_place["is_indoor"],
                walk_hard=selected_place["walk_hard"],
                dist_to_prev_km=round(dist_to_prev, 2)
            )
            place_items.append(place_item)

        # 장소가 2개 이하이면 이 코스는 스킵
        if len(place_items) <= 2 or len(used_place_categories) < 2:
            continue

        trip_used_place_ids.update(selected_place_ids)

        schedule = DailySchedule(
            date=current_date,
            start_location=StartLocation(name=start_name, mapX=start_lat, mapY=start_lng),
            places=place_items
        )
        
        daily_schedules.append(schedule)

    return daily_schedules
