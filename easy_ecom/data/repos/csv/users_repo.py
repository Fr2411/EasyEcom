from __future__ import annotations

from easy_ecom.data.repos.base import BaseRepo


class UsersRepo(BaseRepo):
    table_name = "users.csv"


class UserRolesRepo(BaseRepo):
    table_name = "user_roles.csv"


class RolesRepo(BaseRepo):
    table_name = "roles.csv"
