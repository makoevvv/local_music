from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_secret_key: str
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    database_url: str
    redis_url: str

    storage_local_path: str = "/data/storage"

    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    restricted_sources_enabled: bool = True
    search_cache_ttl_hours: int = 24
    rq_queue_name: str = "default"

    musicbrainz_user_agent: str = "local-music/0.1 (local@example.com)"
    lastfm_api_key: str | None = None

    search_timeout_seconds: int = 45
    ytdlp_socket_timeout_seconds: int = 15
    # SOCKS5/HTTP proxy for yt-dlp (search + download). Use socks5h:// so DNS goes via proxy.
    ytdlp_proxy: str | None = None
    # PO Token provider (bgutil HTTP server in compose). Bypasses YouTube bot checks without cookies.
    ytdlp_pot_base_url: str = "http://ytdlp-pot:4416"
    # Optional override: Netscape cookies file (usually not needed when ytdlp-pot is running).
    ytdlp_cookies_file: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    jwt_secret: str
    jwt_alg: str = "HS256"
    jwt_access_ttl_min: int = 60
    jwt_refresh_ttl_days: int = 30
    jwt_refresh_ttl_days_master: int = 7

    registration_enabled: bool = True
    registration_invite_only: bool = True

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
