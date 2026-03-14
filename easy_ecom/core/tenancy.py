from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException

from easy_ecom.core.config import settings


GLOBAL_ROLES = {"SUPER_ADMIN"}


@dataclass(frozen=True)
class TenantContext:
    user_id: str
    client_id: str
    roles: tuple[str, ...]

    @property
    def is_super_admin(self) -> bool:
        return bool(set(self.roles).intersection(GLOBAL_ROLES))


def require_same_client(context: TenantContext, client_id: str) -> None:
    if context.is_super_admin:
        return
    if context.client_id != client_id:
        raise HTTPException(status_code=403, detail="Cross-tenant access is not allowed")


def normalize_client_id(client_id: str | None) -> str:
    if client_id:
        return client_id
    return settings.global_client_id
