"""图形验证码（SVG，无第三方依赖）。"""

from __future__ import annotations

import random
import time
import uuid
from typing import Any

CAPTCHA_TTL_SEC = 300
_captchas: dict[str, dict[str, Any]] = {}

_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _prune() -> None:
    now = time.time()
    dead = [k for k, v in _captchas.items() if float(v.get("expiresAt") or 0) < now]
    for k in dead:
        _captchas.pop(k, None)


def create_captcha() -> dict[str, str]:
    _prune()
    code = "".join(random.choice(_CHARS) for _ in range(4))
    captcha_id = uuid.uuid4().hex
    _captchas[captcha_id] = {
        "code": code.upper(),
        "expiresAt": time.time() + CAPTCHA_TTL_SEC,
    }
    return {"captchaId": captcha_id, "imageSvg": _svg(code)}


def verify_captcha(captcha_id: str, answer: str, *, consume: bool = True) -> bool:
    _prune()
    item = _captchas.get(captcha_id)
    if not item:
        return False
    ok = str(answer or "").strip().upper() == str(item.get("code") or "")
    if consume or ok:
        _captchas.pop(captcha_id, None)
    return ok


def _svg(code: str) -> str:
    # 简单干扰线 + 旋转字符
    w, h = 120, 40
    lines = []
    for _ in range(4):
        x1, y1 = random.randint(0, w), random.randint(0, h)
        x2, y2 = random.randint(0, w), random.randint(0, h)
        color = f"rgb({random.randint(160,210)},{random.randint(160,210)},{random.randint(160,210)})"
        lines.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1"/>'
        )
    texts = []
    for i, ch in enumerate(code):
        x = 18 + i * 24
        y = random.randint(26, 32)
        rot = random.randint(-28, 28)
        color = f"rgb({random.randint(30,90)},{random.randint(30,90)},{random.randint(30,90)})"
        texts.append(
            f'<text x="{x}" y="{y}" fill="{color}" font-size="22" font-family="monospace" '
            f'font-weight="700" transform="rotate({rot} {x} {y})">{ch}</text>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f'<rect width="100%" height="100%" rx="8" fill="#f3f4f6"/>'
        + "".join(lines)
        + "".join(texts)
        + "</svg>"
    )
