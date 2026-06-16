"""认证端点测试：注册 / 登录 / me / 401 / 409。用未认证的 anon_client。"""

from fastapi.testclient import TestClient


def test_register_returns_token(anon_client: TestClient):
    resp = anon_client.post(
        "/api/v1/auth/register", json={"email": "a@b.com", "password": "secret123"}
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]
    assert resp.json()["token_type"] == "bearer"


def test_login_then_me(anon_client: TestClient):
    anon_client.post("/api/v1/auth/register", json={"email": "x@y.com", "password": "secret123"})
    token = anon_client.post(
        "/api/v1/auth/login", json={"email": "x@y.com", "password": "secret123"}
    ).json()["access_token"]

    me = anon_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "x@y.com"


def test_me_requires_auth(anon_client: TestClient):
    assert anon_client.get("/api/v1/auth/me").status_code == 401
    # 坏 token 也应 401
    assert anon_client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    ).status_code == 401


def test_login_wrong_password(anon_client: TestClient):
    anon_client.post("/api/v1/auth/register", json={"email": "w@z.com", "password": "secret123"})
    resp = anon_client.post(
        "/api/v1/auth/login", json={"email": "w@z.com", "password": "wrongpass"}
    )
    assert resp.status_code == 401


def test_duplicate_email_rejected(anon_client: TestClient):
    anon_client.post("/api/v1/auth/register", json={"email": "d@d.com", "password": "secret123"})
    resp = anon_client.post(
        "/api/v1/auth/register", json={"email": "d@d.com", "password": "secret123"}
    )
    assert resp.status_code == 409
