from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from mawp.agents.base import AgentContext, AgentResult, ToolCallRecord
from mawp.agents.context_utils import format_context_rag_chunks
from mawp.agents.parsing import extract_json_object
from mawp.config.loader import AgentConfig
from mawp.llm.anthropic_adapter import AnthropicAdapter
from mawp.llm.base import LLMAdapter
from mawp.tools.registry import ToolRegistry
from mawp.tools.types import ToolCallContext

CODING_SYSTEM_PROMPT = """你是编码 Agent，负责在代码仓库中实现需求。

工作流程：
1. 阅读需求规格、设计摘要与代码库检索结果
2. 使用 read_file / list_dir / grep / glob_search 了解现有代码
3. 使用 write_file（新文件）或 edit_file（修改现有文件）完成实现
4. 完成后输出**唯一一份** JSON（不要 markdown 代码块）

JSON 字段（全部必填，数组可为空）：
{
  "change_plan": [
    {"path": "相对路径", "action": "create|modify", "summary": "改动说明"}
  ],
  "files_changed": ["相对路径"],
  "changelog": "面向人类的变更摘要"
}

规则：
- 只修改与任务相关的文件，不要改动无关文件
- 遵循项目既有风格与目录结构
- edit_file 的 old_string 必须与文件内容精确匹配
- 最终回复只能是 JSON 对象
"""


class ChangePlanItem(BaseModel):
    path: str
    action: str
    summary: str


class CodingResult(BaseModel):
    change_plan: list[ChangePlanItem] = Field(default_factory=list)
    files_changed: list[str] = Field(default_factory=list)
    changelog: str = ""


@dataclass
class CodingAgentContext(AgentContext):
    requirement_spec: dict[str, Any] = field(default_factory=dict)
    design_summary: dict[str, Any] = field(default_factory=dict)
    retry_feedback: dict[str, Any] = field(default_factory=dict)
    scope_files: list[str] | None = None
    deny_files: list[str] | None = None


def parse_coding_result(text: str) -> CodingResult:
    data = extract_json_object(text)
    return CodingResult.model_validate(data)


def build_coding_user_message(ctx: CodingAgentContext) -> str:
    parts: list[str] = []

    if ctx.rag_chunks:
        rag_text = format_context_rag_chunks(ctx.rag_chunks)
        if rag_text:
            parts.append(rag_text)

    if ctx.requirement_spec:
        parts.append(
            "## 需求规格\n"
            + json.dumps(ctx.requirement_spec, ensure_ascii=False, indent=2)
        )

    if ctx.design_summary:
        parts.append(
            "## 设计摘要\n"
            + json.dumps(ctx.design_summary, ensure_ascii=False, indent=2)
        )

    if ctx.retry_feedback:
        parts.append(
            "## 修复反馈（测试/审查失败，请针对性修复）\n"
            + json.dumps(ctx.retry_feedback, ensure_ascii=False, indent=2)
        )

    parts.append(f"## 编码任务\n{ctx.user_description}")
    return "\n\n".join(parts)


def files_changed_from_tools(tool_records: list[ToolCallRecord]) -> list[str]:
    changed: list[str] = []
    seen: set[str] = set()
    for record in tool_records:
        if not record.success or record.name not in {"write_file", "edit_file"}:
            continue
        path = None
        if isinstance(record.result, dict):
            path = record.result.get("path")
        path = path or record.arguments.get("path")
        if path and path not in seen:
            seen.add(str(path))
            changed.append(str(path))
    return changed


