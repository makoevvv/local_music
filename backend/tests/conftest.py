import os

os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-at-least-32-chars-long")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://music:music@localhost:5432/local_music",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
