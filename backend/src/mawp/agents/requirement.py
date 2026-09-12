from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from mawp.agents.base import AgentContext, AgentResult, ToolCallRecord
from mawp.agents.parsing import extract_json_object
from mawp.config.loader import AgentConfig
from mawp.llm.anthropic_adapter import AnthropicAdapter
from mawp.llm.base import LLMAdapter
from mawp.agents.context_utils import format_context_rag_chunks
from mawp.tools.registry import ToolRegistry
from mawp.tools.types import ToolCallContext

REQUIREMENT_SYSTEM_PROMPT = """你是需求理解 Agent，负责分析用户的软件开发需求。

工作流程：
1. 阅读用户消息中的「代码库检索结果」（若有），识别相关模块与文件
2. 必要时使用工具（list_dir、glob_search、grep、read_file）补充探索
3. 理解需求后，输出**唯一一份** JSON 需求规格（不要 markdown 代码块）

JSON 字段（全部必填，数组可为空）：
{
  "summary": "一句话摘要",
  "goals": ["业务目标"],
  "non_goals": ["明确不做的事"],
  "acceptance_criteria": ["可验证的验收标准"],
  "inputs_outputs": {"inputs": [], "outputs": []},
  "affected_modules": ["模块名"],
  "dependencies": ["依赖的系统/模块"],
  "risks": ["技术或业务风险"],
  "related_files": ["相对路径"],
  "open_questions": ["需用户澄清的问题，无则 []"],
  "tasks": [{"id": "T1", "title": "任务标题", "depends_on": []}]
}

规则：
- related_files 必须是仓库内相对路径
- 超大需求拆成多个 tasks，并标注 depends_on
- 有歧义时写入 open_questions，仍给出最佳猜测的 tasks
- 最终回复只能是 JSON 对象，不要有其他文字
"""


class TaskItem(BaseModel):
    id: str
    title: str
    depends_on: list[str] = Field(default_factory=list)


class RequirementSpec(BaseModel):
    summary: str
    goals: list[str] = Field(default_factory=list)
    non_goals: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    inputs_outputs: dict[str, Any] = Field(default_factory=dict)
    affected_modules: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    related_files: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    tasks: list[TaskItem] = Field(default_factory=list)


def parse_requirement_spec(text: str) -> RequirementSpec:
    data = extract_json_object(text)
    return RequirementSpec.model_validate(data)


def build_requirement_user_message(ctx: AgentContext) -> str:
    parts: list[str] = []
    if ctx.rag_chunks:
        rag_text = format_context_rag_chunks(ctx.rag_chunks)
        if rag_text:
            parts.append(rag_text)

    if ctx.prior_requirement_spec:
        parts.append(
            "## 上一轮需求规格\n"
            + json.dumps(ctx.prior_requirement_spec, ensure_ascii=False, indent=2)
        )

    if ctx.prior_requirement_spec:
        parts.append(f"## 本轮追加/修正\n{ctx.user_description}")
    else:
        parts.append(f"## 用户需求\n{ctx.user_description}")
    return "\n\n".join(parts)


class RequirementAgent:
    agent_type = "requirement"

    def __init__(
        self,
        config: AgentConfig,
        tools: ToolRegistry,
        llm: LLMAdapter | None = None,
    ):
        self.config = config
        self.tools = tools
        self.llm = llm
        self.max_iterations = config.agents.requirement.max_tool_iterations

    def run(self, ctx: AgentContext) -> AgentResult:
        if self.llm is None:
            return self._run_heuristic(ctx)

        tool_records: list[ToolCallRecord] = []
        tokens_used = 0
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": build_requirement_user_message(ctx)},
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
                system=REQUIREMENT_SYSTEM_PROMPT,
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
                spec = parse_requirement_spec(response.content)
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

            return AgentResult(
                success=True,
                output=spec.model_dump(),
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

    def _run_heuristic(self, ctx: AgentContext) -> AgentResult:
        """无 LLM 时的降级：探索仓库并生成最小需求规格。"""
        tool_records: list[ToolCallRecord] = []
        tool_ctx = ToolCallContext(
            agent_name=self.agent_type,
            session_id=ctx.session_id,
            actor_id=ctx.actor_id,
        )

        related_files: list[str] = []
        if ctx.rag_chunks:
            related_files = list(
                dict.fromkeys(
                    str(item.get("path"))
                    for item in ctx.rag_chunks
                    if item.get("path")
                )
            )[:8]

        if not related_files:
            for tool_name, arguments in (
                ("list_dir", {"path": ".", "recursive": False}),
                ("glob_search", {"pattern": "**/*.{py,ts,js,tsx,jsx,md,json,yml,yaml}"}),
            ):
                result = self.tools.execute(tool_name, arguments, tool_ctx)
                tool_records.append(
                    ToolCallRecord(
                        name=tool_name,
                        arguments=arguments,
                        success=result.success,
                        result=result.data,
                        error=result.error,
                        duration_ms=result.duration_ms,
                    )
                )
                if result.success and tool_name == "glob_search":
                    matches = (result.data or {}).get("matches") or []
                    related_files = [str(m) for m in matches[:8]]

        spec = RequirementSpec(
            summary=ctx.user_description,
            goals=[ctx.user_description],
            non_goals=["不在本次迭代范围内的新增模块"],
            acceptance_criteria=[
                f"实现: {ctx.user_description}",
                "相关单元测试通过",
                "不破坏现有功能",
            ],
            related_files=related_files,
            open_questions=["未配置 LLM API Key，当前为启发式需求分析"],
            risks=["启发式分析可能遗漏边界条件"],
            tasks=[
                TaskItem(
                    id="T1",
                    title=ctx.user_description,
                    depends_on=[],
                )
            ],
        )
        return AgentResult(
            success=True,
            output=spec.model_dump(),
            tool_calls=tool_records,
            agent_type=self.agent_type,
        )
