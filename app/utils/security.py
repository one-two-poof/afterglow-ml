import os
from fastapi import Header, HTTPException, status
import jwt

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")

def get_current_user(authorization: str = Header(..., description="Bearer {JWT_TOKEN}")) -> dict:
    """
    Authorization 헤더에서 JWT를 파싱하고 검증하는 의존성 함수
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 토큰 형식이 올바르지 않습니다. ('Bearer <token>' 형식 필요)",
        )
    
    token = authorization.split(" ")[1]
    
    try:
        # 토큰 디코딩 및 검증
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰이 만료되었습니다.",
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다.",
        )