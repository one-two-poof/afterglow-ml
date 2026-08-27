import os

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="JWT access token",
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization 헤더는 Bearer 토큰 형식이어야 합니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    if not SECRET_KEY or not ALGORITHM:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT 서버 설정이 올바르지 않습니다.",
        )

    try:
        # Never derive the accepted algorithm from the token header. The server
        # configuration is the trust boundary for signature verification.
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "id"]},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="만료된 인증 토큰입니다.",
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 인증 토큰입니다.",
        )

    user_id = payload.get("id")
    if isinstance(user_id, bool):
        user_id = None
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 토큰의 사용자 ID가 올바르지 않습니다.",
        )

    if user_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 토큰의 사용자 ID가 올바르지 않습니다.",
        )

    payload["id"] = user_id
    return payload
