from pathlib import Path

from fastapi.testclient import TestClient

from easy_ecom.api import dependencies as deps
from easy_ecom.api.main import create_app
from easy_ecom.core.security import hash_password, verify_password
from easy_ecom.tests.support.sqlite_runtime import build_sqlite_runtime, seed_auth_user

SUPER_ADMIN_ID = "11111111-1111-1111-1111-111111111111"
SUPER_ADMIN_CLIENT_ID = "22222222-2222-2222-2222-222222222222"


def _setup_runtime(tmp_path: Path):
    return build_sqlite_runtime(tmp_path, "api_admin.db")


def _login_super_admin(runtime, monkeypatch) -> TestClient:
    monkeypatch.setattr(deps, "settings", runtime.settings)
    seed_auth_user(
        runtime.session_factory,
        user_id=SUPER_ADMIN_ID,
        client_id=SUPER_ADMIN_CLIENT_ID,
        name="Super Admin",
        email="admin@example.com",
        password_hash=hash_password("secret"),
        role_code="SUPER_ADMIN",
    )
    client = TestClient(create_app())
    response = client.post("/auth/login", json={"email": "admin@example.com", "password": "secret"})
    assert response.status_code == 200
    return client


def test_admin_routes_require_super_admin(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path)
    monkeypatch.setattr(deps, "settings", runtime.settings)
    seed_auth_user(
        runtime.session_factory,
        user_id="33333333-3333-3333-3333-333333333333",
        client_id=SUPER_ADMIN_CLIENT_ID,
        name="Staff User",
        email="staff@example.com",
        password_hash=hash_password("secret"),
        role_code="CLIENT_STAFF",
    )

    client = TestClient(create_app())
    login = client.post("/auth/login", json={"email": "staff@example.com", "password": "secret"})
    assert login.status_code == 200

    response = client.get("/admin/clients")
    assert response.status_code == 403

    access_response = client.get("/admin/users/33333333-3333-3333-3333-333333333333/access")
    assert access_response.status_code == 403


