from __future__ import annotations

from datetime import datetime
from pathlib import Path
from shutil import copy2

import pandas as pd

from easy_ecom.data.store.schema import TABLE_SCHEMAS

HIGH_RISK_FILES = {
    "users.csv",
    "roles.csv",
    "user_roles.csv",
    "sequences.csv",
    "ledger.csv",
    "inventory_txn.csv",
    "sales_orders.csv",
    "sales_order_items.csv",
}


def list_csv_files(data_dir: Path) -> list[str]:
    """Return sorted list of CSV filenames inside data_dir."""
    if not data_dir.exists() or not data_dir.is_dir():
        return []
    return sorted(path.name for path in data_dir.iterdir() if path.is_file() and path.suffix.lower() == ".csv")


def load_csv_safely(file_path: Path) -> pd.DataFrame:
    """Load CSV file to DataFrame and surface readable errors to caller."""
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {file_path.name}")

    try:
        return pd.read_csv(file_path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=TABLE_SCHEMAS.get(file_path.name, []))
    except Exception as exc:  # pragma: no cover - defensive error pass-through
        raise RuntimeError(f"Unable to read {file_path.name}: {exc}") from exc


def validate_required_columns(df: pd.DataFrame, filename: str) -> tuple[bool, list[str]]:
    """Validate file-level required columns using schema contract."""
    required_columns = TABLE_SCHEMAS.get(filename, [])
    missing = [column for column in required_columns if column not in df.columns]
    return len(missing) == 0, missing


def backup_file_before_save(file_path: Path) -> Path:
    """Create a timestamped backup copy in data_files/backups before overwrite."""
    backup_dir = file_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{file_path.stem}_{timestamp}.bak.csv"
    backup_path = backup_dir / backup_name
    copy2(file_path, backup_path)
    return backup_path


def save_csv_safely(df: pd.DataFrame, file_path: Path) -> tuple[bool, str]:
    """Validate schema, backup original CSV, then overwrite with edited DataFrame."""
    is_valid, missing_columns = validate_required_columns(df, file_path.name)
    if not is_valid:
        return False, f"Missing required columns: {', '.join(missing_columns)}"

    try:
        backup_path = backup_file_before_save(file_path)
        df.to_csv(file_path, index=False)
        return True, f"Saved successfully. Backup created at: {backup_path}"
    except Exception as exc:  # pragma: no cover - defensive save guard
        return False, f"Save failed: {exc}"
