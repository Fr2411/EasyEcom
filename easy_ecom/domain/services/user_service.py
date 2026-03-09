from __future__ import annotations

from easy_ecom.core.config import settings
from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import now_iso
from easy_ecom.core.security import hash_password
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
                "password": "",
                "password_hash": hash_password(payload.password),
                "is_active": "true",
                "created_at": now_iso(),
            }
        )
        self.user_roles.append({"user_id": user_id, "role_code": payload.role_code})
        return user_id

    def _env_super_admin_login(self, email: str, password: str) -> dict[str, str] | None:
        admin_email = settings.super_admin_email.strip().lower()
        admin_password = settings.super_admin_password
        if not admin_email or not admin_password:
            return None
        if email.lower() != admin_email or password != admin_password:
            return None
        return {
            "user_id": "ENV_SUPER_ADMIN",
            "client_id": "GLOBAL",
            "roles": "SUPER_ADMIN",
            "name": "Super Admin",
            "email": admin_email,
        }

    def login(self, email: str, password: str) -> dict[str, str] | None:
        env_admin = self._env_super_admin_login(email, password)
        if env_admin:
            return env_admin

        return None

    def list_users(self, client_id: str):
        users = self.users.all()
        if users.empty:
            return users
        scoped = users[users["client_id"] == client_id].copy()
        roles = self.user_roles.all()
        scoped["roles"] = scoped["user_id"].apply(lambda uid: ",".join(roles[roles["user_id"] == uid]["role_code"].tolist()))
        return scoped

    def update_user(self, client_id: str, user_id: str, name: str, email: str, password: str, is_active: bool, role_codes: list[str]) -> None:
        users = self.users.all()
        idx = users[(users["client_id"] == client_id) & (users["user_id"] == user_id)].index
        if len(idx) == 0:
            raise ValueError("User not found for this client")
        i = idx[0]
        users.loc[i, "name"] = name
        users.loc[i, "email"] = email.lower()
        users.loc[i, "password"] = ""
        if "password_hash" not in users.columns:
            users["password_hash"] = ""
        users.loc[i, "password_hash"] = hash_password(password)
        users.loc[i, "is_active"] = "true" if is_active else "false"
        self.users.save(users)

        user_roles = self.user_roles.all()
        user_roles = user_roles[user_roles["user_id"] != user_id].copy()
        for role in role_codes:
            user_roles.loc[len(user_roles)] = {"user_id": user_id, "role_code": role}
        self.user_roles.save(user_roles)
