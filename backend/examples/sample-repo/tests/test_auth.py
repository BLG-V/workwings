"""Sample repo tests for Agent E2E demo."""

import time
from pathlib import Path

from fastapi.testclient import TestClient

from src.main import app
from src.auth.login import CODE_STORE, CODE_TTL_SECONDS

client = TestClient(app)


# ---------------------------------------------------------------------------
# Existing behaviour — regression safety
# ---------------------------------------------------------------------------


def test_main_module_exists() -> None:
    root = Path(__file__).resolve().parents[1]
    main_py = root / "src" / "main.py"
    assert main_py.is_file()


def test_auth_login_module_exists() -> None:
    root = Path(__file__).resolve().parents[1]
    login_py = root / "src" / "auth" / "login.py"
    assert login_py.is_file()
    content = login_py.read_text(encoding="utf-8")
    assert "login" in content


def test_password_login_works_unchanged() -> None:
    """现有密码登录行为不受验证码功能影响"""
    response = client.post(
        "/auth/login", json={"email": "user@example.com", "password": "secret"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["access_token"] == "jwt-token-placeholder"
    assert data["token_type"] == "bearer"


def test_password_login_rejects_empty_password() -> None:
    """密码为空时返回 400"""
    response = client.post(
        "/auth/login", json={"email": "user@example.com", "password": ""}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "invalid credentials"


# ---------------------------------------------------------------------------
# POST /auth/send-code
# ---------------------------------------------------------------------------


def test_send_code_valid_email() -> None:
    """合法 EmailStr 返回 200 与正确的响应结构"""
    response = client.post("/auth/send-code", json={"email": "dev@example.com"})
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Verification code sent to dev@example.com"
    assert data["expires_in_seconds"] == CODE_TTL_SECONDS
    # 验证码已存入内存
    assert "dev@example.com" in CODE_STORE


def test_send_code_invalid_email_returns_422() -> None:
    """非邮箱格式触发 Pydantic 422"""
    response = client.post("/auth/send-code", json={"email": "not-an-email"})
    assert response.status_code == 422


def test_send_code_overwrites_previous() -> None:
    """同一邮箱重复请求发送验证码时，新码覆盖旧码并刷新有效期"""
    email = "overwrite@example.com"
    client.post("/auth/send-code", json={"email": email})
    old_code, old_expiry = CODE_STORE[email]

    # 稍等以确保时间戳不同（实际上 expiry 每次都会刷新）
    client.post("/auth/send-code", json={"email": email})
    new_code, new_expiry = CODE_STORE[email]

    # 新码覆盖旧码（极低概率碰撞，不做强断言）
    # 旧码不应再能登录
    resp = client.post("/auth/login/via-code", json={"email": email, "code": old_code})
    assert resp.status_code == 401

    # 新码应能登录
    resp = client.post("/auth/login/via-code", json={"email": email, "code": new_code})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /auth/login/via-code
# ---------------------------------------------------------------------------


def test_login_via_code_success() -> None:
    """正确的 email + code 返回 TokenResponse"""
    email = "success@example.com"
    client.post("/auth/send-code", json={"email": email})
    code, _ = CODE_STORE[email]

    response = client.post(
        "/auth/login/via-code", json={"email": email, "code": code}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["access_token"] == "jwt-token-placeholder"
    assert data["token_type"] == "bearer"
    # 验证码已被消费
    assert email not in CODE_STORE


def test_login_via_code_wrong_code_returns_401() -> None:
    """错误的验证码返回 401"""
    email = "wrong-code@example.com"
    client.post("/auth/send-code", json={"email": email})

    response = client.post(
        "/auth/login/via-code", json={"email": email, "code": "000000"}
    )
    assert response.status_code == 401
    assert "invalid or expired verification code" in response.json()["detail"]


def test_login_via_code_consumed_once() -> None:
    """验证码一次性消费：第二次使用同一验证码返回 401"""
    email = "once@example.com"
    client.post("/auth/send-code", json={"email": email})
    code, _ = CODE_STORE[email]

    r1 = client.post("/auth/login/via-code", json={"email": email, "code": code})
    assert r1.status_code == 200

    r2 = client.post("/auth/login/via-code", json={"email": email, "code": code})
    assert r2.status_code == 401


def test_login_via_code_expired_returns_401() -> None:
    """过期的验证码返回 401"""
    email = "expired@example.com"
    client.post("/auth/send-code", json={"email": email})
    code, _ = CODE_STORE[email]

    # 手动将过期时间设为过去
    CODE_STORE[email] = (code, time.time() - 1)

    response = client.post(
        "/auth/login/via-code", json={"email": email, "code": code}
    )
    assert response.status_code == 401
    # 过期码应被清理
    assert email not in CODE_STORE


def test_login_via_code_no_code_sent_returns_401() -> None:
    """未请求过验证码的邮箱直接登录返回 401"""
    response = client.post(
        "/auth/login/via-code",
        json={"email": "never-sent@example.com", "code": "123456"},
    )
    assert response.status_code == 401
