from __future__ import annotations

import json
from typing import Any

import httpx

from mawp.llm.base import LLMAdapter
from mawp.llm.exceptions import LLMRequestError
from mawp.llm.types import LLMResponse, LLMToolCall, TokenUsage

DEFAULT_ANTHROPIC_BASE = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicAdapter(LLMAdapter):
    """Anthropic Messages API 兼容适配器（含 DeepSeek Anthropic 端点）。"""

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
        self.base_url = (base_url or DEFAULT_ANTHROPIC_BASE).rstrip("/")
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
        _ = response_format  # Anthropic 通过 prompt 约束 JSON 输出
        api_messages = self._to_anthropic_messages(messages)

        payload: dict[str, Any] = {
            "model": model or self.model,
            "max_tokens": 8192,
            "messages": api_messages,
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = tools

        url = f"{self.base_url}/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise LLMRequestError(f"Anthropic 请求失败: {exc}") from exc

        if response.status_code >= 400:
            raise LLMRequestError(
                f"Anthropic API 错误 ({response.status_code}): {response.text}",
                status_code=response.status_code,
            )

        data = response.json()
        content_parts: list[str] = []
        tool_calls: list[LLMToolCall] = []

        for block in data.get("content") or []:
            block_type = block.get("type")
            if block_type == "text":
                content_parts.append(str(block.get("text") or ""))
            elif block_type == "tool_use":
                tool_calls.append(
                    LLMToolCall(
                        id=str(block.get("id") or block.get("name")),
                        name=str(block.get("name") or ""),
                        arguments=dict(block.get("input") or {}),
                    )
                )

        return LLMResponse(
            content="".join(content_parts) or None,
            tool_calls=tool_calls,
            usage=TokenUsage.from_dict(data.get("usage")),
            raw=data,
        )

    @staticmethod
    def _to_anthropic_messages(
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        converted: list[dict[str, Any]] = []
        i = 0
        while i < len(messages):
            msg = messages[i]
            role = msg.get("role")
            if role == "system":
                i += 1
                continue

            if role == "tool":
                # Anthropic 要求同一轮 assistant tool_use 的所有 tool_result 必须在下一条 user 消息里
                tool_results: list[dict[str, Any]] = []
                while i < len(messages) and messages[i].get("role") == "tool":
                    tool_msg = messages[i]
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_msg.get("tool_call_id"),
                            "content": str(tool_msg.get("content") or ""),
                        }
                    )
                    i += 1
                converted.append({"role": "user", "content": tool_results})
                continue

            content = msg.get("content")
            if role == "assistant" and msg.get("tool_calls"):
                blocks: list[dict[str, Any]] = []
                if content:
                    blocks.append({"type": "text", "text": str(content)})
                for call in msg["tool_calls"]:
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": call.get("id"),
                            "name": call.get("name"),
                            "input": call.get("arguments") or {},
                        }
                    )
                converted.append({"role": "assistant", "content": blocks})
                i += 1
                continue

            converted.append({"role": role, "content": str(content or "")})
            i += 1
        return converted

    @staticmethod
    def tool_schemas_from_openai(schemas: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """将 OpenAI function schema 转为 Anthropic tools 格式。"""
        anthropic_tools: list[dict[str, Any]] = []
        for schema in schemas:
            fn = schema.get("function") or schema
            anthropic_tools.append(
                {
                    "name": fn["name"],
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters") or {"type": "object"},
                }
            )
        return anthropic_tools
