from __future__ import annotations

ROLES_SEED = [
    {"role_code": "SUPER_ADMIN", "role_name": "Super Admin", "description": "Global system administrator"},
    {"role_code": "CLIENT_OWNER", "role_name": "Client Owner", "description": "Full client access"},
    {"role_code": "CLIENT_STAFF", "role_name": "Client Staff", "description": "Operations access across core workflows"},
    {"role_code": "FINANCE_STAFF", "role_name": "Finance Staff", "description": "Finance and reporting access"},
]

CORE_MODULES = [
    "home",
    "dashboard",
    "catalog",
    "inventory",
    "purchases",
    "sales",
    "customers",
    "finance",
    "returns",
    "reports",
    "admin",
    "settings",
]
