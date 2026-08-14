"""후보 장소를 세 곳씩 조합해 거리와 목적 조건을 만족하는 코스를 만든다."""

from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations, permutations

from app.rule.candidate_service import CandidateService
from app.config.settings import (
    COURSE_CANDIDATES_PER_CATEGORY,
    COURSE_DISTANCE_SCORE_BANDS,
    COURSE_PLACE_COUNT,
    COURSE_SCORE_WEIGHTS,
    MAX_COURSE_DISTANCE_KM,
    MAX_LEG_DISTANCE_KM,
    MAX_SAME_CATEGORY_PER_COURSE,
    MAX_SHARED_PLACES_BETWEEN_TOP_COURSES,
    MIN_DISTINCT_CATEGORIES,
    PURPOSE_REQUIRED_CATEGORIES,
    REST_MIN_INDOOR_PLACES,
)
from app.rule.distance_service import haversine_km
from app.models.recommendation import Anchor, TreatmentContext


def _route_distance_score(total_distance_km: float) -> float:
    """코스 누적 직선거리를 설정 구간 점수로 변환한다."""
    # 거리 구간은 가까운 상한부터 정렬되어 있어 첫 일치 점수를 반환한다.
    for upper_bound, score in COURSE_DISTANCE_SCORE_BANDS:
        if total_distance_km <= upper_bound:
            return score
    return 0.0


def _purpose_composition_score(user_purpose: str, places: tuple[dict, ...]) -> float | None:
    """목적별 필수 구성을 검증하고 충족 정도 점수를 반환한다."""
    # 휴식 목적은 특정 카테고리보다 실내 장소 수를 우선한다.
    if user_purpose == "휴식":
        indoor_count = sum(place["is_indoor"] for place in places)
        # 실내 장소 최소 개수를 충족하지 못하면 코스 자체를 제외한다.
        if indoor_count < REST_MIN_INDOOR_PLACES:
            return None
        return 100.0 if indoor_count == COURSE_PLACE_COUNT else 80.0

    # 문화관광·뷰티쇼핑은 목적별 핵심 카테고리가 적어도 하나 필요하다.
    required = PURPOSE_REQUIRED_CATEGORIES.get(user_purpose, set())
    matching_count = sum(place["place_category"] in required for place in places)
    if required and matching_count == 0:
        return None
    return 100.0 if matching_count >= 2 else 75.0


def _best_route(anchor: Anchor, places: tuple[dict, ...]) -> tuple[tuple[dict, ...], list[float], float] | None:
    """세 장소의 모든 방문 순서를 검사해 허용 범위 내 최단 순서를 찾는다."""
    best = None
    # 장소 수가 3개로 고정되어 있으므로 3! 전수조사가 단순하고 재현 가능하다.
    for ordered in permutations(places):
        # 첫 구간 거리도 계산하기 위해 Anchor를 좌표 목록 맨 앞에 둔다.
        points = [(anchor.latitude, anchor.longitude)] + [
            (place["latitude"], place["longitude"]) for place in ordered
        ]
        legs = [
            haversine_km(start[0], start[1], end[0], end[1])
            for start, end in zip(points, points[1:])
        ]
        total = sum(legs)
        # 한 구간이라도 보행 허용 거리를 넘으면 해당 순서를 사용할 수 없다.
        if any(distance > MAX_LEG_DISTANCE_KM for distance in legs):
            continue
        # 개별 구간이 짧아도 누적 이동 한도를 넘으면 제외한다.
        if total > MAX_COURSE_DISTANCE_KM:
            continue
        # 유효한 순서 중 누적 거리가 가장 짧은 하나만 유지한다.
        if best is None or total < best[2]:
            best = ordered, legs, total
    return best


