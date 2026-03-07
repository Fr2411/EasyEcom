from __future__ import annotations

from typing import Iterable

PAGE_PERMISSIONS: dict[str, set[str]] = {
    "Login": {"SUPER_ADMIN", "CLIENT_OWNER", "CLIENT_MANAGER", "CLIENT_EMPLOYEE", "FINANCE_ONLY"},
    "Dashboard": {"SUPER_ADMIN", "CLIENT_OWNER", "CLIENT_MANAGER", "CLIENT_EMPLOYEE", "FINANCE_ONLY"},
    "Catalog & Stock": {"SUPER_ADMIN", "CLIENT_OWNER", "CLIENT_MANAGER", "CLIENT_EMPLOYEE"},
    "Sales": {"SUPER_ADMIN", "CLIENT_OWNER", "CLIENT_MANAGER", "CLIENT_EMPLOYEE"},
    "Customers": {"SUPER_ADMIN", "CLIENT_OWNER", "CLIENT_MANAGER", "CLIENT_EMPLOYEE"},
    "Finance": {"SUPER_ADMIN", "CLIENT_OWNER", "FINANCE_ONLY"},
    "Returns": {"SUPER_ADMIN", "CLIENT_OWNER", "CLIENT_MANAGER", "CLIENT_EMPLOYEE", "FINANCE_ONLY"},
    "Admin": {"SUPER_ADMIN"},
    "Settings": {"SUPER_ADMIN", "CLIENT_OWNER", "CLIENT_MANAGER", "FINANCE_ONLY", "CLIENT_EMPLOYEE"},
}


def can_access_page(user_roles: Iterable[str], page_name: str) -> bool:
    allowed = PAGE_PERMISSIONS.get(page_name, set())
    return bool(set(user_roles).intersection(allowed))


def can_access_finance(user_roles: Iterable[str]) -> bool:
    return can_access_page(user_roles, "Finance")
