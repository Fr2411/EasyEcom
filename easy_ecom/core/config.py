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
    postgres_pool_timeout_seconds: int = field(
        default_factory=lambda: _to_int(os.getenv("POSTGRES_POOL_TIMEOUT_SECONDS"), 30)
    )
    postgres_pool_recycle_seconds: int = field(
        default_factory=lambda: _to_int(os.getenv("POSTGRES_POOL_RECYCLE_SECONDS"), 1800)
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
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", "").strip())
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini")
    openai_helper_model: str = field(default_factory=lambda: os.getenv("OPENAI_HELPER_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini")
    openai_base_url: str = field(default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip() or "https://api.openai.com/v1")
    openai_timeout_seconds: int = field(default_factory=lambda: _to_int(os.getenv("OPENAI_TIMEOUT_SECONDS"), 20))
    ai_tool_api_secret: str = field(default_factory=lambda: os.getenv("AI_TOOL_API_SECRET", "").strip())
    ai_public_rate_limit_per_minute: int = field(default_factory=lambda: _to_int(os.getenv("AI_PUBLIC_RATE_LIMIT_PER_MINUTE"), 20))
    app_base_url: str = field(default_factory=lambda: os.getenv("APP_BASE_URL", "http://localhost:3000").strip() or "http://localhost:3000")
    stripe_secret_key: str = field(default_factory=lambda: os.getenv("STRIPE_SECRET_KEY", "").strip())
    stripe_webhook_secret: str = field(default_factory=lambda: os.getenv("STRIPE_WEBHOOK_SECRET", "").strip())
    stripe_price_growth_monthly: str = field(default_factory=lambda: os.getenv("STRIPE_PRICE_GROWTH_MONTHLY", "").strip())
    stripe_price_scale_monthly: str = field(default_factory=lambda: os.getenv("STRIPE_PRICE_SCALE_MONTHLY", "").strip())
    stripe_portal_configuration_id: str = field(default_factory=lambda: os.getenv("STRIPE_PORTAL_CONFIGURATION_ID", "").strip())
    stripe_publishable_key: str = field(default_factory=lambda: os.getenv("STRIPE_PUBLISHABLE_KEY", "").strip())
    paypal_env: str = field(default_factory=lambda: os.getenv("PAYPAL_ENV", "sandbox").strip().lower() or "sandbox")
    paypal_client_id: str = field(default_factory=lambda: os.getenv("PAYPAL_CLIENT_ID", "").strip())
    paypal_client_secret: str = field(default_factory=lambda: os.getenv("PAYPAL_CLIENT_SECRET", "").strip())
    paypal_webhook_id: str = field(default_factory=lambda: os.getenv("PAYPAL_WEBHOOK_ID", "").strip())
    paypal_product_growth_id: str = field(default_factory=lambda: os.getenv("PAYPAL_PRODUCT_GROWTH_ID", "").strip())
    paypal_product_scale_id: str = field(default_factory=lambda: os.getenv("PAYPAL_PRODUCT_SCALE_ID", "").strip())
    paypal_plan_growth_monthly: str = field(default_factory=lambda: os.getenv("PAYPAL_PLAN_GROWTH_MONTHLY", "").strip())
    paypal_plan_scale_monthly: str = field(default_factory=lambda: os.getenv("PAYPAL_PLAN_SCALE_MONTHLY", "").strip())
    paypal_price_growth_monthly_amount: str = field(default_factory=lambda: os.getenv("PAYPAL_PRICE_GROWTH_MONTHLY_AMOUNT", "").strip())
    paypal_price_scale_monthly_amount: str = field(default_factory=lambda: os.getenv("PAYPAL_PRICE_SCALE_MONTHLY_AMOUNT", "").strip())
    aws_region: str = field(default_factory=lambda: os.getenv("AWS_REGION", "").strip() or "us-east-1")
    product_media_s3_bucket: str = field(default_factory=lambda: os.getenv("PRODUCT_MEDIA_S3_BUCKET", "").strip())
    product_media_s3_prefix: str = field(default_factory=lambda: os.getenv("PRODUCT_MEDIA_S3_PREFIX", "clients").strip() or "clients")
    product_media_staged_ttl_hours: int = field(
        default_factory=lambda: _to_int(os.getenv("PRODUCT_MEDIA_STAGED_TTL_HOURS"), 24)
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

    @property
    def is_sqlite(self) -> bool:
        return self.postgres_dsn.startswith("sqlite")

    @property
    def should_auto_create_schema(self) -> bool:
        return self.auto_create_schema or self.is_sqlite


settings = Settings()
