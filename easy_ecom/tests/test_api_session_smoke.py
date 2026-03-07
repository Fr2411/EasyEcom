from fastapi.testclient import TestClient

from easy_ecom.api.main import app


def test_session_me_smoke() -> None:
    client = TestClient(app)

    response = client.get("/session/me")

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "dev-super-admin",
        "email": "admin@easyecom.local",
        "name": "Super Admin",
        "role": "SUPER_ADMIN",
        "client_id": None,
        "is_authenticated": True,
    }
