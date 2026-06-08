from fastapi.testclient import TestClient


def test_health_status_ok(client: TestClient):
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_health_response_shape(client: TestClient):
    data = client.get("/api/v1/health").json()
    assert data["status"] == "ok"
    assert data["app_name"] == "PaperMoon"
    assert data["app_version"] == "0.1.0"


def test_ready_has_dependencies_field(client: TestClient):
    response = client.get("/api/v1/ready")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "dependencies" in data
    deps = data["dependencies"]
    assert "postgres" in deps
    assert "qdrant" in deps
    assert "redis" in deps


def test_ready_status_is_string(client: TestClient):
    data = client.get("/api/v1/ready").json()
    assert isinstance(data["status"], str)
