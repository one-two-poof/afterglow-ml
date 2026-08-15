from fastapi import APIRouter, Request

router = APIRouter(
    prefix="/api",
    tags=["health"]
)

@router.get("/health")
def health(request: Request) -> dict:
    return {
        "status": "ok",
        "message": "시스템 가동 준비 완료"
    }