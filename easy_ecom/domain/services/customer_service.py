from __future__ import annotations

import pandas as pd

from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import now_iso
from easy_ecom.data.repos.base import TabularRepo


class CustomerService:
    def __init__(self, repo: TabularRepo):
        self.repo = repo

    def list_for_client(self, client_id: str, query: str = "") -> pd.DataFrame:
        df = self.repo.all()
        if df.empty:
            return pd.DataFrame()
        scoped = df[df["client_id"] == client_id].copy()
        if query.strip():
            needle = query.strip().lower()
            mask = (
                scoped["full_name"].astype(str).str.lower().str.contains(needle, na=False)
                | scoped["phone"].astype(str).str.lower().str.contains(needle, na=False)
                | scoped["email"].astype(str).str.lower().str.contains(needle, na=False)
            )
            scoped = scoped[mask]
        return scoped

    def get_for_client(self, client_id: str, customer_id: str) -> dict[str, str] | None:
        scoped = self.list_for_client(client_id=client_id)
        if scoped.empty:
            return None
        found = scoped[scoped["customer_id"] == customer_id]
        if found.empty:
            return None
        return found.iloc[0].to_dict()

    def create(
        self,
        *,
        client_id: str,
        full_name: str,
        phone: str,
        email: str,
        address_line1: str,
        city: str,
        notes: str,
    ) -> dict[str, str]:
        created_at = now_iso()
        row = {
            "customer_id": new_uuid(),
            "client_id": client_id,
            "created_at": created_at,
            "updated_at": created_at,
            "full_name": full_name.strip(),
            "phone": phone.strip(),
            "email": email.strip(),
            "whatsapp": phone.strip(),
            "address_line1": address_line1.strip(),
            "address_line2": "",
            "area": "",
            "city": city.strip(),
            "state": "",
            "postal_code": "",
            "country": "",
            "preferred_contact_channel": "phone",
            "marketing_opt_in": "false",
            "tags": "",
            "notes": notes.strip(),
            "is_active": "true",
        }
        self.repo.append(row)
        return row

    def update_for_client(self, *, client_id: str, customer_id: str, patch: dict[str, str]) -> dict[str, str] | None:
        df = self.repo.all()
        if df.empty:
            return None
        idx = df[(df["client_id"] == client_id) & (df["customer_id"] == customer_id)].index
        if len(idx) == 0:
            return None

        target = idx[0]
        allowed = {"full_name", "phone", "email", "address_line1", "city", "notes"}
        for key, value in patch.items():
            if key in allowed:
                df.loc[target, key] = str(value).strip()
                if key == "phone":
                    df.loc[target, "whatsapp"] = str(value).strip()
        df.loc[target, "updated_at"] = now_iso()
        self.repo.save(df)
        return df.loc[target].to_dict()
