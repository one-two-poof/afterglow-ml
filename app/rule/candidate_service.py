"""Anchor 주변 장소를 필터링하고 Place Score 순으로 정렬한다."""

from __future__ import annotations

from app.config.settings import MAX_SEARCH_RADIUS_KM
from app.models.recommendation import Anchor, TreatmentContext
from app.repositories.place_repository import PlaceRepository
from app.rule.distance_service import haversine_km
from app.rule.place_score import calculate_place_score
from app.rule.treatment_filter import FilterStatus, evaluate_treatments


class CandidateService:
    """저장소의 장소를 사용자·시술 조건에 맞는 추천 후보로 변환한다."""

    def __init__(self, repository: PlaceRepository):
        """저장 기술에 의존하지 않도록 Repository 계약을 주입받는다."""
        self.repository = repository

    def recommend(
        self,
        *,
        anchor: Anchor,
        treatments: list[TreatmentContext],
        user_purpose: str,
        user_walk_preference: int,
        limit: int,
    ) -> list[dict]:
        """반경·시술 규칙을 통과한 상위 후보 장소를 반환한다."""
        candidates = []
        for place in self.repository.list_places():
            # 현재 경로 API가 없으므로 Anchor와 장소 사이의 직선거리를 사용한다.
            distance = haversine_km(
                anchor.latitude, anchor.longitude, place.latitude, place.longitude
            )
            # 설정된 서비스 반경 밖의 장소는 이후 점수 계산 없이 즉시 제외한다.
            if distance > MAX_SEARCH_RADIUS_KM:
                continue
            # 다중 시술을 개별 평가한 뒤 가장 엄격한 최종 상태를 받는다.
            status, risk_signals, treatment_evaluations = evaluate_treatments(
                treatments, place
            )
            # BLOCK은 감점이 아니라 추천 결과에서 완전히 제거하는 상태다.
            if status is FilterStatus.BLOCK:
                continue
            # 남은 장소에 목적·시술·거리·도보 가중 점수를 계산한다.
            scores = calculate_place_score(
                user_purpose, user_walk_preference, place, status, distance
            )
            candidates.append(
                {
                    "place_id": place.place_id,
                    "place_name": place.place_name,
                    "place_category": place.place_category,
                    "category_name": place.category_name,
                    "latitude": place.latitude,
                    "longitude": place.longitude,
                    "is_indoor": place.is_indoor,
                    "walk_hard": place.walk_hard,
                    "distance_from_anchor_km": round(distance, 3),
                    "filter_status": status.value,
                    "risk_signals": risk_signals,
                    "treatment_evaluations": treatment_evaluations,
                    "purpose_score": scores.purpose_score,
                    "treatment_score": scores.treatment_score,
                    "distance_score": scores.distance_score,
                    "walk_score": scores.walk_score,
                    "place_score": scores.place_score,
                    "place_url": place.place_url,
                }
            )
        # 동점이면 가까운 장소, 그다음 안정적인 장소 ID 순으로 결정한다.
        candidates.sort(
            key=lambda item: (-item["place_score"], item["distance_from_anchor_km"], item["place_id"])
        )
        # API limit은 모든 필터와 정렬이 끝난 뒤 적용한다.
        return candidates[:limit]
