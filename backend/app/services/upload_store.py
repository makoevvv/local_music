from __future__ import annotations

import hashlib
import json
from typing import Any

from app.core.config import settings
from app.core.sync_redis import get_sync_redis

_SESSION = "upload:session:v1:"
_FINGERPRINT = "upload:fp:v1:"
_VERIFY = "upload:verify:v1:"


def _loads(raw: str | None) -> dict[str, Any] | None:
    if raw is None:
        return None
    data = json.loads(raw)
    return data if isinstance(data, dict) else None


def save_session(data: dict[str, Any]) -> None:
    get_sync_redis().setex(
        f"{_SESSION}{data['upload_id']}",
        settings.upload_session_ttl_seconds,
        json.dumps(data),
    )


def load_session(upload_id: str) -> dict[str, Any] | None:
    return _loads(get_sync_redis().get(f"{_SESSION}{upload_id}"))


def delete_session(upload_id: str) -> None:
    get_sync_redis().delete(f"{_SESSION}{upload_id}")


def save_fingerprint_cache(sha256: str, fingerprint: str | None, raw: list[int]) -> None:
    get_sync_redis().setex(
        f"{_FINGERPRINT}{sha256}",
        settings.verification_cache_ttl_seconds,
        json.dumps({"fingerprint": fingerprint, "fingerprint_raw": raw}),
    )


def load_fingerprint_cache(sha256: str) -> dict[str, Any] | None:
    return _loads(get_sync_redis().get(f"{_FINGERPRINT}{sha256}"))


def _verify_key(sha256: str, query: str) -> str:
    digest = hashlib.sha256(query.encode()).hexdigest()
    return f"{_VERIFY}{sha256}:{digest}"


def save_verification_cache(sha256: str, query: str, payload: dict[str, Any]) -> None:
    get_sync_redis().setex(
        _verify_key(sha256, query),
        settings.verification_cache_ttl_seconds,
        json.dumps(payload),
    )


def load_verification_cache(sha256: str, query: str) -> dict[str, Any] | None:
    return _loads(get_sync_redis().get(_verify_key(sha256, query)))
