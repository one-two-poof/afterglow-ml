from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

from recommendation.analytics_service import anonymize_user_id, emit_event
from recommendation.candidate_service import CandidateService, CsvPlaceRepository
from recommendation.config import (
    DEFAULT_RESULT_LIMIT,
    DEFAULT_TOP_COURSES,
    MAX_RESULT_LIMIT,
    MAX_TOP_COURSES,
    VALID_PURPOSES,
    VALID_TREATMENTS,
)
from recommendation.course_service import CourseService
from recommendation.models import Anchor, TreatmentContext


BASE_DIR = Path(__file__).resolve().parent
logging.basicConfig(level=logging.INFO, format="%(message)s")


class TreatmentEventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    treatment: str
    days_after: int | None = Field(default=None, ge=0)
    scheduled_at: datetime | None = None
    hospital_name: str | None = None
    package_id: str | None = None

    @model_validator(mode="after")
    def validate_timing(self) -> "TreatmentEventInput":
        if (self.days_after is None) == (self.scheduled_at is None):
            raise ValueError("Provide exactly one of days_after or scheduled_at")
        if self.scheduled_at is not None and self.scheduled_at.utcoffset() is None:
            raise ValueError("scheduled_at must include a timezone offset")
        return self


class RecommendationRequest(BaseModel):
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
        has_legacy = self.treatment is not None or self.days_after is not None
        if has_legacy and self.treatments is not None:
            raise ValueError("Use either treatment/days_after or treatments, not both")
        if has_legacy:
            if self.treatment is None or self.days_after is None:
                raise ValueError("Both treatment and days_after are required")
        elif not self.treatments:
            raise ValueError("At least one treatment is required")
        scheduled = [event for event in self.treatments or [] if event.scheduled_at]
        if scheduled and self.recommendation_at is None:
            raise ValueError("recommendation_at is required with scheduled_at")
        if self.recommendation_at is not None and self.recommendation_at.utcoffset() is None:
            raise ValueError("recommendation_at must include a timezone offset")
        return self


# Backward-compatible import name for existing clients and tests.
PlaceRecommendationRequest = RecommendationRequest


class AnchorResponse(BaseModel):
    name: str
    latitude: float
    longitude: float
    anchor_type: str | None = None


class TreatmentEvaluationResponse(BaseModel):
    treatment: str
    days_after: int
    status: str
    matched_risk_signals: list[str]
    hospital_name: str | None = None
    package_id: str | None = None


class ActiveTreatmentResponse(BaseModel):
    treatment: str
    days_after: int
    hospital_name: str | None = None
    package_id: str | None = None


class CandidatePlaceResponse(BaseModel):
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
    anchor: AnchorResponse
    active_treatments: list[ActiveTreatmentResponse]
    medical_compatibility_checked: bool = False
    candidate_places: list[CandidatePlaceResponse]


class PlaceRecommendationResponse(BaseModel):
    status: str = "success"
    recommendation_id: str
    data: PlaceRecommendationData


class CoursePlaceResponse(CandidatePlaceResponse):
    order: int
    distance_from_previous_km: float


class CourseResponse(BaseModel):
    rank: int
    course_score: float
    average_place_score: float
    route_score: float
    diversity_score: float
    purpose_composition_score: float
    total_distance_km: float
    places: list[CoursePlaceResponse]


class CourseRecommendationData(BaseModel):
    anchor: AnchorResponse
    active_treatments: list[ActiveTreatmentResponse]
    medical_compatibility_checked: bool = False
    courses: list[CourseResponse]


class CourseRecommendationResponse(BaseModel):
    status: str = "success"
    recommendation_id: str
    data: CourseRecommendationData


class CourseSelectionFeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation_id: str = Field(min_length=1)
    jwt: str | None = None
    event_type: Literal["course_selected", "course_dismissed"]
    selected_course_rank: int | None = Field(default=None, ge=1, le=MAX_TOP_COURSES)
    selected_place_ids: list[str] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def validate_selection(self) -> "CourseSelectionFeedbackRequest":
        if self.event_type == "course_selected" and self.selected_course_rank is None:
            raise ValueError("selected_course_rank is required for course_selected")
        return self


class FeedbackResponse(BaseModel):
    status: str = "accepted"


@asynccontextmanager
async def lifespan(app: FastAPI):
    repository = CsvPlaceRepository(BASE_DIR / "data")
    app.state.place_repository = repository
    app.state.candidate_service = CandidateService(repository)
    app.state.course_service = CourseService(app.state.candidate_service)
    yield
    app.state.place_repository = None
    app.state.candidate_service = None
    app.state.course_service = None


app = FastAPI(
    title="Afterglow Rule-Based Recommendation API",
    version="1.0.0",
    lifespan=lifespan,
)


