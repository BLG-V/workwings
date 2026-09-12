from __future__ import annotations

from mawp.agents.base import AgentContext
from mawp.agents.requirement import RequirementAgent, RequirementSpec
from mawp.config.loader import AgentConfig
from mawp.goal.models import PrdDocument
from mawp.goal.slug import make_slug
from mawp.goal.store import GoalStore
from mawp.llm.factory import create_llm_adapter
from mawp.rag.service import RAGService
from mawp.tools.registry import ToolRegistry


class PrdService:
    """生成 PRD 文档。"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.store = GoalStore(config)
        self.tools = ToolRegistry(config)

    def generate(
        self,
        description: str,
        *,
        slug: str | None = None,
    ) -> tuple[PrdDocument, str]:
        resolved_slug = slug or make_slug(description)
        if self.store.prd_exists(resolved_slug):
            raise FileExistsError(
                f"PRD 已存在: {resolved_slug}.md（使用 --slug 指定其他名称）"
            )

        spec = self._analyze_requirement(description)
        doc = _spec_to_prd(resolved_slug, description, spec)
        path = self.store.save_prd(doc)
        return doc, str(path)

    def _analyze_requirement(self, description: str) -> RequirementSpec:
        llm = create_llm_adapter(self.config)
        agent = RequirementAgent(self.config, self.tools, llm=llm)

        rag_chunks: list[dict] = []
        try:
            rag = RAGService(self.config)
            if rag.is_indexed():
                rag_chunks = [
                    chunk.to_dict()
                    for chunk in rag.retrieve_chunks(description)
                ]
        except Exception:
            rag_chunks = []

        ctx = AgentContext(
            session_id="goal-prd",
            user_description=description,
            workspace=self.config.workspace_path(),
            rag_chunks=rag_chunks,
        )
        result = agent.run(ctx)
        if not result.success or not result.output:
            raise RuntimeError(result.error or "需求分析失败")

        return RequirementSpec.model_validate(result.output)


def _spec_to_prd(
    slug: str,
    description: str,
    spec: RequirementSpec,
) -> PrdDocument:
    acceptance = spec.acceptance_criteria or [
        "功能按需求描述实现",
        "相关测试通过",
    ]
    functional = list(acceptance)
    if spec.tasks:
        for task in spec.tasks:
            title = task.title if hasattr(task, "title") else task.get("title", "")
            if title and title not in functional:
                functional.append(title)

    user_stories = [
        f"作为用户，我希望{goal}，以便达成业务目标"
        for goal in (spec.goals or [spec.summary or description])
    ]

    nfr: list[str] = []
    if spec.dependencies:
        nfr.append(f"依赖: {', '.join(spec.dependencies)}")
    nfr.extend(f"风险: {risk}" for risk in spec.risks[:5])
    if not nfr:
        nfr = ["性能与安全性须满足项目基线要求"]

    return PrdDocument(
        slug=slug,
        title=spec.summary or description,
        description=description,
        goals=spec.goals or [spec.summary or description],
        non_goals=spec.non_goals or ["不在本次需求范围内的功能"],
        user_stories=user_stories,
        functional_requirements=functional,
        non_functional_requirements=nfr,
        acceptance_criteria=acceptance,
        open_questions=spec.open_questions,
        affected_modules=spec.affected_modules,
        risks=spec.risks,
        related_files=spec.related_files,
    )
