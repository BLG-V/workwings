from __future__ import annotations

import hashlib
import re
import unicodedata


_KEYWORD_MAP: dict[str, str] = {
    "登录": "login",
    "注册": "register",
    "用户": "user",
    "邮箱": "email",
    "验证码": "verification-code",
    "认证": "auth",
    "鉴权": "auth",
    "jwt": "jwt",
    "api": "api",
    "模块": "module",
    "测试": "test",
    "修复": "fix",
    "bug": "bug",
}


def make_slug(text: str, *, max_len: int = 48) -> str:
    """从功能描述生成 URL 友好 slug。"""
    lowered = text.lower().strip()
    parts: list[str] = []

    for keyword, token in _KEYWORD_MAP.items():
        if keyword in text or keyword in lowered:
            if token not in parts:
                parts.append(token)

    ascii_slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    if ascii_slug and len(ascii_slug) >= 3:
        parts.append(ascii_slug)

    if parts:
        slug = "-".join(parts)
        slug = re.sub(r"-{2,}", "-", slug).strip("-")
        return slug[:max_len]

    normalized = unicodedata.normalize("NFKD", text)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_slug = re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")
    if ascii_slug and len(ascii_slug) >= 3:
        return ascii_slug[:max_len]

    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    return f"feature-{digest}"
