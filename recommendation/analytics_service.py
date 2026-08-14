from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any


LOGGER = logging.getLogger("afterglow.analytics")
HASH_SALT = os.getenv("ANALYTICS_HASH_SALT", "afterglow-local-only")


def anonymize_user_id(user_value: str | None) -> str | None:
    if not user_value:
        return None
    value = f"{HASH_SALT}:{user_value}".encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def emit_event(event_type: str, **payload: Any) -> dict[str, Any]:
    event = {
        "event_type": event_type,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    LOGGER.info(json.dumps(event, ensure_ascii=False, separators=(",", ":")))
    return event
