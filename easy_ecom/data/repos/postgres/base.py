from __future__ import annotations

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker


class PostgresRepo:
    model: type
    columns: list[str]

    def __init__(self, session_factory: sessionmaker[Session]):
        self.session_factory = session_factory

    def all(self) -> pd.DataFrame:
        with self.session_factory() as session:
            rows = session.execute(select(self.model)).scalars().all()
        if not rows:
            return pd.DataFrame(columns=self.columns)
        records = [
            {
                col: "" if getattr(row, col) is None else str(getattr(row, col))
                for col in self.columns
            }
            for row in rows
        ]
        return pd.DataFrame(records, columns=self.columns)

    def append(self, row: dict[str, str]) -> None:
        payload = {col: str(row.get(col, "")) for col in self.columns}
        with self.session_factory() as session:
            session.add(self.model(**payload))
            session.commit()

    def save(self, df: pd.DataFrame) -> None:
        records = []
        for record in df.fillna("").to_dict(orient="records"):
            records.append({col: str(record.get(col, "")) for col in self.columns})
        with self.session_factory() as session:
            session.execute(delete(self.model))
            if records:
                session.bulk_insert_mappings(self.model, records)
            session.commit()
