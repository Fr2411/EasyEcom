from __future__ import annotations

from easy_ecom.data.repos.csv.users_repo import UserRolesRepo, UsersRepo
from easy_ecom.domain.services.auth_service import AuthUserRecord


class CsvAuthRepo:
    def __init__(self, users: UsersRepo, user_roles: UserRolesRepo):
        self.users = users
        self.user_roles = user_roles

    def get_user_by_email(self, email: str) -> AuthUserRecord | None:
        users = self.users.all()
        if users.empty:
            return None
        if "password_hash" not in users.columns:
            users["password_hash"] = ""
            self.users.save(users)
        matches = users[users["email"].str.lower() == email.lower()]
        if matches.empty:
            return None
        row = matches.iloc[0]
        return AuthUserRecord(
            user_id=str(row.get("user_id", "")),
            client_id=str(row.get("client_id", "")),
            name=str(row.get("name", "")),
            email=str(row.get("email", "")),
            password=str(row.get("password", "")),
            password_hash=str(row.get("password_hash", "")),
            is_active=str(row.get("is_active", "")).strip().lower() == "true",
        )

    def get_roles_for_user(self, user_id: str) -> list[str]:
        roles = self.user_roles.all()
        if roles.empty:
            return []
        return roles[roles["user_id"] == user_id]["role_code"].astype(str).tolist()

    def update_password_hash(self, user_id: str, password_hash: str) -> None:
        users = self.users.all()
        idx = users[users["user_id"] == user_id].index
        if len(idx) == 0:
            return
        i = idx[0]
        if "password_hash" not in users.columns:
            users["password_hash"] = ""
        users.loc[i, "password_hash"] = password_hash
        users.loc[i, "password"] = ""
        self.users.save(users)
