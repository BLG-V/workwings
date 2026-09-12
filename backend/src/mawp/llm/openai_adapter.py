from __future__ import annotations

import json
from typing import Any

import httpx

from mawp.llm.base import LLMAdapter
from mawp.llm.exceptions import LLMRequestError
from mawp.llm.types import LLMResponse, LLMToolCall, TokenUsage

DEFAULT_OPENAI_BASE = "https://api.openai.com/v1"


class OpenAIAdapter(LLMAdapter):
    """OpenAI Chat Completions 兼容适配器（含 DeepSeek OpenAI 端点）。"""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str | None = None,
        timeout: float = 120.0,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = (base_url or DEFAULT_OPENAI_BASE).rstrip("/")
        self.timeout = timeout

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        system: str | None = None,
        response_format: dict[str, Any] | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        payload_messages = list(messages)
        if system and (
            not payload_messages or payload_messages[0].get("role") != "system"
        ):
            payload_messages = [{"role": "system", "content": system}, *payload_messages]

        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": payload_messages,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        if response_format:
            payload["response_format"] = response_format

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise LLMRequestError(f"OpenAI 请求失败: {exc}") from exc

        if response.status_code >= 400:
            raise LLMRequestError(
                f"OpenAI API 错误 ({response.status_code}): {response.text}",
                status_code=response.status_code,
            )

        data = response.json()
        choice = data["choices"][0]
        message = choice.get("message") or {}
        tool_calls: list[LLMToolCall] = []

        for raw_call in message.get("tool_calls") or []:
            fn = raw_call.get("function") or {}
            args_raw = fn.get("arguments") or "{}"
            try:
                arguments = json.loads(args_raw)
            except json.JSONDecodeError:
                arguments = {"raw": args_raw}
            tool_calls.append(
                LLMToolCall(
                    id=str(raw_call.get("id") or fn.get("name")),
                    name=str(fn.get("name") or ""),
                    arguments=arguments if isinstance(arguments, dict) else {},
                )
            )

        return LLMResponse(
            content=message.get("content"),
            tool_calls=tool_calls,
            usage=TokenUsage.from_dict(data.get("usage")),
            raw=data,
        )
