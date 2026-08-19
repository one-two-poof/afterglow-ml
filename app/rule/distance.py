from typing import Dict, Any, Tuple

from app.utils.distance import calculate_haversine_distance
from app.utils.config_loader import get_rule_config

def calculate_distance_score(distance_km: float, user_walk_preference: int) -> Tuple[float, bool]:
    """
    거리 룰 설정을 가져와 점수를 가산하는 함수
    """
    # 규칙 설정 가져오기
    rule_config = get_rule_config()
    tables = rule_config.get("preference_tables", {})

    # user_walk_preference에 맞는 규칙 설정 테이블 가져오기
    pref_data = tables.get(user_walk_preference)

    # user_walk_preference에 맞는 최대 거리 및 임계점 변수 설정
    max_allowable_dist = pref_data["max_allowable_dist"]
    thresholds = pref_data["thresholds"]

    # 최대 거리를 초과하는 장소는 바로 ((0,0), True) 반환
    # True로 반환 시 apply_distance_rule에서 해당 장소를 바로 후보군에서 제외
    if distance_km > max_allowable_dist:
        return 0.0, True
        
    score = 0.0
    is_excluded = True

    # 규칙 설정에 제대로 설정 했지만 혹시 몰라서 max_dist 순으로 오름차순
    sorted_thresholds = sorted(thresholds, key=lambda x: x["max_dist"])

    # 현재 장소와 출발지의 거리가 임계점 보다 낮은 값을 가지면 해당 점수를 얻고 반환
    for item in sorted_thresholds:
        if distance_km <= item["max_dist"]:
            score = item["score"]
            is_excluded = False
            break
            
    return score, is_excluded


def apply_distance_rule(
    start_lat: float, 
    start_lng: float, 
    user_walk_preference: int, 
    candidates: Dict[int, Dict[str, Any]]
) -> Dict[int, Dict[str, Any]]:
    """
    후보 장소들에 대해 거리 계산 및 거리 점수 룰 적용 (필터링 포함)
    """
    # 반환할 장소 후보 dict
    filtered_candidates = {}
    
    for place_id, info in candidates.items():
        place_lat = info["mapX"]
        place_lng = info["mapY"]

        # 거리 및 점수 계산
        distance_km = calculate_haversine_distance(start_lat, start_lng, place_lat, place_lng)
        score, is_excluded = calculate_distance_score(distance_km, user_walk_preference)

        # user_walk_preference에 비해 너무 먼 거리는 후보군에서 제외
        if is_excluded:
            continue

        # 점수 적용
        filtered_candidates[place_id] = info.copy()
        filtered_candidates[place_id]["score"] += score

    return filtered_candidates