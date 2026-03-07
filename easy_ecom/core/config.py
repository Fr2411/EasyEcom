from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv()


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _to_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value.strip())
    except (TypeError, ValueError):
        return default


def _to_csv(value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if not value:
        return default
    parsed = [item.strip() for item in value.split(",") if item.strip()]
    return tuple(parsed) or default


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(
        default_factory=lambda: Path(os.getenv("DATA_DIR", "easy_ecom/data_files"))
    )
    app_title: str = field(default_factory=lambda: os.getenv("APP_TITLE", "Easy_Ecom"))
    allow_backorder: bool = field(
        default_factory=lambda: _to_bool(os.getenv("ALLOW_BACKORDER"), False)
    )
    super_admin_email: str = field(default_factory=lambda: os.getenv("SUPER_ADMIN_EMAIL", ""))
    super_admin_password: str = field(default_factory=lambda: os.getenv("SUPER_ADMIN_PASSWORD", ""))
    create_default_client: bool = field(
        default_factory=lambda: _to_bool(os.getenv("CREATE_DEFAULT_CLIENT"), False)
    )
    storage_backend: str = field(
        default_factory=lambda: os.getenv("STORAGE_BACKEND", "csv").strip().lower()
    )
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "").strip())
    postgres_host: str = field(default_factory=lambda: os.getenv("POSTGRES_HOST", "localhost"))
    postgres_port: int = field(default_factory=lambda: _to_int(os.getenv("POSTGRES_PORT"), 5432))
    postgres_db: str = field(default_factory=lambda: os.getenv("POSTGRES_DB", "easy_ecom"))
    postgres_user: str = field(default_factory=lambda: os.getenv("POSTGRES_USER", "easy_ecom"))
    postgres_password: str = field(
        default_factory=lambda: os.getenv("POSTGRES_PASSWORD", "easy_ecom")
    )
    postgres_echo: bool = field(default_factory=lambda: _to_bool(os.getenv("POSTGRES_ECHO"), False))
    postgres_pool_size: int = field(
        default_factory=lambda: _to_int(os.getenv("POSTGRES_POOL_SIZE"), 5)
    )
    postgres_max_overflow: int = field(
        default_factory=lambda: _to_int(os.getenv("POSTGRES_MAX_OVERFLOW"), 10)
    )
    postgres_dsn_override: str = field(
        default_factory=lambda: os.getenv("POSTGRES_DSN", "").strip()
    )
    cors_allow_origins: tuple[str, ...] = field(
        default_factory=lambda: _to_csv(
            os.getenv("CORS_ALLOW_ORIGINS"),
            ("http://localhost:3000", "http://127.0.0.1:3000"),
        )
    )

    @property
    def postgres_dsn(self) -> str:
        if self.database_url:
            return self.database_url
        if self.postgres_dsn_override:
            return self.postgres_dsn_override
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
