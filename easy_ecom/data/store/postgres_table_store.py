from __future__ import annotations

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine


class PostgresTableStore:
    def __init__(self, engine: Engine):
        self._engine = engine

    @staticmethod
    def _table_name(table_name: str) -> str:
        return table_name[:-4] if table_name.endswith(".csv") else table_name

    def ensure_table(self, table_name: str, columns: list[str]) -> None:
        pg_table = self._table_name(table_name)
        column_sql = ", ".join(f'"{column}" TEXT' for column in columns)
        with self._engine.begin() as conn:
            conn.execute(text(f'CREATE TABLE IF NOT EXISTS "{pg_table}" ({column_sql})'))

    def read(self, table_name: str) -> pd.DataFrame:
        pg_table = self._table_name(table_name)
        with self._engine.begin() as conn:
            result = conn.execute(text(f'SELECT * FROM "{pg_table}"'))
            rows = result.fetchall()
            if not rows:
                return pd.DataFrame(columns=result.keys())
            return pd.DataFrame(rows, columns=result.keys()).fillna("")

    def write(self, table_name: str, df: pd.DataFrame) -> None:
        pg_table = self._table_name(table_name)
        with self._engine.begin() as conn:
            conn.execute(text(f'TRUNCATE TABLE "{pg_table}"'))
        if not df.empty:
            df.astype(str).to_sql(pg_table, self._engine, if_exists="append", index=False)

    def append(self, table_name: str, row: dict[str, str]) -> None:
        pg_table = self._table_name(table_name)
        pd.DataFrame([row]).astype(str).to_sql(pg_table, self._engine, if_exists="append", index=False)
