from typing import Dict, Any

from app.utils.config_loader import get_rule_config

def apply_walk_preference_rule(user_walk_preference: int, candidates: Dict[int, Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    """
    도보 선호도 룰 설정을 가져와 점수를 가산하는 함수
    """
    # 규칙 설정 가져오기
    rule_config = get_rule_config()
    walk_preference_config = rule_config.get("intensity_rule")
    score_mapping = walk_preference_config.get("score_mapping")

    for place_id, place_info in candidates.items():
        place_walk_hard = place_info.get("walk_hard")
        
        # 선호도와 장소 강도의 절대 차이 계산
        diff = abs(user_walk_preference - place_walk_hard)
        
        # 설정된 차이값에 해당하는 점수를 가져옴
        score_increment = score_mapping.get(diff, score_mapping.get(str(diff)))
        
        place_info["score"] += score_increment

    return candidates