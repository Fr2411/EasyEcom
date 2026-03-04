from __future__ import annotations

from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import now_iso
from easy_ecom.domain.models.client import ClientCreate
from easy_ecom.data.repos.csv.clients_repo import ClientsRepo


class ClientService:
    def __init__(self, repo: ClientsRepo):
        self.repo = repo

    def create(self, payload: ClientCreate) -> str:
        client_id = new_uuid()
        self.repo.append(
            {
                "client_id": client_id,
                "business_name": payload.business_name,
                "owner_name": payload.owner_name,
                "phone": payload.phone,
                "email": str(payload.email),
                "address": payload.address,
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
