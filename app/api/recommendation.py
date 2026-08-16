from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.schemas.recommendation import RecommendationResponse, RecommendationRequest
from app.config.database import get_db
from app.rule.inference import apply_rule

# 애플리케이션 구동점에서 한 번에 등록할 추천 전용 라우터다.
router = APIRouter(
    prefix="/api",
    tags=["recommendation"]
)

@router.post("/course", response_model=RecommendationResponse, summary="추천 코스 생성 API")
def recommen_courses(request: RecommendationRequest, db: Session = Depends(get_db)):
    try:
        rule_result = apply_rule(request, db=db)
        return RecommendationResponse(
            status="success",
            message="성공적으로 날짜별 추천 코스를 생성했습니다.",
            data=rule_result
        )
    
    except ValueError as ve:
        print(f"추천 중 데이터 에러 발생: {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
        
    except Exception as e:
        # 그 외 서버 에러 500
        print(f"추천 중 서버 에러 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"코스 추천 실패: {str(e)}")
