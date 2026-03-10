from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from easy_ecom.api.dependencies import RequestUser, get_container, get_current_user
from easy_ecom.api.main import app, create_app


@dataclass
class DummyAdminUser:
    user_id: str
    client_id: str
    name: str
    email: str
    is_active: bool
    created_at: str
    roles: list[str]


class DummyAdminService:
    def __init__(self) -> None:
        self.users = [
            DummyAdminUser(
                user_id="u-a",
                client_id="tenant-a",
                name="Alice",
                email="alice@tenant-a.com",
                is_active=True,
                created_at="2026-03-10T00:00:00Z",
                roles=["CLIENT_OWNER"],
            ),
            DummyAdminUser(
                user_id="u-b",
                client_id="tenant-b",
                name="Bob",
                email="bob@tenant-b.com",
                is_active=True,
                created_at="2026-03-10T00:00:00Z",
                roles=["CLIENT_OWNER"],
            ),
        ]

    def list_users_for_client(self, client_id: str):
        return [item for item in self.users if item.client_id == client_id]

    def get_user_for_client(self, client_id: str, user_id: str):
        for item in self.users:
            if item.client_id == client_id and item.user_id == user_id:
                return item
        return None

    def create_user(
        self,
        *,
        client_id: str,
        name: str,
        email: str,
        password: str,
        role_codes: list[str],
        is_active: bool,
    ):
        if any(item.email.lower() == email.lower() for item in self.users):
            raise ValueError("Email already in use")
        user = DummyAdminUser(
            user_id=f"u-{len(self.users)+1}",
            client_id=client_id,
            name=name,
            email=email.lower(),
            is_active=is_active,
            created_at="2026-03-10T00:00:00Z",
            roles=role_codes,
        )
        self.users.append(user)
        return user

    def update_user_profile(
        self,
        *,
        client_id: str,
        user_id: str,
        name: str | None,
        email: str | None,
        is_active: bool | None,
    ):
        user = self.get_user_for_client(client_id, user_id)
        if not user:
            return None
        if email and any(
            item.email.lower() == email.lower() and item.user_id != user_id for item in self.users
        ):
            raise ValueError("Email already in use")
        if name is not None:
            user.name = name
        if email is not None:
            user.email = email.lower()
        if is_active is not None:
            user.is_active = is_active
        return user

    def set_user_roles(self, *, client_id: str, user_id: str, role_codes: list[str]):
        user = self.get_user_for_client(client_id, user_id)
        if not user:
            return None
        user.roles = role_codes
        return user


class DummyContainer:
    def __init__(self) -> None:
        self.admin = DummyAdminService()


def test_admin_requires_auth() -> None:
    client = TestClient(create_app())
    assert client.get("/admin/users").status_code == 401


def test_admin_non_admin_forbidden() -> None:
    container = DummyContainer()
    app.dependency_overrides[get_container] = lambda: container
    app.dependency_overrides[get_current_user] = lambda: RequestUser(
        user_id="u-x", client_id="tenant-a", roles=["CLIENT_EMPLOYEE"]
    )
    client = TestClient(app)

    assert client.get("/admin/users").status_code == 403
    app.dependency_overrides.clear()


def test_admin_users_crud_roles_and_tenant_isolation() -> None:
    container = DummyContainer()
    app.dependency_overrides[get_container] = lambda: container
    app.dependency_overrides[get_current_user] = lambda: RequestUser(
        user_id="u-a", client_id="tenant-a", roles=["CLIENT_OWNER"]
    )
    client = TestClient(app)

    list_res = client.get("/admin/users")
    assert list_res.status_code == 200
    assert len(list_res.json()["items"]) == 1

    create_res = client.post(
        "/admin/users",
        json={
            "name": "Nina",
            "email": "nina@tenant-a.com",
            "password": "Password!1",
            "role_codes": ["CLIENT_MANAGER"],
            "is_active": True,
        },
    )
    assert create_res.status_code == 201

    dup_res = client.post(
        "/admin/users",
        json={
            "name": "Nina",
            "email": "nina@tenant-a.com",
            "password": "Password!1",
            "role_codes": ["CLIENT_MANAGER"],
            "is_active": True,
        },
    )
    assert dup_res.status_code == 409

    update_res = client.patch("/admin/users/u-3", json={"name": "Nina Updated", "is_active": False})
    assert update_res.status_code == 200
    assert update_res.json()["user"]["is_active"] is False

    roles_res = client.patch("/admin/users/u-3/roles", json={"role_codes": ["FINANCE_ONLY"]})
    assert roles_res.status_code == 200
    assert roles_res.json()["user"]["roles"] == ["FINANCE_ONLY"]

    cross_tenant_get = client.get("/admin/users/u-b")
    assert cross_tenant_get.status_code == 404

    audit_res = client.get("/admin/audit")
    assert audit_res.status_code == 200
    assert audit_res.json()["supported"] is False

    app.dependency_overrides.clear()


def test_only_super_admin_can_assign_super_admin() -> None:
    container = DummyContainer()
    app.dependency_overrides[get_container] = lambda: container
    app.dependency_overrides[get_current_user] = lambda: RequestUser(
        user_id="u-a", client_id="tenant-a", roles=["CLIENT_OWNER"]
    )
    client = TestClient(app)

    forbidden = client.patch("/admin/users/u-a/roles", json={"role_codes": ["SUPER_ADMIN"]})
    assert forbidden.status_code == 403

    app.dependency_overrides.clear()
