import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.schemas.recommendation import PlaceItem, DailySchedule, StartLocation
from app.utils.config_loader import get_rule_config
from app.utils.distance import calculate_haversine_distance

PlaceEntry = Tuple[int, Dict[str, Any]]
Coord = Tuple[float, float]


def _mmr_config() -> Dict[str, Any]:
    config = get_rule_config().get("mmr_rule", {})
    return {
        "lambda": float(config.get("lambda", 0.65)),
        "penalty_scale": float(config.get("penalty_scale", 12.0)),
        "category_weight": float(config.get("category_weight", 0.5)),
        "distance_weight": float(config.get("distance_weight", 0.5)),
        "same_detail_similarity": float(config.get("same_detail_similarity", 1.0)),
        "same_category_similarity": float(config.get("same_category_similarity", 0.6)),
        "near_km": float(config.get("near_km", 0.4)),
        "far_km": float(config.get("far_km", 1.5)),
    }


def _proximity_similarity(distance_km: float, near_km: float, far_km: float) -> float:
    if distance_km <= near_km:
        return 1.0
    if distance_km >= far_km:
        return 0.0
    return 1.0 - (distance_km - near_km) / (far_km - near_km)


def _category_similarity(
    place: Dict[str, Any],
    used_categories: set[str],
    used_details: set[str],
    same_detail_similarity: float,
    same_category_similarity: float,
) -> float:
    detail = place.get("category_detail") or ""
    category = place["place_category"]
    if detail and detail in used_details:
        return same_detail_similarity
    if category in used_categories:
        return same_category_similarity
    return 0.0


def _distance_similarity(
    place: Dict[str, Any],
    reference_points: Sequence[Coord],
    near_km: float,
    far_km: float,
) -> float:
    if not reference_points:
        return 0.0
    return max(
        _proximity_similarity(
            calculate_haversine_distance(lat, lng, place["mapX"], place["mapY"]),
            near_km,
            far_km,
        )
        for lat, lng in reference_points
    )


def _mmr_score(
    relevance: float,
    category_sim: float,
    distance_sim: float,
    config: Dict[str, Any],
) -> float:
    redundancy = (
        config["category_weight"] * category_sim
        + config["distance_weight"] * distance_sim
    )
    return (
        config["lambda"] * relevance
        - (1.0 - config["lambda"]) * config["penalty_scale"] * redundancy
    )


def _select_place_by_mmr(
    candidates: Iterable[PlaceEntry],
    trip_used_place_ids: set[int],
    selected_place_ids: set[int],
    used_place_categories: set[str],
    used_category_details: set[str],
    has_drugstore: bool,
    is_last_place: bool,
    reference_points: Sequence[Coord],
    config: Dict[str, Any],
) -> Optional[PlaceEntry]:
    best_entry: Optional[PlaceEntry] = None
    best_mmr = float("-inf")

    for place_id, place in candidates:
        if place_id in trip_used_place_ids or place_id in selected_place_ids:
            continue

        place_category = place["place_category"]
        is_drugstore = place_category == "드럭스토어"
        if is_drugstore and has_drugstore:
            continue
        if (
            is_last_place
            and len(used_place_categories) < 2
            and place_category in used_place_categories
        ):
            continue

        category_sim = _category_similarity(
            place,
            used_place_categories,
            used_category_details,
            config["same_detail_similarity"],
            config["same_category_similarity"],
        )
        distance_sim = _distance_similarity(
            place,
            reference_points,
            config["near_km"],
            config["far_km"],
        )
        mmr = _mmr_score(place["score"], category_sim, distance_sim, config)

        if mmr > best_mmr:
            best_mmr = mmr
            best_entry = (place_id, place)

    return best_entry


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
    mmr_config = _mmr_config()
    daily_schedules = []
    
    for rank in range(1, 4): # 코스 생성 루프 (1위, 2위, 3위 코스 대응)
        place_items = []
        selected_place_ids = set()
        used_category_details = set()
        used_place_categories = set()
        has_drugstore = False
        other_course_points = [
            (place.mapX, place.mapY)
            for schedule in daily_schedules
            for place in schedule.places
        ]
        other_course_categories = {
            place.place_category
            for schedule in daily_schedules
            for place in schedule.places
        }
        
        for idx in range(1, 4): # 코스 내 장소 선별 루프
            is_last_place = idx == 3
            selected_coords = [(item.mapX, item.mapY) for item in place_items]
            # 첫 장소는 출발지 근접이 본점수에 이미 있으므로, 같은 날 다른 코스와의 거리만 본다.
            reference_points = selected_coords + other_course_points

            selected = _select_place_by_mmr(
                candidates=sorted_places,
                trip_used_place_ids=trip_used_place_ids,
                selected_place_ids=selected_place_ids,
                used_place_categories=used_place_categories | other_course_categories,
                used_category_details=used_category_details,
                has_drugstore=has_drugstore,
                is_last_place=is_last_place,
                reference_points=reference_points,
                config=mmr_config,
            )

            if not selected:
                break

            selected_place_id, selected_place = selected
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
