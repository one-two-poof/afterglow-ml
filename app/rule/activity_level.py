from typing import Any, Dict

from app.utils.config_loader import get_rule_config


def apply_activity_level_rule(
    activity_level: int, candidates: Dict[int, Dict[str, Any]]
) -> Dict[int, Dict[str, Any]]:
    """activity_level과 장소 walk_hard 차이에 따라 점수를 가산한다."""
    rule_config = get_rule_config()
    activity_config = rule_config.get("activity_level_rule") or {}
    score_mapping = activity_config.get("score_mapping") or {}

    for _place_id, place_info in candidates.items():
        place_walk_hard = place_info.get("walk_hard")
        diff = abs(activity_level - place_walk_hard)
        score_increment = score_mapping.get(diff, score_mapping.get(str(diff)))
        place_info["score"] += score_increment

    return candidates
