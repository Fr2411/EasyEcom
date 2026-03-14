from __future__ import annotations

from dataclasses import dataclass, field
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
    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "development").strip().lower())
    app_title: str = field(default_factory=lambda: os.getenv("APP_TITLE", "Easy_Ecom"))
    allow_backorder: bool = field(
        default_factory=lambda: _to_bool(os.getenv("ALLOW_BACKORDER"), False)
    )
    auto_create_schema: bool = field(
        default_factory=lambda: _to_bool(os.getenv("AUTO_CREATE_SCHEMA"), False)
    )
    super_admin_email: str = field(default_factory=lambda: os.getenv("SUPER_ADMIN_EMAIL", ""))
    super_admin_password: str = field(default_factory=lambda: os.getenv("SUPER_ADMIN_PASSWORD", ""))
    create_default_client: bool = field(
        default_factory=lambda: _to_bool(os.getenv("CREATE_DEFAULT_CLIENT"), False)
    )
    global_client_id: str = field(
        default_factory=lambda: os.getenv(
            "GLOBAL_CLIENT_ID",
            "00000000-0000-0000-0000-000000000000",
        ).strip()
    )
    global_client_slug: str = field(
        default_factory=lambda: os.getenv("GLOBAL_CLIENT_SLUG", "global").strip().lower()
    )
    request_id_header: str = field(
        default_factory=lambda: os.getenv("REQUEST_ID_HEADER", "X-Request-Id").strip()
    )
    password_reset_ttl_minutes: int = field(
        default_factory=lambda: _to_int(os.getenv("PASSWORD_RESET_TTL_MINUTES"), 60)
    )
    invitation_ttl_hours: int = field(
        default_factory=lambda: _to_int(os.getenv("INVITATION_TTL_HOURS"), 72)
    )
    database_url: str | None = field(
        default_factory=lambda: (os.getenv("DATABASE_URL", "").strip() or None)
    )
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
    session_secret: str = field(default_factory=lambda: os.getenv("SESSION_SECRET", "dev-session-secret"))
    session_cookie_name: str = field(default_factory=lambda: os.getenv("SESSION_COOKIE_NAME", "easy_ecom_session"))
    session_cookie_secure: bool = field(
        default_factory=lambda: _to_bool(os.getenv("SESSION_COOKIE_SECURE"), False)
    )
    session_cookie_domain: str | None = field(
        default_factory=lambda: (os.getenv("SESSION_COOKIE_DOMAIN", "").strip() or None)
    )
    session_cookie_samesite: str = field(
        default_factory=lambda: os.getenv("SESSION_COOKIE_SAMESITE", "lax").strip().lower()
    )
    bcrypt_rounds: int = field(default_factory=lambda: _to_int(os.getenv("BCRYPT_ROUNDS"), 12))

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

    @property
    def is_sqlite(self) -> bool:
        return self.postgres_dsn.startswith("sqlite")

    @property
    def should_auto_create_schema(self) -> bool:
        return self.auto_create_schema or self.is_sqlite


settings = Settings()
