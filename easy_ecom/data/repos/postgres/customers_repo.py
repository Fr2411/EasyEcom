from __future__ import annotations

import pandas as pd

from easy_ecom.data.repos.postgres.base import PostgresRepo
from easy_ecom.data.store.postgres_models import CustomerModel


class CustomersPostgresRepo(PostgresRepo):
    model = CustomerModel
    columns = [
        "customer_id",
        "client_id",
        "created_at",
        "updated_at",
        "full_name",
        "phone",
        "email",
        "whatsapp",
        "address_line1",
        "address_line2",
        "area",
        "city",
        "state",
        "postal_code",
        "country",
        "preferred_contact_channel",
        "marketing_opt_in",
        "tags",
        "notes",
        "is_active",
    ]

    def get_by_id(self, client_id: str, customer_id: str) -> dict[str, str] | None:
        df = self.all()
        if df.empty:
            return None
        scoped = df[(df["client_id"] == client_id) & (df["customer_id"] == customer_id)]
        if scoped.empty:
            return None
        return scoped.iloc[0].to_dict()

    def list_for_client(self, client_id: str, query: str = "") -> pd.DataFrame:
        df = self.all()
        if df.empty:
            return pd.DataFrame(columns=self.columns)
        scoped = df[df["client_id"] == client_id].copy()
        if query.strip():
            needle = query.strip().lower()
            mask = (
                scoped["full_name"].astype(str).str.lower().str.contains(needle, na=False)
                | scoped["phone"].astype(str).str.lower().str.contains(needle, na=False)
                | scoped["email"].astype(str).str.lower().str.contains(needle, na=False)
            )
            scoped = scoped[mask]
        return scoped.copy()

    def update_for_client(self, client_id: str, customer_id: str, patch: dict[str, str]) -> bool:
        df = self.all()
        if df.empty:
            return False
        idx = df[(df["client_id"] == client_id) & (df["customer_id"] == customer_id)].index
        if len(idx) == 0:
            return False
        target = idx[0]
        for key, value in patch.items():
            if key in df.columns:
                df.loc[target, key] = value
        self.save(df)
        return True
