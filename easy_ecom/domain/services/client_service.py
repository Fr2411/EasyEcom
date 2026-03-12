from __future__ import annotations

from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import now_iso
from easy_ecom.domain.models.client import ClientCreate, ClientUpdate
from easy_ecom.data.repos.csv.clients_repo import ClientsRepo


class ClientService:
    def __init__(self, repo: ClientsRepo):
        self.repo = repo

    def _generate_unique_client_id(self) -> str:
        clients = self.repo.all()
        existing_ids = set(clients.get("client_id", []).astype(str).str.strip()) if not clients.empty else set()
        for _ in range(10):
            candidate = new_uuid()
            if candidate not in existing_ids:
                return candidate
        raise ValueError("Could not generate a unique client ID")

    def create(self, payload: ClientCreate) -> str:
        client_id = self._generate_unique_client_id()
        self.repo.append(
            {
                "client_id": client_id,
                "business_name": payload.business_name,
                "owner_name": payload.owner_name,
                "phone": payload.phone,
                "email": str(payload.email),
                "address": payload.address,
                "currency_code": payload.currency_code.upper(),
                "currency_symbol": payload.currency_symbol,
                "website_url": "",
                "facebook_url": "",
                "instagram_url": "",
                "whatsapp_number": "",
                "created_at": now_iso(),
                "status": "active",
                "notes": "",
            }
        )
        return client_id

    def list_clients(self):
        return self.repo.all()

    def update(self, client_id: str, payload: ClientUpdate) -> None:
        clients = self.repo.all()
        idx = clients[clients["client_id"] == client_id].index
        if len(idx) == 0:
            raise ValueError("Client not found")
        i = idx[0]
        clients.loc[i, "business_name"] = payload.business_name
        clients.loc[i, "owner_name"] = payload.owner_name
        clients.loc[i, "phone"] = payload.phone
        clients.loc[i, "email"] = str(payload.email)
        clients.loc[i, "address"] = payload.address
        clients.loc[i, "currency_code"] = payload.currency_code.upper()
        clients.loc[i, "currency_symbol"] = payload.currency_symbol
        clients.loc[i, "status"] = payload.status
        clients.loc[i, "notes"] = payload.notes
        self.repo.save(clients)

    def get_currency(self, client_id: str) -> tuple[str, str]:
        clients = self.repo.all()
        row = clients[clients["client_id"] == client_id]
        if row.empty:
            return "USD", ""
        code = str(row.iloc[0].get("currency_code", "USD") or "USD").upper()
        symbol = str(row.iloc[0].get("currency_symbol", "") or "")
        return code, symbol
