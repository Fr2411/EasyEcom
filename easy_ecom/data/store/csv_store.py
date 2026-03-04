from __future__ import annotations

from pathlib import Path
import pandas as pd
from filelock import FileLock


class CsvStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def file_path(self, table_name: str) -> Path:
        return self.data_dir / table_name

    def _lock_path(self, table_name: str) -> str:
        return str(self.file_path(table_name)) + ".lock"

    def ensure_table(self, table_name: str, columns: list[str]) -> None:
        path = self.file_path(table_name)
        if not path.exists():
            pd.DataFrame(columns=columns).to_csv(path, index=False)

    def read(self, table_name: str) -> pd.DataFrame:
        path = self.file_path(table_name)
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path, dtype=str).fillna("")

    def write(self, table_name: str, df: pd.DataFrame) -> None:
        with FileLock(self._lock_path(table_name)):
            df.to_csv(self.file_path(table_name), index=False)

    def append(self, table_name: str, row: dict[str, str]) -> None:
        with FileLock(self._lock_path(table_name)):
            df = self.read(table_name)
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
            df.to_csv(self.file_path(table_name), index=False)
