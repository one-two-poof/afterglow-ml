"""후보 장소의 목적·안전·거리·도보 점수를 계산한다."""

from dataclasses import dataclass

from app.config.settings import (
    DEFAULT_PURPOSE_SCORE,
    PURPOSE_CATEGORY_SCORE,
    SCORE_WEIGHTS,
    TREATMENT_SCORE,
    WALK_SCORE_BY_EXCESS,
    WALK_SCORE_LARGE_EXCESS,
)
from app.rule.distance_service import distance_score
from app.models.recommendation import Place
from app.rule.treatment_filter import FilterStatus


@dataclass(frozen=True)
class ScoreBreakdown:
    """Place Score와 각 구성 점수를 함께 전달하는 불변 결과 객체다."""
    purpose_score: float
    treatment_score: float
    distance_score: float
    walk_score: float
    place_score: float


def purpose_score(user_purpose: str, place_category: str) -> float:
    """사용자 목적과 장소 카테고리의 사전 정의 적합도를 반환한다."""
    # 목적 또는 카테고리 조합이 없으면 중립 기본점수를 사용한다.
    return PURPOSE_CATEGORY_SCORE.get(user_purpose, {}).get(
        place_category, DEFAULT_PURPOSE_SCORE
    )


def walk_score(user_walk_preference: int, walk_hard: int) -> float:
    """장소 난이도가 사용자 허용 수준을 넘는 정도에 따라 감점한다."""
    # 장소가 더 쉬운 경우에는 초과치가 0이 되어 만점을 유지한다.
    excess = max(0, walk_hard - user_walk_preference)
    return WALK_SCORE_BY_EXCESS.get(excess, WALK_SCORE_LARGE_EXCESS)


def calculate_place_score(
    user_purpose: str,
    user_walk_preference: int,
    place: Place,
    filter_status: FilterStatus,
    distance_km: float,
) -> ScoreBreakdown:
    """네 구성 점수를 설정 가중치로 합산해 최종 Place Score를 만든다."""
    purpose = purpose_score(user_purpose, place.place_category)
    treatment = TREATMENT_SCORE[filter_status.value]
    distance = distance_score(distance_km)
    walk = walk_score(user_walk_preference, place.walk_hard)
    # 모든 구성 점수는 0~100 척도이며 가중치 합은 1.0이다.
    total = (
        purpose * SCORE_WEIGHTS["purpose"]
        + treatment * SCORE_WEIGHTS["treatment"]
        + distance * SCORE_WEIGHTS["distance"]
        + walk * SCORE_WEIGHTS["walk"]
    )
    # 외부 응답과 정렬의 재현성을 위해 최종 점수만 소수 둘째 자리로 고정한다.
    return ScoreBreakdown(purpose, treatment, distance, walk, round(total, 2))
