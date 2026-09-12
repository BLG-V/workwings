from __future__ import annotations

import json
from typing import Any

from mawp.llm.base import LLMAdapter
from mawp.llm.types import LLMResponse, LLMToolCall, TokenUsage


class MockLLMAdapter(LLMAdapter):
    """测试用 LLM 适配器，按队列返回预设响应。"""

    def __init__(self, responses: list[LLMResponse] | None = None):
        self.responses = list(responses or [])
        self.calls: list[dict[str, Any]] = []

    def enqueue(self, response: LLMResponse) -> None:
        self.responses.append(response)

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        system: str | None = None,
        response_format: dict[str, Any] | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        self.calls.append(
            {
                "messages": messages,
                "tools": tools,
                "system": system,
                "response_format": response_format,
                "model": model,
            }
        )
        if self.responses:
            return self.responses.pop(0)
        system = system or ""
        if "任务规划 Agent" in system:
            return self.json_response(
                {
                    "tasks": [
                        {"id": "T1", "title": "implement", "depends_on": []},
                    ],
                    "status": "ok",
                    "count": 1,
                }
            )
        if "需求分析 Agent" in system:
            return self._default_requirement_response(messages)
        if "编码 Agent" in system:
            return self._default_coding_response(messages)
        if "前端 Agent" in system:
            return self.json_response(
                {
                    "status": "ok",
                    "frontend_dir": "frontend",
                    "pages": [{"path": "frontend/index.html", "title": "Status"}],
                    "artifacts": ["frontend/index.html"],
                    "ui_key_points": [],
                }
            )
        if "测试 Agent" in system:
            return self.json_response(
                {
                    "passed": True,
                    "status": "pass",
                    "failures": [],
                    "log_summary": "mock testing pass",
                    "attempt": 1,
                }
            )
        if "调试 Agent" in system:
            return self.json_response(
                {
                    "status": "ok",
                    "fixed": True,
                    "based_on_failures": [],
                    "note": "mock debug",
                    "changed_files": [],
                }
            )
        if "审查 Agent" in system:
            return self.json_response(
                {"status": "pass", "blocking_count": 0, "findings": []}
            )
        if "交付 Agent" in system:
            return self.json_response(
                {
                    "status": "ok",
                    "delivery_notes": "mock ship",
                    "auto_push": False,
                    "auto_merge": False,
                }
            )
        if "编码 Agent" in system or "编码任务" in str(messages):
            return self._default_coding_response(messages)
        return self._default_requirement_response(messages)

    @staticmethod
    def _default_requirement_response(messages: list[dict[str, Any]]) -> LLMResponse:
        description = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = str(msg.get("content") or "")
                if "## 用户需求" in content:
                    description = content.split("## 用户需求", 1)[-1].strip()
                else:
                    description = content
                break

        spec = {
            "summary": description,
            "goals": [description] if description else [],
            "non_goals": [],
            "acceptance_criteria": ["功能按需求描述实现", "相关测试通过"],
            "inputs_outputs": {},
            "affected_modules": [],
            "dependencies": [],
            "risks": [],
            "related_files": [],
            "open_questions": [],
            "tasks": [
                {
                    "id": "T1",
                    "title": description or "实现需求",
                    "depends_on": [],
                }
            ],
        }
        return LLMResponse(
            content=json.dumps(spec, ensure_ascii=False),
            usage=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        )

    @staticmethod
    def _default_coding_response(messages: list[dict[str, Any]]) -> LLMResponse:
        task = "编码任务"
        for msg in reversed(messages):
            if msg.get("role") == "user" and "## 编码任务" in str(msg.get("content") or ""):
                task = str(msg.get("content") or "").split("## 编码任务", 1)[-1].strip()
                break
        payload = {
            "status": "ok",
            "changed_files": ["src/mawp_coding_stub.py"],
            "tasks_done": ["T1"],
            "api_contract": {"endpoints": []},
            "change_plan": [],
            "files_changed": ["src/mawp_coding_stub.py"],
            "changelog": f"Mock 编码完成：{task[:80]}",
        }
        return LLMResponse(
            content=json.dumps(payload, ensure_ascii=False),
            usage=TokenUsage(prompt_tokens=10, completion_tokens=15, total_tokens=25),
        )

    @staticmethod
    def _default_review_response() -> LLMResponse:
        payload = {
            "issues": [],
            "summary": "Mock 审查通过，未发现 blocking 问题",
        }
        return LLMResponse(
            content=json.dumps(payload, ensure_ascii=False),
            usage=TokenUsage(prompt_tokens=8, completion_tokens=12, total_tokens=20),
        )

    @staticmethod
    def tool_call_response(
        tool_call_id: str,
        name: str,
        arguments: dict[str, Any],
    ) -> LLMResponse:
        return LLMResponse(
            tool_calls=[
                LLMToolCall(id=tool_call_id, name=name, arguments=arguments)
            ],
            usage=TokenUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
        )

    @staticmethod
    def json_response(payload: dict[str, Any]) -> LLMResponse:
        return LLMResponse(
            content=json.dumps(payload, ensure_ascii=False),
            usage=TokenUsage(prompt_tokens=5, completion_tokens=15, total_tokens=20),
        )
