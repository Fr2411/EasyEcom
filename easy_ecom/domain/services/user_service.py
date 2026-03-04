from __future__ import annotations

from easy_ecom.core.ids import new_uuid
from easy_ecom.core.security import hash_password, verify_password
from easy_ecom.core.time_utils import now_iso
from easy_ecom.domain.models.user import UserCreate
from easy_ecom.data.repos.csv.users_repo import RolesRepo, UserRolesRepo, UsersRepo


class UserService:
    def __init__(self, users: UsersRepo, roles: RolesRepo, user_roles: UserRolesRepo):
        self.users = users
        self.roles = roles
        self.user_roles = user_roles

    def create(self, payload: UserCreate) -> str:
        user_id = new_uuid()
        self.users.append(
            {
                "user_id": user_id,
                "client_id": payload.client_id,
                "name": payload.name,
                "email": str(payload.email).lower(),
                "password_hash": hash_password(payload.password),
                "is_active": "true",
                "created_at": now_iso(),
            }
        )
        self.user_roles.append({"user_id": user_id, "role_code": payload.role_code})
        return user_id

    def login(self, email: str, password: str) -> dict[str, str] | None:
        users = self.users.all()
        matches = users[users["email"].str.lower() == email.lower()]
        if matches.empty:
            return None
        user = matches.iloc[0].to_dict()
        if not verify_password(password, user["password_hash"]):
            return None
        roles_df = self.user_roles.all()
        roles = roles_df[roles_df["user_id"] == user["user_id"]]["role_code"].tolist()
        return {"user_id": user["user_id"], "client_id": user["client_id"], "roles": ",".join(roles), "name": user["name"]}
