import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.schemas.recommendation import RecommendationRequest, RecommendationResponse
from app.service.inference import apply_rule
from app.service.recommendation_persistence import save_recommendations
from app.utils.security import get_current_user


router = APIRouter(prefix="/api", tags=["recommendation"])


@router.post(
    "/course",
    response_model=RecommendationResponse,
    summary="추천 코스 생성 API",
)
def recommen_courses(
    request: RecommendationRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        rule_result = apply_rule(request, db=db)
        save_recommendations(rule_result, user_id=current_user["id"], db=db)
        db.commit()
        return rule_result
    except ValueError as error:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(error))
    except Exception:
        db.rollback()
        logging.exception("코스 추천 생성 또는 저장에 실패했습니다.")
        raise HTTPException(status_code=500, detail="코스 추천에 실패했습니다.")
