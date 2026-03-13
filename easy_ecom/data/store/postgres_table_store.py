from __future__ import annotations

import pandas as pd
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


class PostgresTableStore:
    def __init__(self, engine: Engine):
        self._engine = engine

    @staticmethod
    def _table_name(table_name: str) -> str:
        return table_name[:-4] if table_name.endswith(".csv") else table_name

    def _existing_columns(self, pg_table: str) -> list[str]:
        inspector = inspect(self._engine)
        if not inspector.has_table(pg_table):
            return []
        return [str(column["name"]) for column in inspector.get_columns(pg_table)]

    def _add_missing_columns(self, pg_table: str, columns: list[str]) -> None:
        existing = set(self._existing_columns(pg_table))
        missing = [column for column in columns if column not in existing]
        if not missing:
            return

        with self._engine.begin() as conn:
            for column in missing:
                if self._engine.dialect.name == "postgresql":
                    conn.execute(
                        text(
                            f'ALTER TABLE "{pg_table}" '
                            f'ADD COLUMN IF NOT EXISTS "{column}" TEXT'
                        )
                    )
                else:
                    conn.execute(text(f'ALTER TABLE "{pg_table}" ADD COLUMN "{column}" TEXT'))

    def ensure_table(self, table_name: str, columns: list[str]) -> None:
        pg_table = self._table_name(table_name)
        column_sql = ", ".join(f'"{column}" TEXT' for column in columns)
        with self._engine.begin() as conn:
            if column_sql:
                conn.execute(text(f'CREATE TABLE IF NOT EXISTS "{pg_table}" ({column_sql})'))
        if columns:
            self._add_missing_columns(pg_table, columns)

    def _normalize_frame(self, table_name: str, df: pd.DataFrame) -> pd.DataFrame:
        pg_table = self._table_name(table_name)
        columns = [str(column) for column in df.columns]
        if columns:
            self.ensure_table(table_name, columns)

        normalized = df.copy()
        for column in self._existing_columns(pg_table):
            if column not in normalized.columns:
                normalized[column] = ""
        return normalized.astype(str)

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
        normalized = self._normalize_frame(table_name, df)
        with self._engine.begin() as conn:
            if self._engine.dialect.name == "sqlite":
                conn.execute(text(f'DELETE FROM "{pg_table}"'))
            else:
                conn.execute(text(f'TRUNCATE TABLE "{pg_table}"'))
        if not normalized.empty:
            normalized.to_sql(pg_table, self._engine, if_exists="append", index=False)

    def append(self, table_name: str, row: dict[str, str]) -> None:
        pg_table = self._table_name(table_name)
        normalized = self._normalize_frame(table_name, pd.DataFrame([row]))
        normalized.to_sql(pg_table, self._engine, if_exists="append", index=False)
