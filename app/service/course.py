import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.rule.category import is_theme_place, place_matches_keywords
from app.rule.distance import calculate_distance_score
from app.schemas.recommendation import PlaceItem, DailySchedule, StartLocation
from app.utils.config_loader import get_rule_config
from app.utils.distance import calculate_haversine_distance

PlaceEntry = Tuple[int, Dict[str, Any]]
Coord = Tuple[float, float]


def _mmr_config() -> Dict[str, Any]:
    config = get_rule_config().get("mmr_rule", {})
    inter_course_weight = config.get("inter_course_weight", config.get("distance_weight", 0.4))
    return {
        "lambda": float(config.get("lambda", 0.65)),
        "penalty_scale": float(config.get("penalty_scale", 1.2)),
        "category_weight": float(config.get("category_weight", 0.7)),
        "compactness_weight": float(config.get("compactness_weight", 1.2)),
        "inter_course_weight": float(inter_course_weight),
        "same_detail_similarity": float(config.get("same_detail_similarity", 1.0)),
        "same_category_similarity": float(config.get("same_category_similarity", 0.55)),
        "near_km": float(config.get("near_km", 0.3)),
        "far_km": float(config.get("far_km", 1.0)),
        "inter_course_near_km": float(config.get("inter_course_near_km", 0.15)),
        "inter_course_far_km": float(config.get("inter_course_far_km", 0.6)),
    }


def _slot_entry(slots: Dict[str, Any], slot_index: int) -> Dict[str, Any]:
    return slots.get(slot_index) or slots.get(str(slot_index)) or {}


