from __future__ import annotations

ROLES_SEED = [
    {"role_code": "SUPER_ADMIN", "role_name": "Super Admin", "description": "Global system administrator"},
    {"role_code": "CLIENT_OWNER", "role_name": "Client Owner", "description": "Full client access"},
    {"role_code": "CLIENT_MANAGER", "role_name": "Client Manager", "description": "Operations management"},
    {"role_code": "CLIENT_EMPLOYEE", "role_name": "Client Employee", "description": "Operational access"},
    {"role_code": "FINANCE_ONLY", "role_name": "Finance Only", "description": "Finance team access"},
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