def resolve_anchor(payload: RecommendationRequest, request: Request) -> Anchor:
    if payload.user_purpose not in VALID_PURPOSES:
        raise HTTPException(status_code=422, detail="Unsupported user_purpose")
    coordinates = (payload.anchor_latitude, payload.anchor_longitude)
    if (coordinates[0] is None) != (coordinates[1] is None):
        raise HTTPException(status_code=422, detail="Both anchor coordinates are required")
    if coordinates[0] is None:
        anchor = request.app.state.place_repository.find_anchor(payload.title)
        if anchor is None:
            raise HTTPException(status_code=404, detail="Anchor not found")
        return anchor
    return Anchor(
        name=payload.title,
        latitude=coordinates[0],
        longitude=coordinates[1],
        anchor_type=payload.anchor_type,
    )


def resolve_treatments(payload: RecommendationRequest) -> list[TreatmentContext]:
    events = payload.treatments or [
        TreatmentEventInput(treatment=payload.treatment, days_after=payload.days_after)
    ]
    contexts = []
    for event in events:
        if event.treatment not in VALID_TREATMENTS:
            raise HTTPException(422, f"Unsupported treatment: {event.treatment}")
        if event.days_after is not None:
            days_after = event.days_after
        else:
            recommendation_at = payload.recommendation_at
            scheduled_at = event.scheduled_at
            recommendation_local = recommendation_at.astimezone(scheduled_at.tzinfo)
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
    return [ActiveTreatmentResponse(**vars(item)) for item in items]


def anchor_response(anchor: Anchor) -> AnchorResponse:
    return AnchorResponse(
        name=anchor.name,
        latitude=anchor.latitude,
        longitude=anchor.longitude,
        anchor_type=anchor.anchor_type,
    )


@app.get("/health")
def health(request: Request) -> dict:
    return {
        "status": "ok",
        "service": "rule-based-recommendation",
        "version": app.version,
        "anchor_count": len(request.app.state.place_repository._anchors),
        "candidate_place_count": len(request.app.state.place_repository.list_places()),
        "catboost_loaded": False,
    }


@app.post("/recommend/places", response_model=PlaceRecommendationResponse)
def recommend_places(
    payload: RecommendationRequest,
    request: Request,
    limit: int = Query(default=DEFAULT_RESULT_LIMIT, ge=1, le=MAX_RESULT_LIMIT),
) -> PlaceRecommendationResponse:
    recommendation_id = str(uuid4())
    anchor = resolve_anchor(payload, request)
    treatments = resolve_treatments(payload)
    candidates = request.app.state.candidate_service.recommend(
        anchor=anchor,
        treatments=treatments,
        user_purpose=payload.user_purpose,
        user_walk_preference=payload.user_walk_preference,
        limit=limit,
    )
    emit_event(
        "place_recommendation_generated",
        recommendation_id=recommendation_id,
        user_hash=anonymize_user_id(payload.jwt),
        anchor_name=anchor.name,
        treatments=[vars(item) for item in treatments],
        purpose=payload.user_purpose,
        place_ids=[item["place_id"] for item in candidates],
    )
    return PlaceRecommendationResponse(
        recommendation_id=recommendation_id,
        data=PlaceRecommendationData(
            anchor=anchor_response(anchor),
            active_treatments=active_treatment_responses(treatments),
            candidate_places=[CandidatePlaceResponse(**item) for item in candidates],
        ),
    )


@app.post("/recommend/courses", response_model=CourseRecommendationResponse)
def recommend_courses(
    payload: RecommendationRequest,
    request: Request,
    top_n: int = Query(default=DEFAULT_TOP_COURSES, ge=1, le=MAX_TOP_COURSES),
) -> CourseRecommendationResponse:
    recommendation_id = str(uuid4())
    anchor = resolve_anchor(payload, request)
    treatments = resolve_treatments(payload)
    courses = request.app.state.course_service.recommend(
        anchor=anchor,
        treatments=treatments,
        user_purpose=payload.user_purpose,
        user_walk_preference=payload.user_walk_preference,
        top_n=top_n,
    )
    emit_event(
        "course_recommendation_generated",
        recommendation_id=recommendation_id,
        user_hash=anonymize_user_id(payload.jwt),
        anchor_name=anchor.name,
        treatments=[vars(item) for item in treatments],
        purpose=payload.user_purpose,
        courses=[
            {
                "rank": course["rank"],
                "course_score": course["course_score"],
                "place_ids": [place["place_id"] for place in course["places"]],
            }
            for course in courses
        ],
    )
    return CourseRecommendationResponse(
        recommendation_id=recommendation_id,
        data=CourseRecommendationData(
            anchor=anchor_response(anchor),
            active_treatments=active_treatment_responses(treatments),
            courses=[CourseResponse(**course) for course in courses],
        ),
    )


@app.post("/feedback/course-selection", response_model=FeedbackResponse)
def collect_course_selection(payload: CourseSelectionFeedbackRequest) -> FeedbackResponse:
    emit_event(
        payload.event_type,
        recommendation_id=payload.recommendation_id,
        user_hash=anonymize_user_id(payload.jwt),
        selected_course_rank=payload.selected_course_rank,
        selected_place_ids=payload.selected_place_ids,
    )
    return FeedbackResponse()
