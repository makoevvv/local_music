from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from app.core.config import settings
from app.services.maintenance import cleanup_uploads


@pytest.mark.no_db
def test_cleanup_uploads_removes_only_expired_directories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "storage_local_path", str(tmp_path))
    monkeypatch.setattr(settings, "upload_session_ttl_seconds", 30)
    old = tmp_path / "uploads" / "old"
    fresh = tmp_path / "uploads" / "fresh"
    old.mkdir(parents=True)
    fresh.mkdir()
    (old / "audio.mp3").write_bytes(b"old")
    expired = time.time() - 120
    os.utime(old, (expired, expired))

    result = cleanup_uploads()

    assert result["removed"] == 1
    assert not old.exists()
    assert fresh.exists()
