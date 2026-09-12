"""腾讯云实时语音识别：签名 URL 生成（密钥仅存服务端）。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import random
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode


def _load_backend_dotenv() -> None:
    """加载 backend/.env（不覆盖已有环境变量）。"""
    # .../backend/src/mawp/asr/tencent.py → backend
    backend_root = Path(__file__).resolve().parents[3]
    path = backend_root / ".env"
    if not path.is_file():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().lstrip("\ufeff")
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def get_tencent_asr_config() -> dict[str, str] | None:
    _load_backend_dotenv()
    secret_id = (os.environ.get("TENCENT_SECRET_ID") or "").strip()
    secret_key = (os.environ.get("TENCENT_SECRET_KEY") or "").strip()
    app_id = (os.environ.get("TENCENT_APP_ID") or "").strip()
    if not secret_id or not secret_key or not app_id:
        return None
    return {
        "secret_id": secret_id,
        "secret_key": secret_key,
        "app_id": app_id,
        "engine_model_type": (
            os.environ.get("TENCENT_ASR_ENGINE") or "16k_zh"
        ).strip(),
    }


def build_realtime_ws_url(*, voice_id: str | None = None) -> tuple[str, str]:
    """返回 (wss_url, voice_id)。"""
    cfg = get_tencent_asr_config()
    if not cfg:
        raise RuntimeError(
            "未配置腾讯云 ASR：请在 backend/.env 设置 "
            "TENCENT_SECRET_ID / TENCENT_SECRET_KEY / TENCENT_APP_ID"
        )

    app_id = cfg["app_id"]
    secret_id = cfg["secret_id"]
    secret_key = cfg["secret_key"]
    engine = cfg["engine_model_type"]
    vid = voice_id or uuid.uuid4().hex

    timestamp = int(time.time())
    expired = timestamp + 24 * 3600
    nonce = random.randint(100000, 9999999999)

    params: dict[str, Any] = {
        "engine_model_type": engine,
        "expired": expired,
        "needvad": 1,
        "vad_silence_time": 800,
        "nonce": nonce,
        "secretid": secret_id,
        "timestamp": timestamp,
        "voice_format": 1,  # pcm
        "voice_id": vid,
        "filter_dirty": 0,
        "filter_modal": 0,
        "filter_punc": 0,
        "convert_num_mode": 1,
    }

    # 签名原文：host/path?按字典序拼接参数（不含 signature）
    sorted_query = urlencode(sorted((str(k), str(v)) for k, v in params.items()))
    sign_str = f"asr.cloud.tencent.com/asr/v2/{app_id}?{sorted_query}"
    digest = hmac.new(
        secret_key.encode("utf-8"),
        sign_str.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    signature = base64.b64encode(digest).decode("utf-8")
    final_query = f"{sorted_query}&signature={quote(signature, safe='')}"
    url = f"wss://asr.cloud.tencent.com/asr/v2/{app_id}?{final_query}"
    return url, vid
