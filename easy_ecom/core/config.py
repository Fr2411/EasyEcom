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


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path(os.getenv("DATA_DIR", "easy_ecom/data_files"))
    app_title: str = os.getenv("APP_TITLE", "Easy_Ecom")
    allow_backorder: bool = _to_bool(os.getenv("ALLOW_BACKORDER"), False)
    super_admin_email: str = os.getenv("SUPER_ADMIN_EMAIL", "")
    super_admin_password: str = os.getenv("SUPER_ADMIN_PASSWORD", "")
    create_default_client: bool = _to_bool(os.getenv("CREATE_DEFAULT_CLIENT"), False)


settings = Settings()
