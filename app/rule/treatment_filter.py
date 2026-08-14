"""장소 위험 신호를 시술별 회복 규칙에 대입해 안전 상태를 결정한다."""

from enum import StrEnum

from app.config.settings import (
    HEAT_CATEGORY_KEYWORDS,
    MASSAGE_CATEGORY_KEYWORDS,
    RISK_HEAT_EXPOSURE,
    RISK_HIGH_ACTIVITY,
    RISK_MASSAGE_PRESSURE,
    RISK_OUTDOOR_EXPOSURE,
    TREATMENT_RISK_RULES,
)
from app.models.recommendation import Place, TreatmentContext


class FilterStatus(StrEnum):
    """추천 유지, 감점, 완전 제외의 세 단계 필터 상태다."""
    NORMAL = "NORMAL"
    PENALTY = "PENALTY"
    BLOCK = "BLOCK"


# 다중 위험·시술 상태를 병합할 때 숫자가 큰 더 엄격한 상태를 선택한다.
STATUS_PRIORITY = {
    FilterStatus.NORMAL: 0,
    FilterStatus.PENALTY: 1,
    FilterStatus.BLOCK: 2,
}


def place_risk_signals(place: Place) -> set[str]:
    """장소 속성과 카테고리 문자열에서 시술 회복 위험 신호를 추출한다."""
    signals: set[str] = set()
    # 걷기 난이도 4 이상은 회복 직후 부담이 큰 활동으로 본다.
    if place.walk_hard >= 4:
        signals.add(RISK_HIGH_ACTIVITY)
    # 야외 장소는 햇빛·기온 등 외부 환경 노출 가능성이 있다.
    if not place.is_indoor:
        signals.add(RISK_OUTDOOR_EXPOSURE)
    # 내부 분류와 카카오 상세 분류를 함께 검색해 특수 장소를 탐지한다.
    category_text = f"{place.place_category} {place.category_name}"
    if any(keyword in category_text for keyword in HEAT_CATEGORY_KEYWORDS):
        signals.add(RISK_HEAT_EXPOSURE)
    if any(keyword in category_text for keyword in MASSAGE_CATEGORY_KEYWORDS):
        signals.add(RISK_MASSAGE_PRESSURE)
    return signals


def _status_for_rule(treatment: str, signal: str, days_after: int) -> FilterStatus:
    """시술·위험 신호·경과일 조합에 해당하는 정책 상태를 조회한다."""
    periods = TREATMENT_RISK_RULES.get(treatment, {}).get(signal, ())
    # 정책의 시작일과 종료일은 모두 포함하는 폐구간이다.
    for first_day, last_day, status in periods:
        if first_day <= days_after <= last_day:
            return FilterStatus(status)
    return FilterStatus.NORMAL


def treatment_filter(
    treatment: str, place: Place, days_after: int
) -> tuple[FilterStatus, list[str]]:
    """하나의 시술을 기준으로 장소의 최종 상태와 전체 신호를 반환한다."""
    signals = sorted(place_risk_signals(place))
    statuses = [_status_for_rule(treatment, signal, days_after) for signal in signals]
    # 여러 신호가 겹치면 가장 보수적인 상태가 해당 시술의 최종 결과다.
    final_status = max(statuses, key=STATUS_PRIORITY.get, default=FilterStatus.NORMAL)
    return final_status, signals


def evaluate_treatments(
    treatments: list[TreatmentContext], place: Place
) -> tuple[FilterStatus, list[str], list[dict]]:
    """모든 활성 시술을 평가하고 가장 엄격한 상태와 상세 결과를 반환한다."""
    evaluations = []
    all_signals: set[str] = set()
    statuses = []
    for context in treatments:
        # 같은 장소라도 시술 종류와 경과일에 따라 결과가 달라진다.
        status, signals = treatment_filter(context.treatment, place, context.days_after)
        # 응답에는 최종 상태를 실제로 유발한 신호만 별도로 표시한다.
        matched_signals = [
            signal
            for signal in signals
            if status is not FilterStatus.NORMAL
            and _status_for_rule(context.treatment, signal, context.days_after) is status
        ]
        statuses.append(status)
        all_signals.update(signals)
        evaluations.append(
            {
                "treatment": context.treatment,
                "days_after": context.days_after,
                "status": status.value,
                "matched_risk_signals": matched_signals,
                "hospital_name": context.hospital_name,
                "package_id": context.package_id,
            }
        )
    # 활성 시술이 없으면 NORMAL, 하나라도 BLOCK이면 전체 결과는 BLOCK이다.
    final_status = max(statuses, key=STATUS_PRIORITY.get, default=FilterStatus.NORMAL)
    return final_status, sorted(all_signals), evaluations