def test_onboard_client_creates_active_tenant_shell(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path)
    client = _login_super_admin(runtime, monkeypatch)

    response = client.post(
        "/admin/clients/onboard",
        json={
            "business_name": "Acme Store",
            "contact_name": "Asha Contact",
            "primary_email": "contact@acme.test",
            "primary_phone": "+9715000000",
            "owner_name": "Owner One",
            "owner_email": "owner@acme.test",
            "owner_password": "owner-secret",
            "default_location_name": "Main Warehouse",
            "additional_users": [
                {
                    "name": "Finance User",
                    "email": "finance@acme.test",
                    "role_code": "FINANCE_STAFF",
                    "password": "finance-secret",
                },
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["client"]["client_code"] == "acme-store"
    assert payload["client"]["contact_name"] == "Asha Contact"
    assert len(payload["users"]) == 2
    assert payload["users"][0]["is_active"] is True
    assert payload["users"][1]["is_active"] is True

    clients = runtime.store.read("clients.csv")
    settings_rows = runtime.store.read("client_settings.csv")
    locations = runtime.store.read("locations.csv")
    users = runtime.store.read("users.csv")
    roles = runtime.store.read("user_roles.csv")
    audit = runtime.store.read("audit_log.csv")

    onboarded = clients[clients["slug"] == "acme-store"]
    assert len(onboarded) == 1
    onboarded_client_id = onboarded.iloc[0]["client_id"]
    assert onboarded.iloc[0]["contact_name"] == "Asha Contact"
    assert len(settings_rows[settings_rows["client_id"] == onboarded_client_id]) == 1
    assert len(locations[locations["client_id"] == onboarded_client_id]) == 1
    onboarded_users = users[users["client_id"] == onboarded_client_id]
    assert len(onboarded_users) == 2
    assert all(str(code) for code in onboarded_users["user_code"].tolist())
    assert all(str(value) in {"True", "1"} for value in onboarded_users["is_active"].tolist())
    assert all(str(value).startswith("$2") for value in onboarded_users["password_hash"].tolist())
    assert len(roles[roles["user_id"].isin(onboarded_users["user_id"])]) == 2
    assert "client_created" in set(audit[audit["client_id"] == onboarded_client_id]["action"].tolist())
    assert "password_set_by_admin" in set(audit[audit["client_id"] == onboarded_client_id]["action"].tolist())

    owner_login = client.post(
        "/auth/login",
        json={"email": "owner@acme.test", "password": "owner-secret"},
    )
    assert owner_login.status_code == 200
    assert "Dashboard" in owner_login.json()["allowed_pages"]

    finance_login = client.post(
        "/auth/login",
        json={"email": "finance@acme.test", "password": "finance-secret"},
    )
    assert finance_login.status_code == 200


def test_super_admin_can_add_user_with_direct_password(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path)
    client = _login_super_admin(runtime, monkeypatch)

    onboard_response = client.post(
        "/admin/clients/onboard",
        json={
            "business_name": "Beacon Retail",
            "contact_name": "Beacon Contact",
            "primary_email": "contact@beacon.test",
            "primary_phone": "+9715111111",
            "owner_name": "Beacon Owner",
            "owner_email": "owner@beacon.test",
            "owner_password": "owner-secret",
            "additional_users": [],
        },
    )
    assert onboard_response.status_code == 200
    beacon_client_id = onboard_response.json()["client"]["client_id"]

    create_response = client.post(
        f"/admin/clients/{beacon_client_id}/users",
        json={
            "name": "Warehouse Staff",
            "email": "warehouse@beacon.test",
            "role_code": "CLIENT_STAFF",
            "password": "warehouse-secret",
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["is_active"] is True

    login_response = client.post(
        "/auth/login",
        json={"email": "warehouse@beacon.test", "password": "warehouse-secret"},
    )
    assert login_response.status_code == 200


def test_super_admin_can_set_password_for_existing_user(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path)
    client = _login_super_admin(runtime, monkeypatch)

    onboard_response = client.post(
        "/admin/clients/onboard",
        json={
            "business_name": "Canvas House",
            "contact_name": "Canvas Contact",
            "primary_email": "contact@canvas.test",
            "primary_phone": "+9715222222",
            "owner_name": "Canvas Owner",
            "owner_email": "owner@canvas.test",
            "owner_password": "owner-secret",
            "additional_users": [],
        },
    )
    assert onboard_response.status_code == 200
    owner = onboard_response.json()["users"][0]

    reset_response = client.post(
        f"/admin/users/{owner['user_id']}/set-password",
        json={"password": "owner-secret-2"},
    )
    assert reset_response.status_code == 200

    login_response = client.post(
        "/auth/login",
        json={"email": "owner@canvas.test", "password": "owner-secret-2"},
    )
    assert login_response.status_code == 200

    users = runtime.store.read("users.csv")
    owner_row = users[users["user_id"] == owner["user_id"]].iloc[0]
    assert verify_password("owner-secret-2", owner_row["password_hash"])


def test_super_admin_can_override_user_access_and_backend_enforces_it(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path)
    client = _login_super_admin(runtime, monkeypatch)

    onboard_response = client.post(
        "/admin/clients/onboard",
        json={
            "business_name": "Delta Ops",
            "contact_name": "Delta Contact",
            "primary_email": "contact@delta.test",
            "primary_phone": "+9715333333",
            "owner_name": "Delta Owner",
            "owner_email": "owner@delta.test",
            "owner_password": "owner-secret",
            "additional_users": [
                {
                    "name": "Delta Staff",
                    "email": "staff@delta.test",
                    "role_code": "CLIENT_STAFF",
                    "password": "staff-secret",
                }
            ],
        },
    )
    assert onboard_response.status_code == 200
    staff = next(item for item in onboard_response.json()["users"] if item["email"] == "staff@delta.test")

    access_response = client.get(f"/admin/users/{staff['user_id']}/access")
    assert access_response.status_code == 200
    assert "CATALOG" in access_response.json()["default_pages"]
    assert "FINANCE" not in access_response.json()["default_pages"]

    update_response = client.put(
        f"/admin/users/{staff['user_id']}/access",
        json={
            "overrides": [
                {"page_code": "CATALOG", "is_allowed": False},
                {"page_code": "FINANCE", "is_allowed": True},
            ]
        },
    )
    assert update_response.status_code == 200
    updated_access = update_response.json()
    assert "CATALOG" not in updated_access["effective_pages"]
    assert "FINANCE" in updated_access["effective_pages"]

    staff_client = TestClient(create_app())
    login_response = staff_client.post(
        "/auth/login",
        json={"email": "staff@delta.test", "password": "staff-secret"},
    )
    assert login_response.status_code == 200
    assert "Catalog" not in login_response.json()["allowed_pages"]
    assert "Finance" in login_response.json()["allowed_pages"]

    catalog_response = staff_client.get("/catalog/overview")
    assert catalog_response.status_code == 403
    finance_response = staff_client.get("/finance/overview")
    assert finance_response.status_code == 200

    audit = runtime.store.read("audit_log.csv")
    assert "user_access_updated" in set(audit["action"].tolist())


def test_admin_access_cannot_be_granted_via_override(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path)
    client = _login_super_admin(runtime, monkeypatch)

    onboard_response = client.post(
        "/admin/clients/onboard",
        json={
            "business_name": "Echo Supply",
            "contact_name": "Echo Contact",
            "primary_email": "contact@echo.test",
            "primary_phone": "+9715444444",
            "owner_name": "Echo Owner",
            "owner_email": "owner@echo.test",
            "owner_password": "owner-secret",
            "additional_users": [],
        },
    )
    assert onboard_response.status_code == 200
    owner = onboard_response.json()["users"][0]

    update_response = client.put(
        f"/admin/users/{owner['user_id']}/access",
        json={"overrides": [{"page_code": "ADMIN", "is_allowed": True}]},
    )
    assert update_response.status_code == 400
