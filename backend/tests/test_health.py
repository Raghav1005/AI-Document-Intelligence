from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_liveness_reports_running_process() -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_reports_api_only_check() -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"api": "ok"}}
