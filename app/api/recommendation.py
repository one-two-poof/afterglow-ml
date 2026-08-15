"""추천 서비스의 HTTP 엔드포인트와 응답 조립을 담당한다."""

from uuid import uuid4

from fastapi import APIRouter, Query, Request, HTTPException

from app.config.settings import (
    DEFAULT_RESULT_LIMIT,
    DEFAULT_TOP_COURSES,
    MAX_RESULT_LIMIT,
    MAX_TOP_COURSES,
)


from app.schemas.recommendation import RecommendationResponse, RecommendationRequest

from app.rule.analytics_service import anonymize_user_id, emit_event
from app.rule.inference import imsi

# 애플리케이션 구동점에서 한 번에 등록할 추천 전용 라우터다.
router = APIRouter(
    prefix="/api",
    tags=["recommendation"]
)

@router.post("/course", response_model=RecommendationResponse, summary="추천 코스 생성 API")
def recommen_courses(requeset: RecommendationRequest):
    try:
        result = imsi(requeset)
        return result
    except Exception as e:
        print(f"추천 중 에러 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"코스 추천 실패: {str(e)}")




"""
@router.post("/recommend/places", response_model=PlaceRecommendationResponse)
def recommend_places(
    payload: RecommendationRequest,
    request: Request,
    limit: int = Query(default=DEFAULT_RESULT_LIMIT, ge=1, le=MAX_RESULT_LIMIT),
) -> PlaceRecommendationResponse:

    # 각 요청에 피드백 및 분석 로그 연결용 고유 ID를 발급한다.
    recommendation_id = str(uuid4())
    # 오케스트레이터가 입력을 내부 Anchor와 시술 컨텍스트로 변환한다.
    anchor = resolve_anchor(payload, request.app.state.place_repository)
    treatments = resolve_treatments(payload)
    # HTTP 계층은 계산하지 않고 후보 추천 서비스에 모든 규칙 계산을 위임한다.
    candidates = request.app.state.candidate_service.recommend(
        anchor=anchor,
        treatments=treatments,
        user_purpose=payload.user_purpose,
        user_walk_preference=payload.user_walk_preference,
        limit=limit,
    )
    # 원본 JWT는 저장하지 않고 해시로 변환한 분석 이벤트만 남긴다.
    emit_event(
        "place_recommendation_generated",
        recommendation_id=recommendation_id,
        user_hash=anonymize_user_id(payload.jwt),
        anchor_name=anchor.name,
        treatments=[vars(item) for item in treatments],
        purpose=payload.user_purpose,
        place_ids=[item["place_id"] for item in candidates],
    )
    # 내부 dict를 명시적 Pydantic 응답 모델로 변환해 스키마를 보장한다.
    return PlaceRecommendationResponse(
        recommendation_id=recommendation_id,
        data=PlaceRecommendationData(
            anchor=anchor_response(anchor),
            active_treatments=active_treatment_responses(treatments),
            candidate_places=[CandidatePlaceResponse(**item) for item in candidates],
        ),
    )


@router.post("/recommend/courses", response_model=CourseRecommendationResponse)
def recommend_courses(
    payload: RecommendationRequest,
    request: Request,
    top_n: int = Query(default=DEFAULT_TOP_COURSES, ge=1, le=MAX_TOP_COURSES),
) -> CourseRecommendationResponse:
    필터를 통과한 장소를 조합하여 점수순 추천 코스를 반환한다.
    recommendation_id = str(uuid4())
    anchor = resolve_anchor(payload, request.app.state.place_repository)
    treatments = resolve_treatments(payload)
    # CourseService가 장소 조합, 방문 순서, 거리 및 다양성 점수를 계산한다.
    courses = request.app.state.course_service.recommend(
        anchor=anchor,
        treatments=treatments,
        user_purpose=payload.user_purpose,
        user_walk_preference=payload.user_walk_preference,
        top_n=top_n,
    )
    # 로그 크기를 제한하기 위해 코스 전체가 아닌 순위·점수·장소 ID만 기록한다.
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


@router.post("/feedback/course-selection", response_model=FeedbackResponse)
def collect_course_selection(payload: CourseSelectionFeedbackRequest) -> FeedbackResponse:
    사용자의 코스 선택 여부를 익명 분석 이벤트로 기록한다.
    # 현재 피드백 저장소는 DB가 아니라 구조화된 애플리케이션 로그다.
    emit_event(
        payload.event_type,
        recommendation_id=payload.recommendation_id,
        user_hash=anonymize_user_id(payload.jwt),
        selected_course_rank=payload.selected_course_rank,
        selected_place_ids=payload.selected_place_ids,
    )
    return FeedbackResponse()
"""