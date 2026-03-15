from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    client_id: str
    name: str
    email: str
    business_name: str | None
    roles: list[str]
    allowed_pages: list[str]

    @property
    def roles_csv(self) -> str:
        return ",".join(self.roles)
