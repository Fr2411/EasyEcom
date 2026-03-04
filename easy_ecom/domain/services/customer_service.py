from __future__ import annotations

from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import now_iso
from easy_ecom.domain.models.customer import CustomerCreate
from easy_ecom.data.repos.csv.customers_repo import CustomersRepo


class CustomerService:
    def __init__(self, repo: CustomersRepo):
        self.repo = repo

    def create(self, payload: CustomerCreate) -> str:
        customer_id = new_uuid()
        self.repo.append(
            {
                "customer_id": customer_id,
                "client_id": payload.client_id,
                "created_at": now_iso(),
                "full_name": payload.full_name,
                "phone": payload.phone,
                "email": payload.email,
                "whatsapp": payload.phone,
                "address_line1": payload.address_line1,
                "address_line2": "",
                "area": "",
                "city": payload.city,
                "state": "",
                "postal_code": "",
                "country": payload.country,
                "preferred_contact_channel": "phone",
                "marketing_opt_in": "false",
                "tags": "",
                "notes": "",
                "is_active": "true",
            }
        )
        return customer_id
