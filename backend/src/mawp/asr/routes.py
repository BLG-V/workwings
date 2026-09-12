"""实时 ASR WebSocket：前端 ↔ 本服务 ↔ 腾讯云。"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from websockets.asyncio.client import connect as ws_connect
from websockets.exceptions import ConnectionClosed

from mawp.asr.tencent import build_realtime_ws_url, get_tencent_asr_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["asr"])


@router.get("/asr/status")
def asr_status() -> dict[str, Any]:
    cfg = get_tencent_asr_config()
    return {
        "configured": bool(cfg),
        "engine": (cfg or {}).get("engine_model_type", "16k_zh"),
        "provider": "tencent",
    }


@router.websocket("/asr/realtime")
async def asr_realtime(client: WebSocket) -> None:
    await client.accept()

    if not get_tencent_asr_config():
        await client.send_json(
            {
                "type": "error",
                "message": "服务端未配置腾讯云语音识别（TENCENT_*）",
            }
        )
        await client.close(code=1013)
        return

    try:
        tencent_url, voice_id = build_realtime_ws_url()
    except Exception as exc:  # noqa: BLE001
        await client.send_json({"type": "error", "message": str(exc)})
        await client.close(code=1011)
        return

    try:
        async with ws_connect(
            tencent_url,
            open_timeout=15,
            max_size=8 * 1024 * 1024,
        ) as upstream:
            # 握手确认
            raw = await asyncio.wait_for(upstream.recv(), timeout=10)
            handshake = json.loads(raw) if isinstance(raw, str) else json.loads(raw.decode())
            if handshake.get("code", -1) != 0:
                await client.send_json(
                    {
                        "type": "error",
                        "message": handshake.get("message") or "腾讯云握手失败",
                        "code": handshake.get("code"),
                    }
                )
                await client.close(code=1011)
                return

            await client.send_json(
                {
                    "type": "ready",
                    "voice_id": voice_id,
                    "message": "ok",
                }
            )

            stop = asyncio.Event()

            async def client_to_upstream() -> None:
                bytes_in = 0
                try:
                    while not stop.is_set():
                        msg = await client.receive()
                        if msg.get("type") == "websocket.disconnect":
                            break
                        if msg.get("bytes") is not None:
                            chunk = msg["bytes"]
                            bytes_in += len(chunk)
                            await upstream.send(chunk)
                            # 用 warning 确保默认日志可见
                            if bytes_in <= len(chunk) or bytes_in % 16000 < len(chunk):
                                logger.warning("asr audio bytes_in=%s", bytes_in)
                        elif msg.get("text") is not None:
                            text = msg["text"]
                            try:
                                data = json.loads(text)
                            except json.JSONDecodeError:
                                data = None
                            if isinstance(data, dict) and data.get("type") == "end":
                                logger.warning(
                                    "asr client end, total_audio_bytes=%s", bytes_in
                                )
                                await upstream.send(json.dumps({"type": "end"}))
                            else:
                                await upstream.send(text)
                except WebSocketDisconnect:
                    logger.warning("asr client disconnect, bytes_in=%s", bytes_in)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("client_to_upstream: %s", exc)
                finally:
                    stop.set()
                    try:
                        await upstream.send(json.dumps({"type": "end"}))
                    except Exception:  # noqa: BLE001
                        pass

            async def upstream_to_client() -> None:
                try:
                    async for raw in upstream:
                        if stop.is_set():
                            break
                        payload = (
                            json.loads(raw)
                            if isinstance(raw, str)
                            else json.loads(raw.decode())
                        )
                        code = payload.get("code", 0)
                        if code != 0:
                            await client.send_json(
                                {
                                    "type": "error",
                                    "message": payload.get("message") or "识别错误",
                                    "code": code,
                                }
                            )
                            break

                        if payload.get("final") == 1:
                            await client.send_json({"type": "done"})
                            break

                        result = payload.get("result") or {}
                        text = str(result.get("voice_text_str") or "").strip()
                        slice_type = result.get("slice_type")
                        logger.warning(
                            "asr result slice=%s text=%r",
                            slice_type,
                            text[:80],
                        )
                        if not text and slice_type not in (0, 1, 2):
                            continue
                        msg_type = "final" if slice_type == 2 else "partial"
                        await client.send_json(
                            {
                                "type": msg_type,
                                "text": text,
                                "slice_type": slice_type,
                                "index": result.get("index"),
                            }
                        )
                except ConnectionClosed:
                    pass
                except Exception as exc:  # noqa: BLE001
                    logger.warning("upstream_to_client: %s", exc)
                    try:
                        await client.send_json(
                            {"type": "error", "message": f"上游断开：{exc}"}
                        )
                    except Exception:  # noqa: BLE001
                        pass
                finally:
                    stop.set()

            await asyncio.gather(client_to_upstream(), upstream_to_client())
    except Exception as exc:  # noqa: BLE001
        logger.exception("tencent asr proxy failed")
        try:
            await client.send_json(
                {"type": "error", "message": f"无法连接腾讯云：{exc}"}
            )
        except Exception:  # noqa: BLE001
            pass
    finally:
        try:
            await client.close()
        except Exception:  # noqa: BLE001
            pass
