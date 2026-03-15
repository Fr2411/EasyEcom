from __future__ import annotations

from typing import Iterable

PAGE_CODE_TO_NAME: dict[str, str] = {
    "DASHBOARD": "Dashboard",
    "CATALOG": "Catalog",
    "INVENTORY": "Inventory",
    "PURCHASES": "Purchases",
    "SALES": "Sales",
    "CUSTOMERS": "Customers",
    "FINANCE": "Finance",
    "RETURNS": "Returns",
    "REPORTS": "Reports",
    "SALES_AGENT": "Sales Agent",
    "SETTINGS": "Settings",
}
PAGE_NAME_TO_CODE = {name: code for code, name in PAGE_CODE_TO_NAME.items()}
OVERRIDABLE_PAGE_CODES: tuple[str, ...] = tuple(PAGE_CODE_TO_NAME.keys())
ALL_PAGE_NAMES: tuple[str, ...] = (
    "Home",
    "Dashboard",
    "Catalog",
    "Inventory",
    "Purchases",
    "Sales",
    "Customers",
    "Finance",
    "Returns",
    "Reports",
    "Sales Agent",
    "Admin",
    "Settings",
)

ROLE_PAGE_ACCESS: dict[str, tuple[str, ...]] = {
    "SUPER_ADMIN": ALL_PAGE_NAMES,
    "CLIENT_OWNER": (
        "Home",
        "Dashboard",
        "Catalog",
        "Inventory",
        "Purchases",
        "Sales",
        "Sales Agent",
        "Finance",
        "Returns",
        "Reports",
        "Settings",
    ),
    "CLIENT_STAFF": (
        "Home",
        "Dashboard",
        "Catalog",
        "Inventory",
        "Purchases",
        "Sales",
        "Sales Agent",
        "Returns",
        "Settings",
    ),
    "FINANCE_STAFF": (
        "Home",
        "Dashboard",
        "Finance",
        "Returns",
        "Reports",
        "Settings",
    ),
}

MANDATORY_ROLE_PAGE_ACCESS: dict[str, tuple[str, ...]] = {
    "CLIENT_OWNER": ("Sales Agent",),
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


def pages_for_role(role_code: str) -> tuple[str, ...]:
    return ROLE_PAGE_ACCESS.get(role_code, tuple())


def default_page_names_for_roles(user_roles: Iterable[str]) -> tuple[str, ...]:
    allowed = {page for role in user_roles for page in pages_for_role(role)}
    return tuple(page for page in ALL_PAGE_NAMES if page in allowed)


def mandatory_page_names_for_roles(user_roles: Iterable[str]) -> tuple[str, ...]:
    required = {page for role in user_roles for page in MANDATORY_ROLE_PAGE_ACCESS.get(role, ())}
    return tuple(page for page in ALL_PAGE_NAMES if page in required)


def default_page_codes_for_roles(user_roles: Iterable[str]) -> tuple[str, ...]:
    names = set(default_page_names_for_roles(user_roles))
    return tuple(code for code, name in PAGE_CODE_TO_NAME.items() if name in names)


def page_names_from_codes(page_codes: Iterable[str]) -> tuple[str, ...]:
    normalized = {str(code).strip().upper() for code in page_codes if str(code).strip()}
    return tuple(PAGE_CODE_TO_NAME[code] for code in OVERRIDABLE_PAGE_CODES if code in normalized)


def effective_page_names(
    user_roles: Iterable[str],
    granted_page_codes: Iterable[str] = (),
    revoked_page_codes: Iterable[str] = (),
) -> tuple[str, ...]:
    allowed = set(default_page_names_for_roles(user_roles))
    allowed.update(page_names_from_codes(granted_page_codes))
    allowed.difference_update(page_names_from_codes(revoked_page_codes))
    allowed.update(mandatory_page_names_for_roles(user_roles))
    return tuple(page for page in ALL_PAGE_NAMES if page in allowed)


def can_access_page(user_roles: Iterable[str], page_name: str, allowed_pages: Iterable[str] | None = None) -> bool:
    if allowed_pages is not None:
        return page_name in {str(page).strip() for page in allowed_pages if str(page).strip()}
    allowed = PAGE_PERMISSIONS.get(page_name, set())
    return bool(set(user_roles).intersection(allowed))


def can_access_finance(user_roles: Iterable[str], allowed_pages: Iterable[str] | None = None) -> bool:
    return can_access_page(user_roles, "Finance", allowed_pages=allowed_pages)
