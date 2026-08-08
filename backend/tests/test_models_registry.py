from __future__ import annotations

import app.models  # noqa: F401
from app.models import Base


def test_users_table_registered() -> None:
    assert "users" in Base.metadata.tables


def test_track_sources_table_registered() -> None:
    assert "track_sources" in Base.metadata.tables
    assert "acoustid_fingerprint" in Base.metadata.tables["tracks"].c
