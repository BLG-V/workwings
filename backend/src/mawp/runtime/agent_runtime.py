from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from mawp.config.loader import AgentConfig
from mawp.llm.base import LLMAdapter
from mawp.llm.exceptions import LLMError
from mawp.llm.factory import create_llm_adapter
from mawp.runtime.json_util import extract_json_object
from mawp.runtime.spec import AgentSpec
from mawp.tools.registry import ToolRegistry
from mawp.tools.types import ToolCallContext


@dataclass
class RuntimeContext:
    session_id: str
    actor_id: str = "platform"


@dataclass
class AgentRunResult:
    """对齐 docs/interfaces/w1-api-onepager.md 的 AgentResult。"""

    success: bool
    output: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "tool_calls": list(self.tool_calls),
            "error": self.error,
            "usage": dict(self.usage or {}),
        }


class AgentRuntime:
    """通用 Agent 运行时：LLM + ToolRegistry 多轮 tool-calling。"""

    def __init__(
        self,
        config: AgentConfig,
        *,
        llm: LLMAdapter | None = None,
        registry: ToolRegistry | None = None,
    ):
        self.config = config
        self.registry = registry or ToolRegistry(config)
        self.llm = llm if llm is not None else create_llm_adapter(config)
        self._specs: dict[str, AgentSpec] = {}

    def register(self, spec: AgentSpec) -> None:
        self._specs[spec.name] = spec

    def get(self, name: str) -> AgentSpec | None:
        return self._specs.get(name)

    def run(
        self,
        spec_ref: str | AgentSpec,
        input_data: dict[str, Any] | str,
        ctx: RuntimeContext,
        *,
        model_override: str | None = None,
    ) -> AgentRunResult:
        if isinstance(spec_ref, AgentSpec):
            spec = spec_ref
        else:
            spec = self._specs.get(spec_ref)
            if spec is None:
                return AgentRunResult(
                    success=False,
                    error=f"未知 Agent: {spec_ref}",
                )

        if self.llm is None:
            return AgentRunResult(
                success=False,
                error="未配置 LLM（可用 mock provider 或设置 API Key）",
            )

        user_text = (
            input_data
            if isinstance(input_data, str)
            else str(input_data.get("text") or input_data.get("input") or input_data)
        )
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": user_text},
        ]
        tool_schemas = self._tool_schemas_for(spec)
        tool_records: list[dict[str, Any]] = []
        usage_acc: dict[str, Any] = {}
        # 有工具时勿强开 json_object（与 tool_calls 冲突）；无工具时可约束 JSON
        response_format = (
            {"type": "json_object"}
            if not tool_schemas and spec.output_schema is not None
            else None
        )
        effective_model = (
            None
            if spec.model == "mock"
            else (model_override or spec.model)
        )

        def _add_usage(response: Any) -> None:
            nonlocal usage_acc
            from mawp.runtime.cost_ledger import merge_usage, usage_dict_from_response

            u = getattr(response, "usage", None)
            if u is None:
                return
            piece = usage_dict_from_response(
                prompt_tokens=int(getattr(u, "prompt_tokens", 0) or 0),
                completion_tokens=int(getattr(u, "completion_tokens", 0) or 0),
                total_tokens=int(getattr(u, "total_tokens", 0) or 0),
                model=effective_model or spec.model,
            )
            usage_acc = merge_usage(usage_acc, piece)

        try:
            for step in range(spec.max_steps):
                response = self.llm.chat_with_retry(
                    messages,
                    tools=tool_schemas or None,
                    system=spec.system_prompt,
                    response_format=response_format,
                    model=effective_model,
                )
                _add_usage(response)

                if response.has_tool_calls:
                    messages.append(
                        {
                            "role": "assistant",
                            "content": response.content,
                            "tool_calls": [
                                {
                                    "id": tc.id,
                                    "type": "function",
                                    "function": {
                                        "name": tc.name,
                                        "arguments": json.dumps(
                                            tc.arguments, ensure_ascii=False
                                        ),
                                    },
                                }
                                for tc in response.tool_calls
                            ],
                        }
                    )
                    for tc in response.tool_calls:
                        record = self._run_one_tool(spec, tc.name, tc.arguments, ctx)
                        tool_records.append(record)
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "name": tc.name,
                                "content": json.dumps(
                                    {
                                        "success": record["success"],
                                        "data": record.get("result"),
                                        "error": record.get("error"),
                                    },
                                    ensure_ascii=False,
                                ),
                            }
                        )
                    if step == spec.max_steps - 1:
                        final = self._finalize_without_tools(
                            spec,
                            messages,
                            tool_records,
                            response_format=response_format,
                            model=effective_model,
                        )
                        from mawp.runtime.cost_ledger import merge_usage

                        final.usage = merge_usage(usage_acc, final.usage)
                        return final
                    continue

                text = (response.content or "").strip()
                parsed = extract_json_object(text)
                if parsed is not None:
                    return AgentRunResult(
                        success=True,
                        output=parsed,
                        tool_calls=tool_records,
                        usage=dict(usage_acc),
                    )
                return AgentRunResult(
                    success=True,
                    output={"text": text},
                    tool_calls=tool_records,
                    usage=dict(usage_acc),
                )
        except LLMError as exc:
            return AgentRunResult(
                success=False,
                output={"tool_summary": tool_records[-8:]},
                tool_calls=tool_records,
                error=str(exc),
                usage=dict(usage_acc),
            )

        return AgentRunResult(
            success=False,
            output={"tool_summary": tool_records[-8:]},
            tool_calls=tool_records,
            error=f"超过 max_steps={spec.max_steps}",
            usage=dict(usage_acc),
        )

    def _finalize_without_tools(
        self,
        spec: AgentSpec,
        messages: list[dict[str, Any]],
        tool_records: list[dict[str, Any]],
        *,
        response_format: dict[str, Any] | None,
        model: str | None = None,
    ) -> AgentRunResult:
        """max_steps 用尽仍在调工具时：禁止工具，强制输出最终 JSON。"""
        messages.append(
            {
                "role": "user",
                "content": "禁止再调用工具。根据已完成的工具结果，只输出最终 JSON。",
            }
        )
        finalize_format = response_format or (
            {"type": "json_object"} if spec.output_schema is not None else None
        )
        use_model = model if model is not None else (
            None if spec.model == "mock" else spec.model
        )
        try:
            response = self.llm.chat_with_retry(
                messages,
                tools=None,
                system=spec.system_prompt,
                response_format=finalize_format,
                model=use_model,
            )
        except LLMError as exc:
            return AgentRunResult(
                success=False,
                output={"tool_summary": tool_records[-8:]},
                tool_calls=tool_records,
                error=str(exc),
            )
        from mawp.runtime.cost_ledger import usage_dict_from_response

        u = getattr(response, "usage", None)
        usage = usage_dict_from_response(
            prompt_tokens=int(getattr(u, "prompt_tokens", 0) or 0) if u else 0,
            completion_tokens=int(getattr(u, "completion_tokens", 0) or 0) if u else 0,
            total_tokens=int(getattr(u, "total_tokens", 0) or 0) if u else 0,
            model=use_model or (None if spec.model == "mock" else spec.model),
        )
        if response.has_tool_calls:
            return AgentRunResult(
                success=False,
                output={"tool_summary": tool_records[-8:]},
                tool_calls=tool_records,
                error=f"超过 max_steps={spec.max_steps}",
                usage=usage,
            )
        text = (response.content or "").strip()
        parsed = extract_json_object(text)
        if parsed is not None:
            return AgentRunResult(
                success=True,
                output=parsed,
                tool_calls=tool_records,
                usage=usage,
            )
        if text:
            return AgentRunResult(
                success=True,
                output={"text": text},
                tool_calls=tool_records,
                usage=usage,
            )
        return AgentRunResult(
            success=False,
            output={"tool_summary": tool_records[-8:]},
            tool_calls=tool_records,
            error=f"超过 max_steps={spec.max_steps}",
            usage=usage,
        )

    def _tool_schemas_for(self, spec: AgentSpec) -> list[dict[str, Any]]:
        if not spec.tools:
            return []
        allowed = set(spec.tools)
        schemas: list[dict[str, Any]] = []
        for tool in self.registry.list_tools():
            if tool.name in allowed:
                schemas.append(tool.to_openai_schema())
        return schemas

    def _run_one_tool(
        self,
        spec: AgentSpec,
        tool_name: str,
        arguments: dict[str, Any],
        ctx: RuntimeContext,
    ) -> dict[str, Any]:
        if tool_name not in spec.tools:
            return {
                "name": tool_name,
                "arguments": arguments,
                "success": False,
                "result": None,
                "error": f"工具不在 Agent 白名单: {tool_name}",
                "duration_ms": 0,
            }

        call_ctx = ToolCallContext(
            agent_name=spec.name,
            session_id=ctx.session_id,
            actor_id=ctx.actor_id,
        )
        result = self.registry.execute(tool_name, arguments, call_ctx)
        return {
            "name": tool_name,
            "arguments": arguments,
            "success": result.success,
            "result": result.data,
            "error": result.error,
            "duration_ms": result.duration_ms,
        }
