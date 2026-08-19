import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.recommendation import router as recommendation_router
from app.api.health import router as health_router
from app.utils.config_loader import load_rule_config

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    서버 구동 및 종료 시 실행되는 수명주기(Lifespan) 관리 함수
    """
    # ==================== 서버 시작 시 ====================
    logging.info("서버 시작 중: 규칙 설정(YAML)을 메모리에 적재합니다.")
    try:
        load_rule_config()
    except Exception as e:
        logging.error(f"설정 파일 로드 실패: {e}")
        raise e
    
    yield
    
    # ==================== 서버 종료 시 ====================
    logging.info("서버 종료 중: 리소스를 정리합니다.")

app = FastAPI(
    title="AI Course Recommendation API",
    description="시술 정보와 유저 성향을 기반으로 최적의 코스를 추천해 주는 API",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(recommendation_router)
app.include_router(health_router)