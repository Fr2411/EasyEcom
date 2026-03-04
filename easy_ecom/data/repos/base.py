from __future__ import annotations

import pandas as pd

from easy_ecom.data.store.csv_store import CsvStore


class BaseRepo:
    table_name: str

    def __init__(self, store: CsvStore):
        self.store = store

    def all(self) -> pd.DataFrame:
        return self.store.read(self.table_name)

    def append(self, row: dict[str, str]) -> None:
        self.store.append(self.table_name, row)

    def save(self, df: pd.DataFrame) -> None:
        self.store.write(self.table_name, df)
