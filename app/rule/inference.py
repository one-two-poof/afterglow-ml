"""API 입력을 도메인 값으로 변환하며 전체 추천 흐름을 조정한다."""

from fastapi import HTTPException

from app.config.settings import VALID_PURPOSES, VALID_TREATMENTS
from app.models.recommendation import Anchor, TreatmentContext
from app.repositories.place_repository import PlaceRepository
from app.schemas.recommendation import (
    ActiveTreatmentResponse,
    AnchorResponse,
    RecommendationRequest,
    TreatmentEventInput,
)


def resolve_anchor(payload: RecommendationRequest, repository: PlaceRepository) -> Anchor:
    """요청의 이름 조회 또는 직접 좌표 방식으로 출발점을 결정한다."""
    # 목적은 Pydantic의 단순 문자열 검증이 아니라 정책 집합을 기준으로 검증한다.
    if payload.user_purpose not in VALID_PURPOSES:
        raise HTTPException(status_code=422, detail="Unsupported user_purpose")
    # 위도와 경도는 부분 입력을 허용하지 않는다.
    coordinates = (payload.anchor_latitude, payload.anchor_longitude)
    if (coordinates[0] is None) != (coordinates[1] is None):
        raise HTTPException(status_code=422, detail="Both anchor coordinates are required")
    # 좌표가 없을 때만 Repository에서 title 완전 일치 Anchor를 찾는다.
    if coordinates[0] is None:
        anchor = repository.find_anchor(payload.title)
        if anchor is None:
            raise HTTPException(status_code=404, detail="Anchor not found")
        return anchor
    # 좌표 직접 입력은 저장소에 존재하지 않아도 임시 Anchor로 사용할 수 있다.
    return Anchor(
        name=payload.title,
        latitude=coordinates[0],
        longitude=coordinates[1],
        anchor_type=payload.anchor_type,
    )


def resolve_treatments(payload: RecommendationRequest) -> list[TreatmentContext]:
    """단일·다중 시술 요청을 활성 시술 컨텍스트 목록으로 통일한다."""
    # 기존 단일 시술 형식을 배열과 같은 처리 흐름으로 정규화한다.
    events = payload.treatments or [
        TreatmentEventInput(treatment=payload.treatment, days_after=payload.days_after)
    ]
    contexts = []
    for event in events:
        # 지원 목록 밖의 시술은 위험 정책이 없으므로 명시적으로 거부한다.
        if event.treatment not in VALID_TREATMENTS:
            raise HTTPException(422, f"Unsupported treatment: {event.treatment}")
        if event.days_after is not None:
            # 클라이언트가 경과일을 제공한 경우 추가 날짜 계산 없이 사용한다.
            days_after = event.days_after
        else:
            recommendation_at = payload.recommendation_at
            scheduled_at = event.scheduled_at
            # 시술 시각의 시간대로 추천 시각을 변환한 뒤 현지 날짜 차이를 계산한다.
            recommendation_local = recommendation_at.astimezone(scheduled_at.tzinfo)
            # 추천 시점 이후에 예정된 미래 시술은 아직 활성화되지 않았으므로 제외한다.
            if recommendation_local < scheduled_at:
                continue
            days_after = (recommendation_local.date() - scheduled_at.date()).days
        contexts.append(
            TreatmentContext(
                treatment=event.treatment,
                days_after=days_after,
                hospital_name=event.hospital_name,
                package_id=event.package_id,
            )
        )
    return contexts


def active_treatment_responses(items: list[TreatmentContext]) -> list[ActiveTreatmentResponse]:
    """내부 시술 컨텍스트를 외부 응답 스키마로 변환한다."""
    return [ActiveTreatmentResponse(**vars(item)) for item in items]


def anchor_response(anchor: Anchor) -> AnchorResponse:
    """내부 Anchor 객체를 외부 응답 스키마로 변환한다."""
    return AnchorResponse(
        name=anchor.name,
        latitude=anchor.latitude,
        longitude=anchor.longitude,
        anchor_type=anchor.anchor_type,
    )