class CodingAgent:
    agent_type = "coding"

    def __init__(
        self,
        config: AgentConfig,
        tools: ToolRegistry,
        llm: LLMAdapter | None = None,
    ):
        self.config = config
        self.tools = tools
        self.llm = llm
        self.max_iterations = config.agents.coding.max_tool_iterations

    def run(self, ctx: CodingAgentContext) -> AgentResult:
        if self.llm is None:
            return self._run_heuristic(ctx)
        return self._run_with_llm(ctx)

    def _run_with_llm(self, ctx: CodingAgentContext) -> AgentResult:
        tool_records: list[ToolCallRecord] = []
        tokens_used = 0
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": build_coding_user_message(ctx)},
        ]
        tool_schemas = self.tools.schemas_for_agent(self.agent_type)
        is_anthropic = isinstance(self.llm, AnthropicAdapter)
        anthropic_tools = (
            AnthropicAdapter.tool_schemas_from_openai(tool_schemas)
            if is_anthropic
            else None
        )

        for _ in range(self.max_iterations):
            response = self.llm.chat_with_retry(
                messages,
                tools=anthropic_tools if is_anthropic else tool_schemas,
                system=CODING_SYSTEM_PROMPT,
                response_format={"type": "json_object"} if not is_anthropic else None,
            )
            tokens_used += response.usage.total_tokens

            if response.has_tool_calls:
                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": [
                        {
                            "id": call.id,
                            "name": call.name,
                            "arguments": call.arguments,
                        }
                        for call in response.tool_calls
                    ],
                }
                messages.append(assistant_msg)

                for call in response.tool_calls:
                    tool_ctx = ToolCallContext(
                        agent_name=self.agent_type,
                        session_id=ctx.session_id,
                        actor_id=ctx.actor_id,
                        scope_files=ctx.scope_files,
                        deny_files=ctx.deny_files,
                    )
                    result = self.tools.execute(call.name, call.arguments, tool_ctx)
                    tool_records.append(
                        ToolCallRecord(
                            name=call.name,
                            arguments=call.arguments,
                            success=result.success,
                            result=result.data,
                            error=result.error,
                            duration_ms=result.duration_ms,
                        )
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": json.dumps(
                                result.to_dict(), ensure_ascii=False, default=str
                            ),
                        }
                    )
                continue

            if not response.content:
                return AgentResult(
                    success=False,
                    tool_calls=tool_records,
                    tokens_used=tokens_used,
                    error="LLM 未返回内容",
                    agent_type=self.agent_type,
                )

            try:
                coding = parse_coding_result(response.content)
            except (ValueError, ValidationError, json.JSONDecodeError) as exc:
                messages.append({"role": "assistant", "content": response.content})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"输出格式无效（{exc}）。请仅返回符合 schema 的 JSON 对象。"
                        ),
                    }
                )
                continue

            output = coding.model_dump()
            tool_files = files_changed_from_tools(tool_records)
            if tool_files:
                output["files_changed"] = list(
                    dict.fromkeys((output.get("files_changed") or []) + tool_files)
                )
            if not output.get("change_plan") and output.get("files_changed"):
                output["change_plan"] = [
                    {
                        "path": path,
                        "action": "modify",
                        "summary": output.get("changelog") or "Agent 变更",
                    }
                    for path in output["files_changed"]
                ]

            return AgentResult(
                success=True,
                output=output,
                tool_calls=tool_records,
                tokens_used=tokens_used,
                agent_type=self.agent_type,
            )

        return AgentResult(
            success=False,
            tool_calls=tool_records,
            tokens_used=tokens_used,
            error=f"超过最大工具调用轮次 ({self.max_iterations})",
            agent_type=self.agent_type,
        )

    def _run_heuristic(self, ctx: CodingAgentContext) -> AgentResult:
        """无 LLM 时：在 related_files 或默认路径写入最小实现桩。"""
        tool_records: list[ToolCallRecord] = []
        tool_ctx = ToolCallContext(
            agent_name=self.agent_type,
            session_id=ctx.session_id,
            actor_id=ctx.actor_id,
            scope_files=ctx.scope_files,
            deny_files=ctx.deny_files,
        )

        related = list(ctx.requirement_spec.get("related_files") or [])
        target_path = related[0] if related else "src/agent_generated.py"
        summary = (
            ctx.requirement_spec.get("summary")
            or ctx.user_description
            or "Agent 生成实现"
        )
        action = "create"

        read_result = self.tools.execute(
            "read_file", {"path": target_path}, tool_ctx
        )
        if read_result.success:
            old_content = (read_result.data or {}).get("content") or ""
            marker = "# --- agent-generated ---"
            if marker not in old_content:
                new_content = old_content.rstrip() + f"\n\n{marker}\n# {summary}\n"
                write_result = self.tools.execute(
                    "write_file",
                    {"path": target_path, "content": new_content},
                    tool_ctx,
                )
                tool_records.extend(
                    [
                        ToolCallRecord(
                            name="read_file",
                            arguments={"path": target_path},
                            success=True,
                            result=read_result.data,
                        ),
                        ToolCallRecord(
                            name="write_file",
                            arguments={"path": target_path, "content": new_content},
                            success=write_result.success,
                            result=write_result.data,
                            error=write_result.error,
                            duration_ms=write_result.duration_ms,
                        ),
                    ]
                )
                action = "modify"
                if not write_result.success:
                    return AgentResult(
                        success=False,
                        tool_calls=tool_records,
                        error=write_result.error or "写入失败",
                        agent_type=self.agent_type,
                    )
            else:
                return AgentResult(
                    success=True,
                    output={
                        "change_plan": [],
                        "files_changed": [],
                        "changelog": f"文件 {target_path} 已含 agent 标记，未重复写入",
                    },
                    tool_calls=tool_records,
                    agent_type=self.agent_type,
                )
        else:
            content = (
                f'"""Agent 启发式生成 — {summary}"""\n\n'
                f"# TODO: 配置 LLM API Key 以启用完整编码 Agent\n\n"
                f"def agent_placeholder():\n"
                f'    """{summary}"""\n'
                f"    pass\n"
            )
            write_result = self.tools.execute(
                "write_file",
                {"path": target_path, "content": content},
                tool_ctx,
            )
            tool_records.append(
                ToolCallRecord(
                    name="write_file",
                    arguments={"path": target_path, "content": content},
                    success=write_result.success,
                    result=write_result.data,
                    error=write_result.error,
                    duration_ms=write_result.duration_ms,
                )
            )
            action = "create"
            if not write_result.success:
                return AgentResult(
                    success=False,
                    tool_calls=tool_records,
                    error=write_result.error or "写入失败",
                    agent_type=self.agent_type,
                )

        files = files_changed_from_tools(tool_records)
        if not files:
            return AgentResult(
                success=False,
                tool_calls=tool_records,
                error="启发式编码未能写入文件",
                agent_type=self.agent_type,
            )

        output = {
            "change_plan": [
                {
                    "path": files[0],
                    "action": action,
                    "summary": summary,
                }
            ],
            "files_changed": files,
            "changelog": f"启发式实现：{summary}（文件: {', '.join(files)}）",
        }
        return AgentResult(
            success=True,
            output=output,
            tool_calls=tool_records,
            agent_type=self.agent_type,
        )
