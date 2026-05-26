import os
import subprocess
import sys

import pytest

os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-at-least-32-chars-long")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-at-least-32-characters-long")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://music:music@localhost:5432/local_music",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")


@pytest.fixture(scope="session")
def database_ready() -> bool:
    backend_dir = os.path.dirname(os.path.dirname(__file__))
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=os.environ.copy(),
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


@pytest.fixture(autouse=True)
def require_database(database_ready: bool, request: pytest.FixtureRequest) -> None:
    if request.node.get_closest_marker("no_db"):
        return
    if not database_ready:
        pytest.skip("Database migrations unavailable")


pytest_plugins = ["tests.conftest_db", "tests.conftest_auth"]
