"""추천 API가 외부와 주고받는 요청·응답 데이터 형식을 정의한다."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.config.settings import MAX_TOP_COURSES


class TreatmentEventInput(BaseModel):
    """단일 시술의 종류와 평가 기준 시점을 표현한다."""

    # 명세에 없는 필드가 조용히 무시되어 오입력되는 것을 방지한다.
    model_config = ConfigDict(extra="forbid")

    treatment: str
    days_after: int | None = Field(default=None, ge=0)
    scheduled_at: datetime | None = None
    hospital_name: str | None = None
    package_id: str | None = None

    @model_validator(mode="after")
    def validate_timing(self) -> "TreatmentEventInput":
        """경과일과 시술 시각 중 정확히 하나만 받도록 검증한다."""
        if (self.days_after is None) == (self.scheduled_at is None):
            raise ValueError("Provide exactly one of days_after or scheduled_at")
        if self.scheduled_at is not None and self.scheduled_at.utcoffset() is None:
            raise ValueError("scheduled_at must include a timezone offset")
        return self


class RecommendationRequest(BaseModel):
    """장소 추천과 코스 추천이 공통으로 사용하는 요청 본문이다."""

    model_config = ConfigDict(extra="forbid")

    jwt: str | None = None
    title: str = Field(min_length=1)
    treatment: str | None = None
    days_after: int | None = Field(default=None, ge=0)
    treatments: list[TreatmentEventInput] | None = Field(default=None, min_length=1, max_length=20)
    recommendation_at: datetime | None = None
    user_purpose: str
    user_walk_preference: int = Field(ge=1, le=5)
    anchor_type: str | None = None
    anchor_latitude: float | None = Field(default=None, ge=-90, le=90)
    anchor_longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def validate_treatments(self) -> "RecommendationRequest":
        """단일·다중 시술 형식과 시간대 관련 교차 필드를 검증한다."""
        # 기존 클라이언트의 단일 시술 필드와 신규 배열 형식은 혼용할 수 없다.
        has_legacy = self.treatment is not None or self.days_after is not None
        if has_legacy and self.treatments is not None:
            raise ValueError("Use either treatment/days_after or treatments, not both")
        if has_legacy:
            if self.treatment is None or self.days_after is None:
                raise ValueError("Both treatment and days_after are required")
        elif not self.treatments:
            raise ValueError("At least one treatment is required")
        # 시술 시각으로 경과일을 계산하려면 추천 평가 시각도 반드시 필요하다.
        scheduled = [event for event in self.treatments or [] if event.scheduled_at]
        if scheduled and self.recommendation_at is None:
            raise ValueError("recommendation_at is required with scheduled_at")
        if self.recommendation_at is not None and self.recommendation_at.utcoffset() is None:
            raise ValueError("recommendation_at must include a timezone offset")
        return self


# 기존 코드가 사용하던 클래스 이름을 계속 지원한다.
PlaceRecommendationRequest = RecommendationRequest


class AnchorResponse(BaseModel):
    """추천 경로의 출발점으로 사용한 병원·숙소 또는 사용자 좌표다."""
    name: str
    latitude: float
    longitude: float
    anchor_type: str | None = None


class TreatmentEvaluationResponse(BaseModel):
    """후보 장소 한 곳에 대한 개별 시술의 안전 규칙 평가 결과다."""
    treatment: str
    days_after: int
    status: str
    matched_risk_signals: list[str]
    hospital_name: str | None = None
    package_id: str | None = None


class ActiveTreatmentResponse(BaseModel):
    """추천 평가 시점에 이미 시행되어 활성화된 시술 정보다."""
    treatment: str
    days_after: int
    hospital_name: str | None = None
    package_id: str | None = None


class CandidatePlaceResponse(BaseModel):
    """필터를 통과한 후보 장소와 점수 상세를 반환한다."""
    place_id: str
    place_name: str
    place_category: str
    category_name: str
    latitude: float
    longitude: float
    is_indoor: bool
    walk_hard: int
    distance_from_anchor_km: float
    filter_status: str
    risk_signals: list[str]
    treatment_evaluations: list[TreatmentEvaluationResponse]
    purpose_score: float
    treatment_score: float
    distance_score: float
    walk_score: float
    place_score: float
    place_url: str


class PlaceRecommendationData(BaseModel):
    """장소 추천 응답의 실제 데이터 영역이다."""
    anchor: AnchorResponse
    active_treatments: list[ActiveTreatmentResponse]
    medical_compatibility_checked: bool = False
    candidate_places: list[CandidatePlaceResponse]


class PlaceRecommendationResponse(BaseModel):
    """장소 추천 API의 최상위 성공 응답이다."""
    status: str = "success"
    recommendation_id: str
    data: PlaceRecommendationData


class CoursePlaceResponse(CandidatePlaceResponse):
    """후보 장소 정보에 코스 방문 순서와 이전 구간 거리를 추가한다."""
    order: int
    distance_from_previous_km: float


class CourseResponse(BaseModel):
    """장소 세 곳으로 구성된 단일 추천 코스와 점수 구성이다."""
    rank: int
    course_score: float
    average_place_score: float
    route_score: float
    diversity_score: float
    purpose_composition_score: float
    total_distance_km: float
    places: list[CoursePlaceResponse]


class CourseRecommendationData(BaseModel):
    """코스 추천 응답의 실제 데이터 영역이다."""
    anchor: AnchorResponse
    active_treatments: list[ActiveTreatmentResponse]
    medical_compatibility_checked: bool = False
    courses: list[CourseResponse]


class CourseRecommendationResponse(BaseModel):
    """코스 추천 API의 최상위 성공 응답이다."""
    status: str = "success"
    recommendation_id: str
    data: CourseRecommendationData


class CourseSelectionFeedbackRequest(BaseModel):
    """추천 코스 선택 또는 미선택 분석 이벤트 요청이다."""

    model_config = ConfigDict(extra="forbid")

    recommendation_id: str = Field(min_length=1)
    jwt: str | None = None
    event_type: Literal["course_selected", "course_dismissed"]
    selected_course_rank: int | None = Field(default=None, ge=1, le=MAX_TOP_COURSES)
    selected_place_ids: list[str] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def validate_selection(self) -> "CourseSelectionFeedbackRequest":
        """선택 이벤트에는 선택 순위가 반드시 포함되도록 보장한다."""
        if self.event_type == "course_selected" and self.selected_course_rank is None:
            raise ValueError("selected_course_rank is required for course_selected")
        return self


class FeedbackResponse(BaseModel):
    """피드백 이벤트 접수 완료 응답이다."""
    status: str = "accepted"
