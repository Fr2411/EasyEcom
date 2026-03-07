from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv()


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _to_csv(value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if not value:
        return default
    parsed = [item.strip() for item in value.split(",") if item.strip()]
    return tuple(parsed) or default


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path(os.getenv("DATA_DIR", "easy_ecom/data_files"))
    app_title: str = os.getenv("APP_TITLE", "Easy_Ecom")
    allow_backorder: bool = _to_bool(os.getenv("ALLOW_BACKORDER"), False)
    super_admin_email: str = os.getenv("SUPER_ADMIN_EMAIL", "")
    super_admin_password: str = os.getenv("SUPER_ADMIN_PASSWORD", "")
    create_default_client: bool = _to_bool(os.getenv("CREATE_DEFAULT_CLIENT"), False)
    cors_allow_origins: tuple[str, ...] = _to_csv(
        os.getenv("CORS_ALLOW_ORIGINS"),
        ("http://localhost:3000", "http://127.0.0.1:3000"),
    )


settings = Settings()
