"""认证端点测试：注册 / 登录 / me / 401 / 409 + 启动安全闸。用未认证的 anon_client。"""

import pytest
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


def test_duplicate_email_race_falls_back_to_409(anon_client: TestClient, monkeypatch):
    # 模拟并发：让查重短路（返回 None），仍应被 unique 约束的 IntegrityError 兜成 409 而非 500
    anon_client.post("/api/v1/auth/register", json={"email": "race@d.com", "password": "secret123"})

    import app.services.auth_service as auth_service
    monkeypatch.setattr(auth_service.user_repository, "get_by_email", lambda *a, **k: None)

    resp = anon_client.post(
        "/api/v1/auth/register", json={"email": "race@d.com", "password": "secret123"}
    )
    assert resp.status_code == 409


# ── 注册收紧：密码策略 + 邮箱规范化/校验 ──────────────────────────────────

@pytest.mark.parametrize(
    "email,password,reason",
    [
        ("p1@test.com", "short1", "至少 8 位"),         # 不足 8 位
        ("p2@test.com", "abcdefgh", "字母和数字"),       # 无数字
        ("p3@test.com", "12345678", "字母和数字"),       # 无字母
        ("p4@test.com", "password1", "过于常见"),        # 命中弱密码黑名单
        ("danielx@test.com", "danielx12", "邮箱名"),     # 包含邮箱本地名
    ],
)
def test_register_rejects_weak_password(anon_client: TestClient, email, password, reason):
    resp = anon_client.post(
        "/api/v1/auth/register", json={"email": email, "password": password}
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["error_code"] == "WEAK_PASSWORD"
    assert reason in body["message"]


def test_register_rejects_malformed_email(anon_client: TestClient):
    resp = anon_client.post(
        "/api/v1/auth/register", json={"email": "notanemail", "password": "secret123"}
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "INVALID_EMAIL"


def test_register_normalizes_email_case(anon_client: TestClient):
    # 大小写混写注册 → 存储为小写；不同大小写视为同一邮箱（去重 + 登录均匹配）。
    anon_client.post(
        "/api/v1/auth/register", json={"email": "Foo@Example.COM", "password": "secret123"}
    )
    dup = anon_client.post(
        "/api/v1/auth/register", json={"email": "foo@example.com", "password": "secret123"}
    )
    assert dup.status_code == 409  # 视为重复

    token = anon_client.post(
        "/api/v1/auth/login", json={"email": "FOO@EXAMPLE.com", "password": "secret123"}
    ).json()["access_token"]
    me = anon_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["email"] == "foo@example.com"


def test_register_rejects_undeliverable_email_when_check_enabled(anon_client, monkeypatch):
    # 打开 MX 校验开关，并 monkeypatch validate_email 抛错（不打真实 DNS），
    # 验证“开关透传 + 不可投递 → 400 INVALID_EMAIL”。
    import app.services.auth_service as auth_service
    from app.core.config import settings
    from email_validator import EmailNotValidError

    monkeypatch.setattr(settings, "auth_check_email_deliverability", True)

    def fake_validate(email, check_deliverability=False, **kw):
        assert check_deliverability is True  # 开关确实透传到了校验
        raise EmailNotValidError("no MX")

    monkeypatch.setattr(auth_service, "validate_email", fake_validate)

    resp = anon_client.post(
        "/api/v1/auth/register", json={"email": "x@hh.hh", "password": "secret123"}
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "INVALID_EMAIL"


def test_startup_rejects_default_jwt_secret_in_prod(monkeypatch):
    # 安全闸：非 debug + 默认 JWT 密钥 → lifespan 启动应直接拒绝（防伪造 token）
    from app.core.config import DEV_JWT_SECRET, settings
    import app.main as main

    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "jwt_secret", DEV_JWT_SECRET)

    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        with TestClient(main.app):
            pass
