import logging as _logging

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_logger = _logging.getLogger(__name__)

_DEFAULT_SECRET_KEY = "change-me-in-production-please"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CHATTY_", env_file=".env", extra="ignore"
    )

    database_url: str = "postgresql://postgres:cho9942!@localhost/chatty"
    secret_key: str = _DEFAULT_SECRET_KEY
    algorithm: str = "HS256"
    access_token_expire_hours: int = 2
    refresh_token_expire_days: int = 30

    @model_validator(mode="after")
    def warn_insecure_defaults(self) -> "Settings":
        if self.secret_key == _DEFAULT_SECRET_KEY:
            _logger.warning(
                "[SECURITY] CHATTY_SECRET_KEY is using the insecure default value. "
                "Set a strong random secret before deploying to production."
            )
        return self

    redis_url: str = "redis://localhost:6379/0"
    debug: bool = False
    db_pool_min: int = 2
    db_pool_max: int = 10
    google_client_id: str = ""
    google_client_secret: str = ""
    base_url: str = "http://localhost:7799"
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60


settings = Settings()
