"""추천 및 피드백 이벤트를 개인정보 최소화 형태로 기록한다."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any


# 추천 이벤트만 별도로 필터링할 수 있는 전용 로거 이름을 사용한다.
LOGGER = logging.getLogger("afterglow.analytics")
# 운영 환경에서는 반드시 별도 비밀값으로 덮어써야 하는 해시 salt다.
HASH_SALT = os.getenv("ANALYTICS_HASH_SALT", "afterglow-local-only")


def anonymize_user_id(user_value: str | None) -> str | None:
    """원본 사용자 값을 저장하지 않고 salt가 결합된 SHA-256 해시를 반환한다."""
    if not user_value:
        return None
    value = f"{HASH_SALT}:{user_value}".encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def emit_event(event_type: str, **payload: Any) -> dict[str, Any]:
    """UTC 발생 시각을 붙인 구조화 이벤트를 JSON 한 줄로 기록한다."""
    # 호출자가 전달한 payload 앞에 공통 이벤트 메타데이터를 추가한다.
    event = {
        "event_type": event_type,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    # 한글을 보존하고 공백을 제거해 로그 수집 비용과 파싱 오차를 줄인다.
    LOGGER.info(json.dumps(event, ensure_ascii=False, separators=(",", ":")))
    return event
