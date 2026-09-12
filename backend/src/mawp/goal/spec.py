from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from mawp.agents.parsing import extract_json_object
from mawp.config.loader import AgentConfig
from mawp.goal.models import PrdDocument, SpecDocument
from mawp.goal.store import GoalStore
from mawp.llm.base import LLMAdapter
from mawp.llm.factory import create_llm_adapter

SPEC_SYSTEM_PROMPT = """你是架构师 Agent，负责将 PRD 转化为可实施的技术 SPEC。

输出**唯一一份** JSON（不要 markdown 代码块）：
{
  "architecture": "架构设计说明（Markdown 段落）",
  "api_contracts": "API 契约说明，无则写「无 API 变更」",
  "data_model": "数据模型说明",
  "error_handling": "错误处理策略",
  "security": "安全策略",
  "testing_strategy": "测试策略",
  "implementation_plan": ["步骤1", "步骤2"]
}
"""


class SpecPayload(BaseModel):
    architecture: str = ""
    api_contracts: str = ""
    data_model: str = ""
    error_handling: str = ""
    security: str = ""
    testing_strategy: str = ""
    implementation_plan: list[str] = Field(default_factory=list)


class SpecService:
    """从 PRD 生成技术 SPEC。"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.store = GoalStore(config)

    def generate(self, slug: str) -> tuple[SpecDocument, str]:
        prd = self.store.load_prd(slug)
        if self.store.spec_exists(slug):
            raise FileExistsError(f"SPEC 已存在: {slug}.md")

        payload = self._design_spec(prd)
        doc = SpecDocument(
            slug=slug,
            title=prd.title,
            prd_ref=slug,
            architecture=payload.architecture,
            api_contracts=payload.api_contracts,
            data_model=payload.data_model,
            error_handling=payload.error_handling,
            security=payload.security,
            testing_strategy=payload.testing_strategy,
            implementation_plan=payload.implementation_plan,
        )
        path = self.store.save_spec(doc)
        return doc, str(path)

    def _design_spec(self, prd: PrdDocument) -> SpecPayload:
        llm = create_llm_adapter(self.config)
        if llm is None:
            return _heuristic_spec(prd)

        user_content = _build_spec_prompt(prd)
        response = llm.chat_with_retry(
            [{"role": "user", "content": user_content}],
            system=SPEC_SYSTEM_PROMPT,
            response_format={"type": "json_object"},
        )
        if not response.content:
            return _heuristic_spec(prd)

        try:
            data = extract_json_object(response.content)
            payload = SpecPayload.model_validate(data)
            if not payload.architecture and not payload.implementation_plan:
                return _heuristic_spec(prd)
            return payload
        except (ValueError, ValidationError, json.JSONDecodeError):
            return _heuristic_spec(prd)


def _build_spec_prompt(prd: PrdDocument) -> str:
    return (
        f"## PRD 标题\n{prd.title}\n\n"
        f"## 描述\n{prd.description}\n\n"
        f"## 目标\n" + "\n".join(f"- {g}" for g in prd.goals) + "\n\n"
        f"## 验收标准\n"
        + "\n".join(f"- {c}" for c in prd.acceptance_criteria)
        + "\n\n"
        f"## 影响模块\n"
        + "\n".join(f"- {m}" for m in prd.affected_modules)
        + "\n\n"
        f"## 关联文件\n"
        + "\n".join(f"- {f}" for f in prd.related_files)
    )


def _heuristic_spec(prd: PrdDocument) -> SpecPayload:
    modules = ", ".join(prd.affected_modules) or "核心模块"
    files = ", ".join(prd.related_files) or "待实现时确定"
    plan = [
        f"在 {modules} 中实现「{prd.title}」",
        "补充/更新单元测试",
        "运行 pytest 验证",
    ]
    if prd.related_files:
        plan.insert(1, f"主要修改文件: {files}")

    return SpecPayload(
        architecture=(
            f"在现有 {modules} 架构上增量实现。\n"
            f"- 保持与现有代码风格一致\n"
            f"- 优先修改: {files}"
        ),
        api_contracts="根据 PRD 验收标准定义接口，实现时补充具体签名。",
        data_model="复用现有数据模型，按需扩展字段。",
        error_handling="输入校验失败返回 4xx；内部错误记录日志并返回 5xx。",
        security="遵循项目既有鉴权机制；敏感信息不得硬编码。",
        testing_strategy="为新增逻辑编写 pytest 单元测试；验收标准逐条对应测试用例。",
        implementation_plan=plan,
    )
