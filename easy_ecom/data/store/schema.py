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
    "customer_communication",
    "finance",
    "returns",
    "reports",
    "admin",
    "settings",
]

BILLING_PLANS_SEED = [
    {
        "plan_code": "free",
        "display_name": "Free",
        "is_paid": False,
        "billing_provider": "paypal",
        "provider_product_id": None,
        "provider_plan_id": None,
        "currency_code": "USD",
        "interval": "month",
        "sort_order": 1,
        "public_description": "Core commerce workspace for early-stage tenants.",
        "feature_flags_json": {
            "tier": "free",
            "full_access": False,
        },
    },
    {
        "plan_code": "growth",
        "display_name": "Growth",
        "is_paid": True,
        "billing_provider": "paypal",
        "provider_product_id": None,
        "provider_plan_id": None,
        "currency_code": "USD",
        "interval": "month",
        "sort_order": 2,
        "public_description": "Full operating stack for growing businesses.",
        "feature_flags_json": {
            "tier": "growth",
            "full_access": True,
        },
    },
    {
        "plan_code": "scale",
        "display_name": "Scale",
        "is_paid": True,
        "billing_provider": "paypal",
        "provider_product_id": None,
        "provider_plan_id": None,
        "currency_code": "USD",
        "interval": "month",
        "sort_order": 3,
        "public_description": "Advanced commercial plan for larger operators.",
        "feature_flags_json": {
            "tier": "scale",
            "full_access": True,
        },
    },
]
