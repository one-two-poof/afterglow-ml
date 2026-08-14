"""FastAPI 애플리케이션을 생성하고 런타임 의존성을 연결하는 구동점이다."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api.recommendation import router as recommendation_router
from app.config.settings import APP_TITLE, APP_VERSION
from app.repositories.csv_place_repository import CsvPlaceRepository
from app.rule.candidate_service import CandidateService
from app.rule.course_service import CourseService


# app/의 상위 프로젝트 루트를 기준으로 data/ 경로를 계산한다.
BASE_DIR = Path(__file__).resolve().parent.parent
# 분석 이벤트가 JSON 한 줄 형태로 그대로 출력되도록 메시지만 기록한다.
logging.basicConfig(level=logging.INFO, format="%(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작 시 데이터와 서비스를 한 번 구성하고 종료 시 참조를 해제한다."""
    # Repository 구현체만 바꾸면 추천 규칙을 수정하지 않고 DB로 전환할 수 있다.
    repository = CsvPlaceRepository(BASE_DIR / "data")
    # 요청마다 CSV를 다시 읽지 않도록 앱 상태에 싱글턴 서비스 그래프를 보관한다.
    app.state.place_repository = repository
    app.state.candidate_service = CandidateService(repository)
    app.state.course_service = CourseService(app.state.candidate_service)
    # 여기서 요청을 처리하며, yield 이후는 애플리케이션 종료 정리 구간이다.
    yield
    app.state.place_repository = None
    app.state.candidate_service = None
    app.state.course_service = None


# 구동점에는 비즈니스 규칙을 두지 않고 앱 생성과 라우터 등록만 둔다.
app = FastAPI(title=APP_TITLE, version=APP_VERSION, lifespan=lifespan)
app.include_router(recommendation_router)
