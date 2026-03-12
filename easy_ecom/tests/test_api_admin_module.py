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


@dataclass
class DummyTenantRecord:
    client_id: str
    business_name: str
    owner_user: DummyAdminUser


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


    def create_tenant_with_owner(
        self,
        *,
        business_name: str,
        owner_name: str,
        owner_email: str,
        owner_password: str,
        currency_code: str,
        owner_role_codes: list[str],
    ) -> DummyTenantRecord:
        client_id = f"tenant-{len({item.client_id for item in self.users}) + 1}"
        owner = self.create_user(
            client_id=client_id,
            name=owner_name,
            email=owner_email,
            password=owner_password,
            role_codes=owner_role_codes,
            is_active=True,
        )
        return DummyTenantRecord(client_id=client_id, business_name=business_name, owner_user=owner)

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


def test_super_admin_can_create_tenant_and_target_tenant_user() -> None:
    container = DummyContainer()
    app.dependency_overrides[get_container] = lambda: container
    app.dependency_overrides[get_current_user] = lambda: RequestUser(
        user_id="u-super", client_id="tenant-a", roles=["SUPER_ADMIN"]
    )
    client = TestClient(app)

    tenant_res = client.post(
        "/admin/tenants",
        json={
            "business_name": "New Biz",
            "owner_name": "Owner",
            "owner_email": "owner@newbiz.com",
            "owner_password": "Password!1",
            "currency_code": "USD",
        },
    )
    assert tenant_res.status_code == 201
    created_client_id = tenant_res.json()["client_id"]

    user_res = client.post(
        "/admin/users",
        json={
            "client_id": created_client_id,
            "name": "Emp",
            "email": "emp@newbiz.com",
            "password": "Password!1",
            "role_codes": ["CLIENT_EMPLOYEE"],
            "is_active": True,
        },
    )
    assert user_res.status_code == 201
    assert user_res.json()["user"]["client_id"] == created_client_id

    app.dependency_overrides.clear()


def test_non_super_admin_cannot_create_tenant_or_cross_tenant_user() -> None:
    container = DummyContainer()
    app.dependency_overrides[get_container] = lambda: container
    app.dependency_overrides[get_current_user] = lambda: RequestUser(
        user_id="u-a", client_id="tenant-a", roles=["CLIENT_OWNER"]
    )
    client = TestClient(app)

    tenant_res = client.post(
        "/admin/tenants",
        json={
            "business_name": "Nope",
            "owner_name": "Owner",
            "owner_email": "owner@nope.com",
            "owner_password": "Password!1",
            "currency_code": "USD",
        },
    )
    assert tenant_res.status_code == 403

    user_res = client.post(
        "/admin/users",
        json={
            "client_id": "tenant-b",
            "name": "Emp",
            "email": "emp@tenant-a.com",
            "password": "Password!1",
            "role_codes": ["CLIENT_EMPLOYEE"],
            "is_active": True,
        },
    )
    assert user_res.status_code == 403

    app.dependency_overrides.clear()
