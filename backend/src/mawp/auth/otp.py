"""验证码登录：邮箱 SMTP + 阿里云短信（真实发送）。"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import random
import re
import smtplib
import ssl
import time
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Literal

Channel = Literal["phone", "email"]
Purpose = Literal["login", "register"]

PHONE_RE = re.compile(r"^1[3-9]\d{9}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

CODE_TTL_SEC = 300
SEND_COOLDOWN_SEC = 60
MAX_VERIFY_ATTEMPTS = 5


def _data_dir() -> Path:
    root = Path(__file__).resolve().parents[3]  # backend/
    d = root / "data" / "auth"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _users_path() -> Path:
    return _data_dir() / "users.json"


def _sessions_path() -> Path:
    return _data_dir() / "sessions.json"


def _load_auth_env() -> None:
    """加载 backend/.env 与 cwd/.env（不覆盖已有环境变量）。"""
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parents[3] / ".env",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        text = None
        for enc in ("utf-8-sig", "utf-8", "gbk", "cp936"):
            try:
                text = path.read_text(encoding=enc)
                break
            except UnicodeDecodeError:
                continue
            except OSError:
                text = None
                break
        if text is None:
            continue
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip().lstrip("\ufeff")
            value = value.strip().strip("'").strip('"')
            if key and key not in os.environ:
                os.environ[key] = value


def _env_truthy(name: str) -> bool:
    _load_auth_env()
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _admin_emails() -> set[str]:
    _load_auth_env()
    raw = os.getenv("AUTH_ADMIN_EMAILS", "wzt@example.com")
    return {x.strip().lower() for x in re.split(r"[,，\s]+", raw) if x.strip()}


def _admin_phones() -> set[str]:
    _load_auth_env()
    raw = os.getenv("AUTH_ADMIN_PHONES", "")
    return {x.strip() for x in re.split(r"[,，\s]+", raw) if x.strip()}


def normalize_target(channel: Channel, target: str) -> str:
    t = target.strip()
    if channel == "phone":
        t = re.sub(r"[\s\-]", "", t)
        if t.startswith("+86"):
            t = t[3:]
        if not PHONE_RE.match(t):
            raise ValueError("请输入有效的大陆手机号")
        return t
    t = t.lower()
    if not EMAIL_RE.match(t):
        raise ValueError("请输入有效的邮箱地址")
    return t


def resolve_role(*, phone: str | None, email: str | None) -> str:
    if phone and phone in _admin_phones():
        return "admin"
    if email and email.lower() in _admin_emails():
        return "admin"
    return "user"


def _read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def list_users() -> list[dict[str, Any]]:
    users = _read_json(_users_path(), [])
    out = []
    for u in users if isinstance(users, list) else []:
        out.append(
            {
                "id": u.get("id"),
                "name": u.get("name"),
                "username": u.get("username"),
                "email": u.get("email") or "",
                "phone": u.get("phone") or "",
                "role": u.get("role") or "user",
                "provider": u.get("provider") or "otp",
                "avatar": u.get("avatar"),
                "bio": u.get("bio"),
                "hasPassword": bool(u.get("passwordHash")),
            }
        )
    return out


def _raw_users() -> list[dict[str, Any]]:
    users = _read_json(_users_path(), [])
    return users if isinstance(users, list) else []


def find_user(
    *,
    phone: str | None = None,
    email: str | None = None,
    username: str | None = None,
) -> dict[str, Any] | None:
    for u in _raw_users():
        if phone and u.get("phone") == phone:
            return u
        if email and (u.get("email") or "").lower() == email.lower():
            return u
        if username and (u.get("username") or "").lower() == username.lower():
            return u
    return None


def public_user(u: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": u.get("id"),
        "name": u.get("name"),
        "username": u.get("username"),
        "email": u.get("email") or "",
        "phone": u.get("phone") or "",
        "role": u.get("role") or "user",
        "provider": u.get("provider") or "otp",
        "avatar": u.get("avatar"),
        "bio": u.get("bio"),
        "hasPassword": bool(u.get("passwordHash")),
    }


def hash_password(password: str) -> str:
    salt = uuid.uuid4().hex
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120_000,
    ).hex()
    return f"pbkdf2${salt}${digest}"


def check_password(password: str, password_hash: str | None) -> bool:
    if not password_hash or not password_hash.startswith("pbkdf2$"):
        return False
    try:
        _, salt, digest = password_hash.split("$", 2)
    except ValueError:
        return False
    got = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120_000,
    ).hex()
    return hmac.compare_digest(got, digest)


def upsert_user(
    *,
    channel: Channel | None = None,
    target: str | None = None,
    name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    username: str | None = None,
    password: str | None = None,
) -> dict[str, Any]:
    users = _raw_users()

    if channel == "phone" and target:
        phone = target
    elif channel == "email" and target:
        email = target

    phone = phone or None
    email = (email or "").strip().lower() or None
    username_norm = (username or "").strip().lower() or None

    existing = None
    for u in users:
        if phone and u.get("phone") == phone:
            existing = u
            break
        if email and (u.get("email") or "").lower() == email:
            existing = u
            break
        if username_norm and (u.get("username") or "").lower() == username_norm:
            existing = u
            break

    role = resolve_role(
        phone=phone or (existing or {}).get("phone"),
        email=email or (existing or {}).get("email"),
    )

    if existing:
        if name and name.strip():
            existing["name"] = name.strip()
        existing["role"] = role
        if phone:
            existing["phone"] = phone
        if email:
            existing["email"] = email
        if username_norm:
            existing["username"] = username_norm
        if password:
            existing["passwordHash"] = hash_password(password)
            existing["provider"] = "password+otp"
        _write_json(_users_path(), users)
        return public_user(existing)

    if username_norm:
        if not re.fullmatch(r"[a-z0-9_]{3,20}", username_norm):
            raise ValueError("用户名需为 3–20 位字母/数字/下划线")
        if any((u.get("username") or "").lower() == username_norm for u in users):
            raise ValueError("用户名已被占用")
        candidate = username_norm
    else:
        base = (email or phone or "user").split("@")[0]
        username = re.sub(r"[^a-z0-9_]", "", base.lower())[:16] or f"u{int(time.time()) % 100000}"
        taken = {str(u.get("username", "")).lower() for u in users}
        candidate = username
        n = 1
        while candidate.lower() in taken:
            candidate = f"{username}{n}"
            n += 1

    display = (name or "").strip() or (
        email.split("@")[0] if email else f"用户{(phone or '')[-4:]}"
    )
    uid = f"u-{uuid.uuid4().hex[:10]}"
    if resolve_role(phone=phone, email=email) == "admin":
        preferred = os.getenv("AUTH_ADMIN_ID", "u-1").strip() or "u-1"
        if not any(str(u.get("id")) == preferred for u in users):
            uid = preferred

    user: dict[str, Any] = {
        "id": uid,
        "name": display,
        "username": candidate,
        "email": email or "",
        "phone": phone or "",
        "role": role,
        "provider": "password+otp" if password else "otp",
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if password:
        if len(password) < 6:
            raise ValueError("密码至少 6 位")
        user["passwordHash"] = hash_password(password)
    users.append(user)
    _write_json(_users_path(), users)
    return public_user(user)


def create_session(user_id: str) -> str:
    token = uuid.uuid4().hex + uuid.uuid4().hex
    sessions = _read_json(_sessions_path(), {})
    if not isinstance(sessions, dict):
        sessions = {}
    sessions[token] = {"userId": user_id, "createdAt": time.time()}
    # prune old (>30d)
    cutoff = time.time() - 30 * 86400
    sessions = {
        k: v
        for k, v in sessions.items()
        if isinstance(v, dict) and float(v.get("createdAt") or 0) >= cutoff
    }
    _write_json(_sessions_path(), sessions)
    return token


@dataclass
class PendingCode:
    code_hash: str
    channel: Channel
    target: str
    purpose: Purpose
    expires_at: float
    last_sent_at: float
    attempts: int = 0


_pending: dict[str, PendingCode] = {}


def _pending_key(channel: Channel, target: str, purpose: Purpose) -> str:
    return f"{purpose}:{channel}:{target}"


def _hash_code(code: str) -> str:
    salt = os.getenv("AUTH_CODE_SALT", "mawp-otp")
    return hashlib.sha256(f"{salt}:{code}".encode()).hexdigest()


def _gen_code() -> str:
    return f"{random.randint(0, 999999):06d}"


def user_from_token(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    sessions = _read_json(_sessions_path(), {})
    if not isinstance(sessions, dict):
        return None
    meta = sessions.get(token)
    if not isinstance(meta, dict):
        return None
    uid = meta.get("userId")
    for u in _raw_users():
        if u.get("id") == uid:
            return public_user(u)
    return None


def update_profile(
    token: str | None,
    *,
    name: str | None = None,
    username: str | None = None,
    email: str | None = None,
    avatar: str | None = None,
    bio: str | None = None,
) -> dict[str, Any]:
    """更新当前登录用户资料（头像/简介等会写回 users.json）。"""
    if not token:
        raise ValueError("未登录或会话已失效")
    sessions = _read_json(_sessions_path(), {})
    if not isinstance(sessions, dict):
        raise ValueError("未登录或会话已失效")
    meta = sessions.get(token)
    if not isinstance(meta, dict):
        raise ValueError("未登录或会话已失效")
    uid = meta.get("userId")
    users = _raw_users()
    target: dict[str, Any] | None = None
    for u in users:
        if u.get("id") == uid:
            target = u
            break
    if not target:
        raise ValueError("用户不存在")

    if name is not None:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("昵称不能为空")
        target["name"] = cleaned[:40]

    if username is not None:
        username_norm = username.strip().lower()
        if not re.fullmatch(r"[a-z0-9_]{3,20}", username_norm):
            raise ValueError("用户名需为 3–20 位字母/数字/下划线")
        for u in users:
            if u.get("id") != uid and (u.get("username") or "").lower() == username_norm:
                raise ValueError("用户名已被占用")
        target["username"] = username_norm

    if email is not None:
        email_norm = email.strip().lower()
        if email_norm and "@" not in email_norm:
            raise ValueError("邮箱格式不正确")
        if email_norm:
            for u in users:
                if u.get("id") != uid and (u.get("email") or "").lower() == email_norm:
                    raise ValueError("邮箱已被占用")
            target["email"] = email_norm

    if avatar is not None:
        target["avatar"] = _persist_avatar(str(uid), avatar)

    if bio is not None:
        target["bio"] = bio.strip()[:200]

    _write_json(_users_path(), users)
    return public_user(target)


def _persist_avatar(user_id: str, avatar: str) -> str:
    """data URL 落盘为文件，避免 users.json 膨胀导致代理/进程异常。"""
    import base64

    value = (avatar or "").strip()
    if not value:
        return ""
    if not value.startswith("data:"):
        if len(value) > 2000:
            raise ValueError("头像 URL 过长")
        return value

    try:
        header, b64 = value.split(",", 1)
    except ValueError as exc:
        raise ValueError("头像数据无效") from exc
    try:
        raw = base64.b64decode(b64, validate=False)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("头像数据无效") from exc
    if len(raw) > 600_000:
        raise ValueError("头像过大，请压缩后再上传（建议 ≤ 500KB）")

    mime = header.split(";")[0].removeprefix("data:").lower()
    ext = "jpg"
    if "png" in mime:
        ext = "png"
    elif "webp" in mime:
        ext = "webp"
    elif "gif" in mime:
        ext = "gif"

    folder = _data_dir() / "avatars"
    folder.mkdir(parents=True, exist_ok=True)
    # 清理同用户旧扩展名
    for old in folder.glob(f"{user_id}.*"):
        try:
            old.unlink()
        except OSError:
            pass
    path = folder / f"{user_id}.{ext}"
    path.write_bytes(raw)
    # 前端经 Vite 代理 /api/mawp → /api
    return f"/api/mawp/auth/avatars/{user_id}.{ext}?v={int(time.time())}"


def avatar_file(filename: str) -> Path | None:
    name = Path(filename).name
    if not re.fullmatch(r"u-[\w-]+\.(jpg|jpeg|png|webp|gif)", name, re.I):
        return None
    path = _data_dir() / "avatars" / name
    if not path.is_file():
        return None
    return path



def verify_register(
    *,
    name: str | None,
    username: str,
    password: str,
    email: str,
    phone: str = "",
    email_code: str,
    phone_code: str = "",
) -> dict[str, Any]:
    """注册：用户名+密码 + 邮箱验证码（手机可选）。"""
    if not (name or "").strip():
        raise ValueError("请填写昵称")
    username_norm = (username or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9_]{3,20}", username_norm):
        raise ValueError("用户名需为 3–20 位字母/数字/下划线")
    if len(password or "") < 6:
        raise ValueError("密码至少 6 位")

    email_norm = normalize_target("email", email)
    if not (email_code or "").strip():
        raise ValueError("请填写邮箱验证码")

    phone_norm = ""
    if (phone or "").strip():
        phone_norm = normalize_target("phone", phone)
        if not (phone_code or "").strip():
            raise ValueError("请填写手机验证码")

    if find_user(username=username_norm):
        raise ValueError("用户名已被占用")
    if find_user(email=email_norm) or (phone_norm and find_user(phone=phone_norm)):
        raise ValueError("该邮箱/手机号已注册，请直接登录")

    _peek_pending("email", email_norm, "register", email_code)
    _pending.pop(_pending_key("email", email_norm, "register"), None)
    if phone_norm:
        _peek_pending("phone", phone_norm, "register", phone_code)
        _pending.pop(_pending_key("phone", phone_norm, "register"), None)

    user = upsert_user(
        name=name,
        username=username_norm,
        password=password,
        email=email_norm,
        phone=phone_norm or None,
    )
    token = create_session(str(user["id"]))
    return {"ok": True, "token": token, "user": user}


def login_with_password(
    *,
    username: str,
    password: str,
    captcha_id: str,
    captcha_code: str,
) -> dict[str, Any]:
    from mawp.auth.captcha import verify_captcha

    if not verify_captcha(captcha_id, captcha_code, consume=True):
        raise ValueError("图形验证码不正确或已过期")
    user = find_user(username=(username or "").strip().lower())
    if not user:
        raise ValueError("用户名或密码不正确")
    if not check_password(password, user.get("passwordHash")):
        raise ValueError("用户名或密码不正确")
    # 刷新角色
    role = resolve_role(phone=user.get("phone"), email=user.get("email"))
    if user.get("role") != role:
        users = _raw_users()
        for u in users:
            if u.get("id") == user.get("id"):
                u["role"] = role
                break
        _write_json(_users_path(), users)
        user["role"] = role
    token = create_session(str(user["id"]))
    return {"ok": True, "token": token, "user": public_user(user)}


def verify_code(
    *,
    channel: Channel,
    target_raw: str,
    code: str,
    purpose: Purpose,
    name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
) -> dict[str, Any]:
    if purpose == "register":
        raise ValueError("请使用双重验证码完成注册")

    target = normalize_target(channel, target_raw)
    _consume_pending(channel, target, purpose, code)

    user = find_user(
        phone=target if channel == "phone" else None,
        email=target if channel == "email" else None,
    )
    if not user:
        raise ValueError("账号未注册，请先注册")
    pub = upsert_user(
        channel=channel,
        target=target,
        name=name or user.get("name"),
        email=user.get("email") or (target if channel == "email" else None),
        phone=user.get("phone") or (target if channel == "phone" else None),
    )

    token = create_session(str(pub["id"]))
    return {"ok": True, "token": token, "user": pub}

def send_email_code(to_email: str, code: str) -> None:
    _load_auth_env()
    host = os.getenv("SMTP_HOST", "").strip()
    port = int(os.getenv("SMTP_PORT", "465") or "465")
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    mail_from = os.getenv("SMTP_FROM", user).strip()
    if not host or not user or not password or not mail_from:
        raise RuntimeError(
            "邮箱验证码未配置：请在 backend/.env 设置 SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD / SMTP_FROM"
        )

    msg = EmailMessage()
    msg["Subject"] = f"智流 MAWP 验证码：{code}"
    msg["From"] = mail_from
    msg["To"] = to_email
    msg.set_content(
        f"您的验证码是 {code}，{CODE_TTL_SEC // 60} 分钟内有效。\n"
        f"如非本人操作，请忽略本邮件。\n\n— 智流 MAWP"
    )

    context = ssl.create_default_context()
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as smtp:
                smtp.ehlo()
                smtp.login(user, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=20) as smtp:
                smtp.ehlo()
                smtp.starttls(context=context)
                smtp.ehlo()
                smtp.login(user, password)
                smtp.send_message(msg)
    except smtplib.SMTPAuthenticationError as exc:
        raise RuntimeError(
            "QQ 邮箱 SMTP 登录失败：请确认已开启 SMTP 服务，并使用「授权码」而非登录密码。"
            f" 详情：{exc.smtp_error.decode('utf-8', errors='ignore') if isinstance(exc.smtp_error, bytes) else exc}"
        ) from exc
    except smtplib.SMTPServerDisconnected as exc:
        raise RuntimeError(
            "QQ 邮箱 SMTP 连接被断开（常见原因：未开启 SMTP、授权码错误/过期、发送频率受限）。"
            "请到 QQ 邮箱 → 设置 → 账户 → POP3/IMAP/SMTP 重新生成授权码。"
        ) from exc


def send_aliyun_sms(phone: str, code: str) -> None:
    _load_auth_env()
    access_key = os.getenv("ALIYUN_ACCESS_KEY_ID", "").strip()
    access_secret = os.getenv("ALIYUN_ACCESS_KEY_SECRET", "").strip()
    sign_name = os.getenv("ALIYUN_SMS_SIGN_NAME", "").strip()
    template_code = os.getenv("ALIYUN_SMS_TEMPLATE_CODE", "").strip()
    if not all([access_key, access_secret, sign_name, template_code]):
        raise RuntimeError(
            "短信验证码未配置：请在 backend/.env 设置 ALIYUN_ACCESS_KEY_ID / "
            "ALIYUN_ACCESS_KEY_SECRET / ALIYUN_SMS_SIGN_NAME / ALIYUN_SMS_TEMPLATE_CODE"
        )

    params: dict[str, str] = {
        "AccessKeyId": access_key,
        "Action": "SendSms",
        "Format": "JSON",
        "PhoneNumbers": phone,
        "RegionId": os.getenv("ALIYUN_SMS_REGION", "cn-hangzhou"),
        "SignName": sign_name,
        "SignatureMethod": "HMAC-SHA1",
        "SignatureNonce": uuid.uuid4().hex,
        "SignatureVersion": "1.0",
        "TemplateCode": template_code,
        "TemplateParam": json.dumps({"code": code}, ensure_ascii=False),
        "Timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "Version": "2017-05-25",
    }

    sorted_items = sorted(params.items())
    query = urllib.parse.urlencode(sorted_items, quote_via=urllib.parse.quote)
    string_to_sign = "GET&%2F&" + urllib.parse.quote(query, safe="")
    key = (access_secret + "&").encode("utf-8")
    digest = hmac.new(key, string_to_sign.encode("utf-8"), hashlib.sha1).digest()
    signature = base64_encode(digest)
    params["Signature"] = signature

    url = "https://dysmsapi.aliyuncs.com/?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if body.get("Code") != "OK":
        raise RuntimeError(f"短信发送失败：{body.get('Message') or body.get('Code') or body}")


def base64_encode(data: bytes) -> str:
    import base64

    return base64.b64encode(data).decode("utf-8")


def dispatch_code(channel: Channel, target: str, code: str) -> dict[str, Any]:
    """真实发送；开发模式可回显验证码。"""
    meta: dict[str, Any] = {"sent": True, "channel": channel}
    if _env_truthy("AUTH_DEV_MODE"):
        # 开发模式：有配置才尝试真发；没配就静默回显，不打断登录
        configured = False
        if channel == "email":
            _load_auth_env()
            configured = bool(
                os.getenv("SMTP_HOST", "").strip()
                and os.getenv("SMTP_USER", "").strip()
                and os.getenv("SMTP_PASSWORD", "").strip()
            )
        else:
            _load_auth_env()
            configured = bool(
                os.getenv("ALIYUN_ACCESS_KEY_ID", "").strip()
                and os.getenv("ALIYUN_ACCESS_KEY_SECRET", "").strip()
                and os.getenv("ALIYUN_SMS_SIGN_NAME", "").strip()
                and os.getenv("ALIYUN_SMS_TEMPLATE_CODE", "").strip()
            )
        if configured:
            try:
                if channel == "email":
                    send_email_code(target, code)
                else:
                    send_aliyun_sms(target, code)
            except Exception as exc:  # noqa: BLE001
                meta["warning"] = f"真发失败，已回显验证码：{exc}"
        else:
            meta["devFallback"] = True
        meta["devCode"] = code
        print(f"[AUTH_DEV_MODE] {channel} {target} code={code}", flush=True)
        return meta

    if channel == "email":
        send_email_code(target, code)
    else:
        send_aliyun_sms(target, code)
    return meta


def request_code(channel: Channel, target_raw: str, purpose: Purpose) -> dict[str, Any]:
    target = normalize_target(channel, target_raw)
    key = _pending_key(channel, target, purpose)
    now = time.time()
    prev = _pending.get(key)
    if prev and now - prev.last_sent_at < SEND_COOLDOWN_SEC:
        wait = int(SEND_COOLDOWN_SEC - (now - prev.last_sent_at))
        raise ValueError(f"发送过于频繁，请 {wait} 秒后再试")

    existing = find_user(phone=target if channel == "phone" else None, email=target if channel == "email" else None)
    if purpose == "register" and existing:
        raise ValueError("该手机号/邮箱已注册，请直接登录")
    if purpose == "login" and not existing:
        # 允许登录页提示去注册；也可自动注册——按产品：登录未注册则报错
        raise ValueError("账号未注册，请先注册")

    code = _gen_code()
    send_meta = dispatch_code(channel, target, code)
    _pending[key] = PendingCode(
        code_hash=_hash_code(code),
        channel=channel,
        target=target,
        purpose=purpose,
        expires_at=now + CODE_TTL_SEC,
        last_sent_at=now,
        attempts=0,
    )
    return {
        "ok": True,
        "channel": channel,
        "targetMasked": _mask(channel, target),
        "expiresIn": CODE_TTL_SEC,
        "cooldown": SEND_COOLDOWN_SEC,
        **({"devCode": send_meta["devCode"]} if "devCode" in send_meta else {}),
        **({"warning": send_meta["warning"]} if send_meta.get("warning") else {}),
    }


def _mask(channel: Channel, target: str) -> str:
    if channel == "phone":
        return target[:3] + "****" + target[-4:]
    name, _, domain = target.partition("@")
    if len(name) <= 2:
        masked = name[0] + "*"
    else:
        masked = name[0] + "***" + name[-1]
    return f"{masked}@{domain}"


def _peek_pending(channel: Channel, target: str, purpose: Purpose, code: str) -> PendingCode:
    key = _pending_key(channel, target, purpose)
    pending = _pending.get(key)
    if not pending:
        raise ValueError(f"请先获取{'邮箱' if channel == 'email' else '手机'}验证码")
    if time.time() > pending.expires_at:
        _pending.pop(key, None)
        raise ValueError(f"{'邮箱' if channel == 'email' else '手机'}验证码已过期，请重新获取")
    if pending.attempts >= MAX_VERIFY_ATTEMPTS:
        _pending.pop(key, None)
        raise ValueError("验证失败次数过多，请重新获取验证码")
    if _hash_code(code.strip()) != pending.code_hash:
        pending.attempts += 1
        raise ValueError(f"{'邮箱' if channel == 'email' else '手机'}验证码不正确")
    return pending


def _consume_pending(channel: Channel, target: str, purpose: Purpose, code: str) -> None:
    _peek_pending(channel, target, purpose, code)
    _pending.pop(_pending_key(channel, target, purpose), None)
