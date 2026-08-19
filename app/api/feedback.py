import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.schemas.feedback import CourseFeedbackRequest
from app.service.feedback import CourseSelectionNotFoundError, save_selected_course
from app.utils.security import get_current_user


router = APIRouter(prefix="/api", tags=["feedback"])


@router.post(
    "/course-selection",
    response_class=PlainTextResponse,
    summary="선택한 추천 코스 저장 API",
)
def create_course_feedback(
    request: CourseFeedbackRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        save_selected_course(
            course_id=request.course_id,
            user_id=current_user["id"],
            db=db,
        )
        db.commit()
        return "ok!"
    except CourseSelectionNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="추천 코스를 찾을 수 없습니다.")
    except Exception:
        db.rollback()
        logging.exception("선택한 추천 코스 저장에 실패했습니다.")
        raise HTTPException(status_code=500, detail="피드백 저장에 실패했습니다.")
