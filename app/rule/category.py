from typing import Any, Dict, Optional, Sequence

from app.utils.config_loader import get_rule_config


def _place_text(place: Dict[str, Any]) -> str:
    primary = place.get("place_category") or ""
    detail = place.get("category_detail") or ""
    return f"{primary} {detail}"


def _theme_place_excludes() -> Sequence[str]:
    category_config = get_rule_config().get("category_rule") or {}
    return list(category_config.get("theme_place_excludes") or [])


def is_theme_place(place: Dict[str, Any]) -> bool:
    text = _place_text(place)
    return any(keyword in text for keyword in _theme_place_excludes())


def place_matches_keywords(
    place: Dict[str, Any],
    keywords: Sequence[str],
    exclude_keywords: Optional[Sequence[str]] = None,
) -> bool:
    if not keywords:
        return False
    text = _place_text(place)
    excludes = list(exclude_keywords) if exclude_keywords is not None else list(_theme_place_excludes())
    if excludes and any(keyword in text for keyword in excludes):
        return False
    return any(keyword in text for keyword in keywords)


def apply_category_rule(user_purpose: str, candidates: Dict[int, Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    """
    방문 목적에 맞는 소분류 키워드가 있으면 점수를 가산하는 함수.
    대분류(place_category 단독 매핑)는 쓰지 않고, 소분류 키워드가
    place_category 또는 category_detail에 포함되는지만 본다.
    """
    category_config = get_rule_config().get("category_rule") or {}
    weights = category_config.get("weights") or {}
    keyword_weight = float(weights.get("keyword_match", 0.0))
    purpose_keywords = category_config.get("purpose_keywords") or {}
    preferred_keywords = list(purpose_keywords.get(user_purpose) or [])

    for _place_id, place_info in candidates.items():
        if place_matches_keywords(place_info, preferred_keywords):
            place_info["score"] += keyword_weight

    return candidates
