"""Auth HTTP routes for OTP + password login/register."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from mawp.auth import captcha as captcha_svc
from mawp.auth import otp as otp_svc

router = APIRouter(prefix="/api/auth", tags=["auth"])


class SendCodeBody(BaseModel):
    channel: Literal["phone", "email"]
    target: str = Field(min_length=3, max_length=120)
    purpose: Literal["login", "register"] = "login"


class VerifyBody(BaseModel):
    channel: Literal["phone", "email"] | None = None
    target: str | None = Field(default=None, min_length=3, max_length=120)
    code: str | None = Field(default=None, min_length=4, max_length=8)
    purpose: Literal["login", "register"] = "login"
    name: str | None = Field(default=None, max_length=40)
    username: str | None = Field(default=None, max_length=40)
    password: str | None = Field(default=None, max_length=128)
    email: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=20)
    email_code: str | None = Field(default=None, min_length=4, max_length=8)
    phone_code: str | None = Field(default=None, min_length=4, max_length=8)


class PasswordLoginBody(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=6, max_length=128)
    captcha_id: str = Field(min_length=8, max_length=80)
    captcha_code: str = Field(min_length=3, max_length=8)


@router.get("/captcha")
def captcha() -> dict[str, Any]:
    return captcha_svc.create_captcha()


@router.post("/send-code")
def send_code(body: SendCodeBody) -> dict[str, Any]:
    try:
        return otp_svc.request_code(body.channel, body.target, body.purpose)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"发送失败：{exc}") from exc


@router.post("/login-password")
def login_password(body: PasswordLoginBody) -> dict[str, Any]:
    try:
        return otp_svc.login_with_password(
            username=body.username,
            password=body.password,
            captcha_id=body.captcha_id,
            captcha_code=body.captcha_code,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/verify")
def verify(body: VerifyBody) -> dict[str, Any]:
    try:
        if body.purpose == "register":
            return otp_svc.verify_register(
                name=body.name,
                username=body.username or "",
                password=body.password or "",
                email=body.email or "",
                phone=body.phone or "",
                email_code=body.email_code or "",
                phone_code=body.phone_code or "",
            )
        if not body.channel or not body.target or not body.code:
            raise ValueError("请填写登录账号与验证码")
        return otp_svc.verify_code(
            channel=body.channel,
            target_raw=body.target,
            code=body.code,
            purpose="login",
            name=body.name,
            email=body.email,
            phone=body.phone,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class ProfileBody(BaseModel):
    name: str | None = Field(default=None, max_length=40)
    username: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=120)
    # 允许较大 data URL；服务端会落盘并改写为短 URL
    avatar: str | None = None
    bio: str | None = Field(default=None, max_length=200)


@router.get("/avatars/{filename}")
def get_avatar(filename: str) -> FileResponse:
    path = otp_svc.avatar_file(filename)
    if not path:
        raise HTTPException(status_code=404, detail="头像不存在")
    return FileResponse(path)


@router.get("/me")
def me(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    token = _bearer(authorization)
    user = otp_svc.user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="未登录或会话已失效")
    return {"user": user}


@router.patch("/me")
def patch_me(
    body: ProfileBody,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    try:
        user = otp_svc.update_profile(
            _bearer(authorization),
            name=body.name,
            username=body.username,
            email=body.email,
            avatar=body.avatar,
            bio=body.bio,
        )
        return {"ok": True, "user": user}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"资料同步失败：{exc}") from exc


@router.get("/users")
def users(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    token = _bearer(authorization)
    user = otp_svc.user_from_token(token)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return {"users": otp_svc.list_users()}


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return authorization.strip()
