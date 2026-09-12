"""文生图代理：服务端拉取 Pollinations，避免浏览器跨域/墙导致加载失败。"""

from __future__ import annotations

import base64
import logging
import os
import random
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["image"])


class ImageGenBody(BaseModel):
    prompt: str = Field(min_length=1, max_length=1200)
    width: int = Field(default=1024, ge=256, le=1536)
    height: int = Field(default=1024, ge=256, le=1536)
    seed: int | None = None


def _pollinations_key() -> str:
    return (
        os.environ.get("POLLINATIONS_API_KEY", "").strip()
        or os.environ.get("VITE_POLLINATIONS_KEY", "").strip()
    )


def _candidate_urls(prompt: str, width: int, height: int, seed: int) -> list[str]:
    path = quote(prompt, safe="")
    key = _pollinations_key()
    urls: list[str] = []

    # 新端点（参数尽量精简，复杂参数易 502）
    qs_new = f"model=flux&width={width}&height={height}&nologo=true&seed={seed}"
    if key:
        qs_new += f"&key={quote(key)}"
    urls.append(f"https://gen.pollinations.ai/image/{path}?{qs_new}")

    # 旧端点兜底
    qs_old = f"width={width}&height={height}&nologo=true&seed={seed}"
    urls.append(f"https://image.pollinations.ai/prompt/{path}?{qs_old}")

    # 再试 turbo 类轻量模型名（部分区域更稳）
    qs_turbo = f"model=turbo&width={width}&height={height}&nologo=true&seed={seed}"
    if key:
        qs_turbo += f"&key={quote(key)}"
    urls.append(f"https://gen.pollinations.ai/image/{path}?{qs_turbo}")

    return urls


@router.get("/image/status")
def image_status() -> dict[str, Any]:
    return {
        "ok": True,
        "hasKey": bool(_pollinations_key()),
        "provider": "pollinations",
    }


@router.post("/image/generate")
async def image_generate(body: ImageGenBody) -> dict[str, Any]:
    prompt = body.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt 不能为空")

    seed = body.seed if body.seed is not None else random.randint(1, 1_000_000_000)
    width = body.width
    height = body.height
    last_err = "unknown"

    headers = {
        "User-Agent": "Mozilla/5.0 AgentFlow-ImageProxy/1.0",
        "Accept": "image/*,*/*",
    }
    key = _pollinations_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(90.0, connect=20.0),
        follow_redirects=True,
        headers=headers,
    ) as client:
        for url in _candidate_urls(prompt, width, height, seed):
            try:
                resp = await client.get(url)
                ctype = (resp.headers.get("content-type") or "").lower()
                if resp.status_code != 200:
                    last_err = f"HTTP {resp.status_code}"
                    continue
                data = resp.content
                if len(data) < 1200:
                    last_err = "响应过小"
                    continue
                if ctype and "image" not in ctype and "octet-stream" not in ctype:
                    # 偶发返回 HTML 错误页
                    last_err = f"非图片类型: {ctype}"
                    continue
                if not ctype or "octet-stream" in ctype:
                    ctype = "image/jpeg"
                b64 = base64.b64encode(data).decode("ascii")
                return {
                    "ok": True,
                    "dataUrl": f"data:{ctype};base64,{b64}",
                    "width": width,
                    "height": height,
                    "seed": seed,
                    "bytes": len(data),
                    "provider": "Pollinations",
                }
            except Exception as exc:  # noqa: BLE001
                last_err = str(exc)
                logger.warning("image generate candidate failed: %s", last_err)

    raise HTTPException(
        status_code=502,
        detail=f"图像生成失败（服务繁忙或网络不可达）：{last_err}",
    )
