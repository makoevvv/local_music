from __future__ import annotations

import app.models  # noqa: F401
from app.models import Base


def test_users_table_registered() -> None:
    assert "users" in Base.metadata.tables


def test_track_sources_table_registered() -> None:
    table = Base.metadata.tables["track_sources"]
    assert "acoustid_fingerprint" in Base.metadata.tables["tracks"].c
    unique = next(
        index for index in table.indexes if index.name == "uq_track_sources_track_kind_id"
    )
    assert unique.unique is True
    assert list(unique.columns.keys()) == ["track_id", "source_kind", "source_id"]
    assert unique.dialect_options["postgresql"]["nulls_not_distinct"] is True
