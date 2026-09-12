"""开通/更新管理员账号（写入 users.json）。

用法（在 backend 目录）:
  python -m mawp.auth.bootstrap_admin

读取 backend/.env:
  AUTH_ADMIN_EMAILS=你的邮箱
  AUTH_ADMIN_PHONES=你的手机号
  AUTH_ADMIN_NAME=管理员昵称（可选）
  AUTH_ADMIN_USERNAME=登录用户名（可选，默认 wzt）
  AUTH_ADMIN_PASSWORD=登录密码（可选，默认 123456）
"""

from __future__ import annotations

import os
import sys

from mawp.auth import otp as otp_svc


def main() -> int:
    otp_svc._load_auth_env()  # noqa: SLF001
    emails = sorted(otp_svc._admin_emails())  # noqa: SLF001
    phones = sorted(otp_svc._admin_phones())  # noqa: SLF001
    name = os.getenv("AUTH_ADMIN_NAME", "管理员").strip() or "管理员"

    if not emails and not phones:
        print("请先在 backend/.env 配置 AUTH_ADMIN_EMAILS 或 AUTH_ADMIN_PHONES")
        return 1

    email = emails[0] if emails else None
    phone = phones[0] if phones else None

    # 若只有邮箱，补一个占位手机号仅用于本地开发账号结构（生产请配置真实手机）
    if email and not phone:
        if otp_svc._env_truthy("AUTH_DEV_MODE"):  # noqa: SLF001
            phone = "13800138000"
            print(f"[AUTH_DEV_MODE] 未配置 AUTH_ADMIN_PHONES，使用占位手机号 {phone}")
        else:
            print("生产环境请同时配置 AUTH_ADMIN_PHONES")
            return 1

    if phone and not email:
        if otp_svc._env_truthy("AUTH_DEV_MODE"):  # noqa: SLF001
            email = "admin@mawp.local"
            print(f"[AUTH_DEV_MODE] 未配置 AUTH_ADMIN_EMAILS，使用占位邮箱 {email}")
        else:
            print("生产环境请同时配置 AUTH_ADMIN_EMAILS")
            return 1

    assert email and phone
    username = (
        os.getenv("AUTH_ADMIN_USERNAME", "wzt").strip().lower() or "wzt"
    )
    password = os.getenv("AUTH_ADMIN_PASSWORD", "123456").strip() or "123456"
    existing = (
        otp_svc.find_user(email=email)
        or otp_svc.find_user(phone=phone)
        or otp_svc.find_user(username=username)
    )
    user = otp_svc.upsert_user(
        name=name,
        username=username,
        password=password,
        email=email,
        phone=phone,
    )
    action = "更新" if existing else "创建"
    print(f"已{action}管理员账号：")
    print(f"  昵称   {user.get('name')}")
    print(f"  用户名 {user.get('username')}  / 密码 {password}")
    print(f"  邮箱   {user.get('email')}  （登录页选「邮箱」获取验证码）")
    print(f"  手机   {user.get('phone')}  （登录页选「手机号」获取验证码）")
    print(f"  角色   {user.get('role')}")
    print()
    print("登录方式：账号密码+图形验证码，或手机/邮箱验证码。")
    print("开发模式 AUTH_DEV_MODE=1 时，点「获取验证码」会直接弹出验证码。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