def _parse_slots(slots: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    parsed_slots: Dict[int, Dict[str, Any]] = {}
    for slot_index in (1, 2, 3):
        slot = _slot_entry(slots, slot_index)
        parsed_slots[slot_index] = {
            "keywords": list(slot.get("keywords", [])),
            "bonus": float(slot.get("bonus", 0.0)),
        }
    return parsed_slots


def _purpose_key(user_purpose: Optional[str], default: str) -> str:
    if user_purpose is None:
        return default
    value = getattr(user_purpose, "value", user_purpose)
    return str(value) if value else default


def _flow_config(user_purpose: Optional[str] = None) -> Dict[str, Any]:
    config = get_rule_config().get("course_flow_rule", {})
    purposes = config.get("purposes") or {}
    default_purpose = str(config.get("default_purpose") or "문화관광")
    purpose_key = _purpose_key(user_purpose, default_purpose)
    purpose_cfg = purposes.get(purpose_key) or purposes.get(default_purpose) or {}
    slots = purpose_cfg.get("slots") or config.get("slots") or {}
    parsed_slots = _parse_slots(slots)
    purpose_keywords: List[str] = []
    seen_keywords: set[str] = set()
    for slot in parsed_slots.values():
        for keyword in slot.get("keywords", []):
            if keyword not in seen_keywords:
                seen_keywords.add(keyword)
                purpose_keywords.append(keyword)
    by_walk = config.get("slot_max_hop_by_walk") or {}
    return {
        "slots": parsed_slots,
        "purpose_keywords": purpose_keywords,
        "shopping_keywords": list(purpose_cfg.get("shopping_keywords", config.get("shopping_keywords", []))),
        "skip_categories": set(purpose_cfg.get("skip_categories", [])),
        "early_shopping_penalty": float(
            purpose_cfg.get("early_shopping_penalty", config.get("early_shopping_penalty", 0.0))
        ),
        "reorder_distance_weight": float(config.get("reorder_distance_weight", 1.0)),
        "slot_max_hop_by_walk": {
            int(walk): float(max_hop) for walk, max_hop in by_walk.items()
        },
        "purpose_key": purpose_key,
    }


def _slot_max_hop_km(user_walk_preference: int, flow: Dict[str, Any]) -> float:
    by_walk = flow.get("slot_max_hop_by_walk") or {}
    return float(by_walk.get(user_walk_preference, 2.5))


def _hop_km(
    place: Dict[str, Any],
    prev_points: Sequence[Coord],
    origin: Optional[Coord],
) -> float:
    if prev_points:
        prev_lat, prev_lng = prev_points[-1]
        return calculate_haversine_distance(prev_lat, prev_lng, place["mapX"], place["mapY"])
    if origin is not None:
        return calculate_haversine_distance(origin[0], origin[1], place["mapX"], place["mapY"])
    return 0.0


def _best_mmr_entry(
    eligible: Sequence[Tuple[PlaceEntry, float, float, float, float]],
    config: Dict[str, Any],
) -> Optional[PlaceEntry]:
    if not eligible:
        return None
    normalized = _normalize_scores([item[1] for item in eligible])
    best_entry: Optional[PlaceEntry] = None
    best_mmr = float("-inf")
    for (entry, _raw_score, category_sim, compactness, inter_course_sim), relevance in zip(
        eligible, normalized
    ):
        mmr = _mmr_score(
            relevance,
            category_sim,
            compactness,
            inter_course_sim,
            config,
        )
        if mmr > best_mmr:
            best_mmr = mmr
            best_entry = entry
    return best_entry


def _diversify_by_category(
    eligible: Sequence[Tuple[PlaceEntry, float, float, float, float]],
    avoid_categories: set[str],
) -> List[Tuple[PlaceEntry, float, float, float, float]]:
    if not avoid_categories:
        return list(eligible)
    diverse = [
        item for item in eligible if item[0][1]["place_category"] not in avoid_categories
    ]
    return diverse or list(eligible)


def _slot_score(place: Dict[str, Any], slot_index: int, flow: Dict[str, Any]) -> float:
    slot = flow.get("slots", {}).get(slot_index, {})
    score = 0.0
    if place_matches_keywords(place, slot.get("keywords", [])):
        score += float(slot.get("bonus", 0.0))
    if slot_index == 1 and place_matches_keywords(place, flow.get("shopping_keywords", [])):
        score += float(flow.get("early_shopping_penalty", 0.0))
    return score


def _proximity_similarity(distance_km: float, near_km: float, far_km: float) -> float:
    if distance_km <= near_km:
        return 1.0
    if distance_km >= far_km:
        return 0.0
    span = far_km - near_km
    if span <= 0:
        return 0.0
    return 1.0 - (distance_km - near_km) / span


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


def _normalize_scores(scores: Sequence[float]) -> List[float]:
    if not scores:
        return []
    min_score = min(scores)
    max_score = max(scores)
    if max_score - min_score < 1e-9:
        return [1.0] * len(scores)
    return [(score - min_score) / (max_score - min_score) for score in scores]


def _mmr_score(
    relevance: float,
    category_sim: float,
    compactness: float,
    inter_course_sim: float,
    config: Dict[str, Any],
) -> float:
    diversity_penalty = (
        config["category_weight"] * category_sim
        + config["inter_course_weight"] * inter_course_sim
    )
    return (
        config["lambda"] * relevance
        + config["compactness_weight"] * compactness
        - (1.0 - config["lambda"]) * config["penalty_scale"] * diversity_penalty
    )


def _select_place_by_mmr(
    candidates: Iterable[PlaceEntry],
    excluded_place_ids: set[int],
    selected_place_ids: set[int],
    used_place_categories: set[str],
    used_category_details: set[str],
    has_drugstore: bool,
    is_last_place: bool,
    prev_points: Sequence[Coord],
    other_course_points: Sequence[Coord],
    user_walk_preference: int,
    config: Dict[str, Any],
    slot_index: int = 1,
    flow: Optional[Dict[str, Any]] = None,
    allow_repeat_category: bool = False,
    origin: Optional[Coord] = None,
    avoid_categories: Optional[set[str]] = None,
) -> Optional[PlaceEntry]:
    flow = flow if flow is not None else _flow_config()
    eligible: List[Tuple[PlaceEntry, float, float, float, float]] = []
    avoid = avoid_categories or set()
    max_hop = _slot_max_hop_km(user_walk_preference, flow)
    slot_keywords = list(flow.get("slots", {}).get(slot_index, {}).get("keywords", []))
    purpose_keywords = list(flow.get("purpose_keywords", []))

    for place_id, place in candidates:
        if place_id in excluded_place_ids or place_id in selected_place_ids:
            continue
        if is_theme_place(place):
            continue

        place_category = place["place_category"]
        if place_category in flow.get("skip_categories", set()):
            continue
        is_drugstore = place_category == "드럭스토어"
        if is_drugstore and has_drugstore:
            continue

        sequential_score = 0.0
        if prev_points:
            prev_lat, prev_lng = prev_points[-1]
            dist_to_prev = calculate_haversine_distance(
                prev_lat, prev_lng, place["mapX"], place["mapY"]
            )
            sequential_score, is_excluded = calculate_distance_score(
                dist_to_prev, user_walk_preference
            )
            if is_excluded:
                continue

        category_sim = _category_similarity(
            place,
            used_place_categories,
            used_category_details,
            config["same_detail_similarity"],
            config["same_category_similarity"],
        )
        compactness = _distance_similarity(
            place,
            prev_points,
            config["near_km"],
            config["far_km"],
        )
        inter_course_sim = _distance_similarity(
            place,
            other_course_points,
            config["inter_course_near_km"],
            config["inter_course_far_km"],
        )
        eligible.append(
            (
                (place_id, place),
                place["score"] + sequential_score + _slot_score(place, slot_index, flow),
                category_sim,
                compactness,
                inter_course_sim,
            )
        )

    if not eligible:
        return None

    unique = [
        item
        for item in eligible
        if item[0][1]["place_category"] not in used_place_categories
    ]
    near_unique = [
        item for item in unique if _hop_km(item[0][1], prev_points, origin) <= max_hop
    ]
    near_all = [
        item for item in eligible if _hop_km(item[0][1], prev_points, origin) <= max_hop
    ]

    def _matching(
        pool: Sequence[Tuple[PlaceEntry, float, float, float, float]],
        keywords: Sequence[str],
    ) -> List[Tuple[PlaceEntry, float, float, float, float]]:
        if not keywords:
            return []
        return [item for item in pool if place_matches_keywords(item[0][1], keywords)]

    if allow_repeat_category:
        pools = [
            _matching(near_all, slot_keywords),
            _matching(near_all, purpose_keywords),
            eligible,
        ]
    else:
        slot_near_unique = _matching(near_unique, slot_keywords)
        purpose_near_unique = _matching(near_unique, purpose_keywords)
        slot_near_repeat = _matching(near_all, slot_keywords or purpose_keywords)
        need_new_category = len(used_place_categories) < 2
        is_rest = flow.get("purpose_key") == "휴식"
        if need_new_category:
            pools = [
                slot_near_unique,
                purpose_near_unique,
                near_unique,
                slot_near_repeat,
                unique,
                eligible,
            ]
        elif is_rest:
            pools = [
                slot_near_unique,
                purpose_near_unique,
                slot_near_repeat,
                near_unique,
                unique,
                eligible,
            ]
        else:
            pools = [
                slot_near_unique,
                purpose_near_unique,
                near_unique,
                slot_near_repeat,
                unique,
                eligible,
            ]

    for pool in pools:
        chosen = _best_mmr_entry(_diversify_by_category(pool, avoid), config)
        if chosen:
            return chosen
    return None


def _build_ordered_place_items(
    selected_entries: Sequence[PlaceEntry],
    start_lat: float,
    start_lng: float,
    flow: Optional[Dict[str, Any]] = None,
) -> List[PlaceItem]:
    remaining = list(selected_entries)
    items: List[PlaceItem] = []
    prev_lat, prev_lng = start_lat, start_lng
    prev_category: Optional[str] = None
    flow = flow if flow is not None else _flow_config()
    distance_weight = float(flow.get("reorder_distance_weight", 1.0))

    while remaining:
        slot_index = len(items) + 1
        candidate_indices = list(range(len(remaining)))
        # Avoid the same place_category twice in a row when another category remains.
        if prev_category is not None:
            different_indices = [
                index
                for index in candidate_indices
                if remaining[index][1]["place_category"] != prev_category
            ]
            if different_indices:
                candidate_indices = different_indices

        def _order_key(index: int) -> float:
            place = remaining[index][1]
            distance_km = calculate_haversine_distance(
                prev_lat,
                prev_lng,
                place["mapX"],
                place["mapY"],
            )
            return distance_weight * distance_km - _slot_score(place, slot_index, flow)

        next_idx = min(candidate_indices, key=_order_key)
        _, place = remaining.pop(next_idx)
        dist_to_prev = calculate_haversine_distance(
            prev_lat, prev_lng, place["mapX"], place["mapY"]
        )
        items.append(
            PlaceItem(
                visit_order=len(items) + 1,
                place_name=place["place_name"],
                place_category=place["place_category"],
                mapX=place["mapX"],
                mapY=place["mapY"],
                is_indoor=place["is_indoor"],
                walk_hard=place["walk_hard"],
                dist_to_prev_km=round(dist_to_prev, 2),
            )
        )
        prev_lat, prev_lng = place["mapX"], place["mapY"]
        prev_category = place["place_category"]

    return items


def generate_courses(
    scored_candidates: dict,
    current_date: datetime.date,
    start_lat: float,
    start_lng: float,
    start_name: str,
    used_by_rank: Dict[int, set[int]],
    user_walk_preference: int,
    user_purpose: Optional[str] = None,
) -> List[DailySchedule]:
    """
    점수가 반영된 후보 장소들을 바탕으로 특정 날짜의 DailySchedule 리스트를 생성하는 함수
    """
    # Selection is deliberately greedy by rule score. Distance is calculated for
    # the response after selection; it does not optimize the visiting order.
    sorted_places = sorted(
        scored_candidates.items(),
        key=lambda item: item[1]["score"],
        reverse=True
    )
    mmr_config = _mmr_config()
    flow_config = _flow_config(user_purpose)
    daily_schedules = []
    used_today: set[int] = set()
    selected_slot_categories: List[List[str]] = []

    for rank in range(1, 4):
        selected_entries: List[PlaceEntry] = []
        selected_place_ids: set[int] = set()
        used_category_details: set[str] = set()
        used_place_categories: set[str] = set()
        has_drugstore = False
        previously_used = set().union(*used_by_rank.values()) if used_by_rank else set()
        excluded_place_ids = previously_used | used_today
        other_course_points = [
            (place.mapX, place.mapY)
            for schedule in daily_schedules
            for place in schedule.places
        ]
        origin = (start_lat, start_lng)

        for idx in range(1, 4):
            is_last_place = idx == 3
            prev_points = [
                (place["mapX"], place["mapY"]) for _, place in selected_entries
            ]
            avoid_categories = {
                cats[idx - 1]
                for cats in selected_slot_categories
                if len(cats) >= idx
            }

            selected = _select_place_by_mmr(
                candidates=sorted_places,
                excluded_place_ids=excluded_place_ids,
                selected_place_ids=selected_place_ids,
                used_place_categories=used_place_categories,
                used_category_details=used_category_details,
                has_drugstore=has_drugstore,
                is_last_place=is_last_place,
                prev_points=prev_points,
                other_course_points=other_course_points,
                user_walk_preference=user_walk_preference,
                config=mmr_config,
                slot_index=idx,
                flow=flow_config,
                origin=origin,
                avoid_categories=avoid_categories,
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
            selected_entries.append(selected)

        if len(selected_entries) <= 2 or len(used_place_categories) < 2:
            continue

        used_today.update(selected_place_ids)
        used_by_rank.setdefault(rank, set()).update(selected_place_ids)
        selected_slot_categories.append(
            [place["place_category"] for _, place in selected_entries]
        )

        schedule = DailySchedule(
            date=current_date,
            start_location=StartLocation(name=start_name, mapX=start_lat, mapY=start_lng),
            places=_build_ordered_place_items(
                selected_entries, start_lat, start_lng, flow=flow_config
            ),
        )
        daily_schedules.append(schedule)

    return daily_schedules
