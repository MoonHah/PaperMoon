from fastapi.testclient import TestClient


def test_health_status_code(client: TestClient):
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_health_response_body(client: TestClient):
    response = client.get("/api/v1/health")
    data = response.json()
    assert data["status"] == "ok"
    assert data["app_name"] == "PaperMoon"
    assert data["app_version"] == "0.1.0"
