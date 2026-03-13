from __future__ import annotations

TABLE_SCHEMAS: dict[str, list[str]] = {
    "clients.csv": [
        "client_id",
        "business_name",
        "owner_name",
        "phone",
        "email",
        "address",
        "currency_code",
        "currency_symbol",
        "website_url",
        "facebook_url",
        "instagram_url",
        "whatsapp_number",
        "created_at",
        "status",
        "notes",
    ],
    "users.csv": [
        "user_id",
        "client_id",
        "name",
        "email",
        "password",
        "password_hash",
        "is_active",
        "created_at",
    ],
    "roles.csv": ["role_code", "role_name", "description"],
    "user_roles.csv": ["user_id", "role_code"],
}

ROLES_SEED = [
    {"role_code": "SUPER_ADMIN", "role_name": "Super Admin", "description": "Global system administrator"},
    {"role_code": "CLIENT_OWNER", "role_name": "Client Owner", "description": "Full client access"},
    {"role_code": "CLIENT_MANAGER", "role_name": "Client Manager", "description": "Operations management"},
    {"role_code": "CLIENT_EMPLOYEE", "role_name": "Client Employee", "description": "Operational access"},
    {"role_code": "FINANCE_ONLY", "role_name": "Finance Only", "description": "Finance team access"},
]
