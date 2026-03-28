from fastapi.testclient import TestClient

from easy_ecom.api.main import app


def test_health_endpoint_smoke() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_live_endpoint_smoke() -> None:
    client = TestClient(app)

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "mode": "live"}
