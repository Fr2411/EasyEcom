from __future__ import annotations

from typing import Iterable

ROLE_PAGE_ACCESS: dict[str, tuple[str, ...]] = {
    "SUPER_ADMIN": (
        "Login",
        "Dashboard",
        "Catalog",
        "Inventory",
        "Purchases",
        "Sales",
        "Customers",
        "Finance",
        "Returns",
        "Reports",
        "Admin",
        "Settings",
    ),
    "CLIENT_OWNER": (
        "Login",
        "Dashboard",
        "Catalog",
        "Inventory",
        "Purchases",
        "Sales",
        "Customers",
        "Finance",
        "Returns",
        "Reports",
        "Settings",
    ),
    "CLIENT_STAFF": (
        "Login",
        "Dashboard",
        "Catalog",
        "Inventory",
        "Purchases",
        "Sales",
        "Customers",
        "Returns",
        "Settings",
    ),
    "FINANCE_STAFF": (
        "Login",
        "Dashboard",
        "Finance",
        "Returns",
        "Reports",
        "Settings",
    ),
}

PAGE_PERMISSIONS: dict[str, set[str]] = {}
for role_code, pages in ROLE_PAGE_ACCESS.items():
    for page in pages:
        PAGE_PERMISSIONS.setdefault(page, set()).add(role_code)

SYSTEM_ROLE_CODES = {"SUPER_ADMIN"}
TENANT_ROLE_CODES = {"CLIENT_OWNER", "CLIENT_STAFF", "FINANCE_STAFF"}
ADMIN_MANAGE_USERS_ROLES = {"SUPER_ADMIN"}


def has_any_role(user_roles: Iterable[str], allowed_roles: set[str]) -> bool:
    return bool(set(user_roles).intersection(allowed_roles))


def can_access_page(user_roles: Iterable[str], page_name: str) -> bool:
    allowed = PAGE_PERMISSIONS.get(page_name, set())
    return bool(set(user_roles).intersection(allowed))


def can_access_finance(user_roles: Iterable[str]) -> bool:
    return can_access_page(user_roles, "Finance")


def pages_for_role(role_code: str) -> tuple[str, ...]:
    return ROLE_PAGE_ACCESS.get(role_code, tuple())
