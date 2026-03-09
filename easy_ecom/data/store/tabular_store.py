from __future__ import annotations

from typing import Protocol

import pandas as pd


class TabularStore(Protocol):
    def ensure_table(self, table_name: str, columns: list[str]) -> None: ...

    def read(self, table_name: str) -> pd.DataFrame: ...

    def write(self, table_name: str, df: pd.DataFrame) -> None: ...

    def append(self, table_name: str, row: dict[str, str]) -> None: ...
