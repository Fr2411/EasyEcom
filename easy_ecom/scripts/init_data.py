from __future__ import annotations

from easy_ecom.core.config import settings
from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import now_iso
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.store.schema import ROLES_SEED, TABLE_SCHEMAS


def main() -> None:
    store = CsvStore(settings.data_dir)
    for table, cols in TABLE_SCHEMAS.items():
        store.ensure_table(table, cols)

    roles = store.read("roles.csv")
    if roles.empty:
        for role in ROLES_SEED:
            store.append("roles.csv", role)

    users = store.read("users.csv")
    admin_email = settings.super_admin_email.strip().lower()
    admin_password = settings.super_admin_password
    if admin_email and admin_password and users[users["email"].str.lower() == admin_email].empty:
        admin_id = new_uuid()
        store.append(
            "users.csv",
            {
                "user_id": admin_id,
                "client_id": "GLOBAL",
                "name": "Super Admin",
                "email": admin_email,
                "password": admin_password,
                "is_active": "true",
                "created_at": now_iso(),
            },
        )
        store.append("user_roles.csv", {"user_id": admin_id, "role_code": "SUPER_ADMIN"})

    if settings.create_default_client:
        clients = store.read("clients.csv")
        if clients.empty:
            store.append(
                "clients.csv",
                {
                    "client_id": new_uuid(),
                    "business_name": "Default Client",
                    "owner_name": "Owner",
                    "phone": "",
                    "email": "owner@example.com",
                    "address": "",
                    "currency_code": "USD",
                    "currency_symbol": "$",
                    "website_url": "",
                    "facebook_url": "",
                    "instagram_url": "",
                    "whatsapp_number": "",
                    "created_at": now_iso(),
                    "status": "active",
                    "notes": "",
                },
            )


if __name__ == "__main__":
    main()
