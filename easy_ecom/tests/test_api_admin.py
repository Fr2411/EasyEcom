from pathlib import Path

from fastapi.testclient import TestClient

from easy_ecom.api import dependencies as deps
from easy_ecom.api.main import create_app
from easy_ecom.core.security import hash_password
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


def test_onboard_client_creates_tenant_shell(monkeypatch, tmp_path: Path):
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
            "default_location_name": "Main Warehouse",
            "additional_users": [
                {"name": "Finance User", "email": "finance@acme.test", "role_code": "FINANCE_STAFF"},
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["client"]["client_code"] == "acme-store"
    assert payload["client"]["contact_name"] == "Asha Contact"
    assert len(payload["users"]) == 2
    assert payload["users"][0]["invitation_token"]
    assert payload["users"][1]["invitation_token"]

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
    assert len(roles[roles["user_id"].isin(onboarded_users["user_id"])]) == 2
    assert len(audit[audit["client_id"] == onboarded_client_id]) >= 3


def test_accept_invitation_activates_precreated_user(monkeypatch, tmp_path: Path):
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
            "additional_users": [],
        },
    )
    assert onboard_response.status_code == 200
    owner = onboard_response.json()["users"][0]

    accept_response = client.post(
        "/auth/accept-invitation",
        json={
            "token": owner["invitation_token"],
            "name": "Beacon Owner",
            "password": "owner-secret",
        },
    )
    assert accept_response.status_code == 200
    assert accept_response.json()["email"] == "owner@beacon.test"

    login_response = client.post(
        "/auth/login",
        json={"email": "owner@beacon.test", "password": "owner-secret"},
    )
    assert login_response.status_code == 200

    users = runtime.store.read("users.csv")
    owner_rows = users[users["email"] == "owner@beacon.test"]
    assert len(owner_rows) == 1
    assert str(owner_rows.iloc[0]["is_active"]) in {"True", "1"}


def test_super_admin_can_issue_password_reset_for_active_user(monkeypatch, tmp_path: Path):
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
            "additional_users": [],
        },
    )
    owner = onboard_response.json()["users"][0]

    accept_response = client.post(
        "/auth/accept-invitation",
        json={
            "token": owner["invitation_token"],
            "name": "Canvas Owner",
            "password": "owner-secret",
        },
    )
    assert accept_response.status_code == 200

    super_admin_login = client.post("/auth/login", json={"email": "admin@example.com", "password": "secret"})
    assert super_admin_login.status_code == 200

    reset_response = client.post(f"/admin/users/{owner['user_id']}/issue-password-reset")
    assert reset_response.status_code == 200
    reset_token = reset_response.json()["password_reset_token"]
    assert reset_token

    confirm_response = client.post(
        "/auth/reset-password",
        json={"token": reset_token, "new_password": "owner-secret-2"},
    )
    assert confirm_response.status_code == 200

    login_response = client.post(
        "/auth/login",
        json={"email": "owner@canvas.test", "password": "owner-secret-2"},
    )
    assert login_response.status_code == 200
