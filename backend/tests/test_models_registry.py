from __future__ import annotations

import app.models  # noqa: F401
from app.models import Base


def test_users_table_registered() -> None:
    assert "users" in Base.metadata.tables
