from __future__ import annotations

import pandas as pd

from easy_ecom.data.repos.base import BaseRepo


class CustomersRepo(BaseRepo):
    table_name = "customers.csv"

    def find_by_name(self, client_id: str, name: str) -> pd.DataFrame:
        df = self.all()
        if df.empty:
            return pd.DataFrame(columns=["customer_id", "full_name", "phone", "email", "address_line1"])
        normalized = name.strip().lower()
        if not normalized:
            return pd.DataFrame(columns=df.columns)
        scoped = df[df["client_id"] == client_id].copy()
        return scoped[scoped["full_name"].astype(str).str.strip().str.lower() == normalized].copy()

    def create(self, customer: dict[str, str]) -> None:
        self.append(customer)

    def update(self, customer_id: str, patch: dict[str, str]) -> bool:
        df = self.all()
        if df.empty:
            return False
        idx = df[df["customer_id"] == customer_id].index
        if len(idx) == 0:
            return False
        i = idx[0]
        for key, value in patch.items():
            if key in df.columns:
                df.loc[i, key] = value
        self.save(df)
        return True
