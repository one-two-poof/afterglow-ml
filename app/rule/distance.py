from typing import Any, Dict, Tuple

from app.utils.config_loader import get_rule_config
from app.utils.distance import calculate_haversine_distance


def calculate_distance_score(
    distance_km: float, mobility_range: int
) -> Tuple[float, bool]:
    """거리 룰 설정을 가져와 점수를 가산하는 함수."""
    rule_config = get_rule_config()
    tables = rule_config.get("preference_tables", {})

    pref_data = tables.get(mobility_range)
    max_allowable_dist = pref_data["max_allowable_dist"]
    thresholds = pref_data["thresholds"]

    if distance_km > max_allowable_dist:
        return 0.0, True

    score = 0.0
    is_excluded = True
    sorted_thresholds = sorted(thresholds, key=lambda x: x["max_dist"])

    for item in sorted_thresholds:
        if distance_km <= item["max_dist"]:
            score = item["score"]
            is_excluded = False
            break

    return score, is_excluded


def apply_distance_rule(
    start_lat: float,
    start_lng: float,
    mobility_range: int,
    candidates: Dict[int, Dict[str, Any]],
) -> Dict[int, Dict[str, Any]]:
    """후보 장소들에 대해 거리 계산 및 거리 점수 룰 적용 (필터링 포함)."""
    filtered_candidates = {}

    for place_id, info in candidates.items():
        place_lat = info["mapX"]
        place_lng = info["mapY"]

        distance_km = calculate_haversine_distance(
            start_lat, start_lng, place_lat, place_lng
        )
        score, is_excluded = calculate_distance_score(distance_km, mobility_range)

        if is_excluded:
            continue

        filtered_candidates[place_id] = info.copy()
        filtered_candidates[place_id]["score"] += score

    return filtered_candidates