class CourseService:
    """장소 후보를 유효한 코스로 조합하고 상위 결과의 다양성을 보장한다."""

    def __init__(self, candidate_service: CandidateService):
        """안전 필터와 Place Score 계산이 완료된 후보 서비스를 주입받는다."""
        self.candidate_service = candidate_service

    def recommend(
        self,
        *,
        anchor: Anchor,
        treatments: list[TreatmentContext],
        user_purpose: str,
        user_walk_preference: int,
        top_n: int,
    ) -> list[dict]:
        """사용자 목적에 맞는 상위 코스를 최대 top_n개 반환한다."""
        # 조합 전에 limit을 충분히 크게 두어 반경 내 전체 유효 후보를 받는다.
        all_candidates = self.candidate_service.recommend(
            anchor=anchor,
            treatments=treatments,
            user_purpose=user_purpose,
            user_walk_preference=user_walk_preference,
            limit=10_000,
        )
        # 조합 폭증을 막으면서 특정 카테고리 독점을 방지하기 위해 카테고리별로 자른다.
        by_category: dict[str, list[dict]] = defaultdict(list)
        for candidate in all_candidates:
            category_candidates = by_category[candidate["place_category"]]
            if len(category_candidates) < COURSE_CANDIDATES_PER_CATEGORY:
                category_candidates.append(candidate)
        candidate_places = [
            candidate
            for category_candidates in by_category.values()
            for candidate in category_candidates
        ]
        scored_courses = []
        # 중복 없는 세 장소 조합을 만든 뒤 구성·경로 조건을 차례로 적용한다.
        for place_group in combinations(candidate_places, COURSE_PLACE_COUNT):
            category_counts = Counter(place["place_category"] for place in place_group)
            # 한 카테고리가 코스 전체를 차지하지 못하도록 개수 상한을 둔다.
            if max(category_counts.values()) > MAX_SAME_CATEGORY_PER_COURSE:
                continue
            # 최소 두 종류 카테고리를 포함해야 코스로 인정한다.
            if len(category_counts) < MIN_DISTINCT_CATEGORIES:
                continue
            # 목적 필수 구성을 충족하지 못하면 None을 받아 즉시 제외한다.
            purpose_composition = _purpose_composition_score(user_purpose, place_group)
            if purpose_composition is None:
                continue
            # 거리 제한을 만족하는 방문 순서가 하나도 없으면 조합을 버린다.
            route = _best_route(anchor, place_group)
            if route is None:
                continue
            ordered_places, leg_distances, total_distance = route
            # 장소 품질은 개별 Place Score의 산술평균으로 대표한다.
            average_place_score = sum(p["place_score"] for p in ordered_places) / COURSE_PLACE_COUNT
            route_score = _route_distance_score(total_distance)
            # 세 장소 카테고리가 모두 다르면 다양성 만점을 준다.
            diversity_score = 100.0 if len(category_counts) == 3 else 70.0
            # 장소 품질, 경로, 다양성, 목적 구성을 정책 가중치로 합산한다.
            course_score = (
                average_place_score * COURSE_SCORE_WEIGHTS["places"]
                + route_score * COURSE_SCORE_WEIGHTS["route"]
                + diversity_score * COURSE_SCORE_WEIGHTS["diversity"]
                + purpose_composition * COURSE_SCORE_WEIGHTS["purpose_composition"]
            )
            # 각 장소에 1부터 시작하는 방문 순서와 직전 구간 거리를 붙인다.
            route_places = []
            for order, (place, leg_distance) in enumerate(
                zip(ordered_places, leg_distances), start=1
            ):
                route_places.append({**place, "order": order, "distance_from_previous_km": round(leg_distance, 3)})
            scored_courses.append(
                {
                    "course_score": round(course_score, 2),
                    "average_place_score": round(average_place_score, 2),
                    "route_score": route_score,
                    "diversity_score": diversity_score,
                    "purpose_composition_score": purpose_composition,
                    "total_distance_km": round(total_distance, 3),
                    "places": route_places,
                }
            )

        # Course Score가 같으면 총 이동거리가 짧은 코스를 우선한다.
        scored_courses.sort(
            key=lambda course: (-course["course_score"], course["total_distance_km"])
        )
        selected = []
        # 상위 코스끼리 지나치게 비슷하지 않도록 장소 교집합을 제한한다.
        for course in scored_courses:
            place_ids = {place["place_id"] for place in course["places"]}
            if any(
                len(place_ids & {place["place_id"] for place in chosen["places"]})
                > MAX_SHARED_PLACES_BETWEEN_TOP_COURSES
                for chosen in selected
            ):
                continue
            # 실제 선택된 순서대로 1부터 연속된 추천 순위를 부여한다.
            selected.append({**course, "rank": len(selected) + 1})
            if len(selected) == top_n:
                break
        return selected
