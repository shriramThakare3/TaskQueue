"""
core/config.py
--------------
Central configuration loaded from environment variables / .env file.
All services (api, worker) import settings from here.
"""
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # ── Database ────────────────────────────────────────────────────────────
    POSTGRES_USER: str = Field(default="taskuser")
    POSTGRES_PASSWORD: str = Field(default="taskpass")
    POSTGRES_DB: str = Field(default="taskqueue")
    POSTGRES_HOST: str = Field(default="db")
    POSTGRES_PORT: int = Field(default=5432)

    # ── Worker ──────────────────────────────────────────────────────────────
    WORKER_POLL_INTERVAL: float = Field(default=2.0)   # seconds between polls
    WORKER_MAX_RETRIES: int = Field(default=3)          # max task retry attempts
    WORKER_COUNT: int = Field(default=2)                # concurrent worker threads

    # ── App ─────────────────────────────────────────────────────────────────
    APP_ENV: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Singleton — import this everywhere
settings = Settings()
