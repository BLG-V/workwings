from __future__ import annotations

import re

from mawp.config.loader import AgentConfig
from mawp.goal.deps import DependencyCycleError, validate_dag
from mawp.goal.models import IssueDocument, IssueStatus, PrdDocument, SpecDocument
from mawp.goal.slug import make_slug
from mawp.goal.store import GoalStore


class IssuesService:
    """将 PRD/SPEC 拆解为 Issue 卡片。"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.store = GoalStore(config)

    def generate_from_slug(self, slug: str) -> tuple[list[IssueDocument], list[str]]:
        prd = self.store.load_prd(slug)
        spec: SpecDocument | None = None
        if self.store.spec_exists(slug):
            spec = self.store.load_spec(slug)
        return self._generate(prd, spec)

    def generate_continue(self, slug: str) -> tuple[list[IssueDocument], list[str]]:
        """增量追加：仅为尚未拆解的实施步骤创建新 Issue（CM-004 / E2E-03）。"""
        if not self.store.prd_exists(slug):
            raise FileNotFoundError(f"PRD 不存在: {slug}")

        prd = self.store.load_prd(slug)
        spec: SpecDocument | None = None
        if self.store.spec_exists(slug):
            spec = self.store.load_spec(slug)

        existing = _issues_for_slug(self.store, slug)
        existing_titles = {issue.title for issue in existing}
        tasks = _build_tasks(prd, spec)
        if not tasks:
            return [], []

        new_tasks = [task for task in tasks if task["title"] not in existing_titles]
        if not new_tasks:
            return [], []

        task_id_map = _build_task_id_map(tasks, existing)
        tail = existing[-1] if existing else None

        docs: list[IssueDocument] = []
        for task in new_tasks:
            issue_id = self.store.next_issue_id()
            mapped_deps = [
                task_id_map[dep]
                for dep in task.get("depends_on", [])
                if dep in task_id_map
            ]
            if not mapped_deps and tail is not None:
                mapped_deps = [tail.id]

            doc = IssueDocument(
                id=issue_id,
                title=task["title"],
                description=task.get("description") or task["title"],
                status=IssueStatus.OPEN,
                priority="P1",
                depends_on=mapped_deps,
                acceptance_criteria=task.get("acceptance_criteria")
                or prd.acceptance_criteria[:3]
                or ["功能实现完成", "测试通过"],
                verify_command=_default_verify_command(self.config),
                scope_files=task.get("scope_files") or prd.related_files or [],
                prd_ref=prd.slug,
                spec_ref=prd.slug if spec else "—",
            )
            docs.append(doc)
            task_id = task.get("task_id")
            if task_id:
                task_id_map[task_id] = issue_id
            tail = doc

        validate_dag(existing + docs)

        paths: list[str] = []
        for doc in docs:
            path = self.store.save_issue(doc)
            paths.append(str(path))
        return docs, paths

    def generate_quick(self, description: str) -> tuple[IssueDocument, str]:
        """快速通道：跳过 PRD/SPEC，直接创建单个 Issue。"""
        issue_id = self.store.next_issue_id()
        slug = make_slug(description)
        verify = _default_verify_command(self.config)
        scope = _guess_scope_files(description)

        doc = IssueDocument(
            id=issue_id,
            title=description[:80],
            description=description,
            status=IssueStatus.OPEN,
            priority="P0",
            acceptance_criteria=[
                description,
                "相关测试通过",
            ],
            verify_command=verify,
            scope_files=scope,
            prd_ref="—",
            spec_ref="—",
        )
        path = self.store.save_issue(doc)
        return doc, str(path)

    def _generate(
        self,
        prd: PrdDocument,
        spec: SpecDocument | None,
    ) -> tuple[list[IssueDocument], list[str]]:
        existing = {issue.id for issue in self.store.list_issues()}
        tasks = _build_tasks(prd, spec)
        if not tasks:
            tasks = [
                {
                    "title": prd.title,
                    "description": prd.description,
                    "acceptance_criteria": prd.acceptance_criteria,
                    "depends_on": [],
                    "scope_files": prd.related_files,
                }
            ]

        docs: list[IssueDocument] = []
        id_map: dict[str, str] = {}

        for index, task in enumerate(tasks, start=1):
            issue_id = f"GW-{index:03d}"
            while issue_id in existing:
                index += 1
                issue_id = f"GW-{index:03d}"

            mapped_deps = [
                id_map.get(dep, dep) for dep in task.get("depends_on", [])
            ]
            doc = IssueDocument(
                id=issue_id,
                title=task["title"],
                description=task.get("description") or task["title"],
                status=IssueStatus.OPEN,
                priority="P0" if index == 1 else "P1",
                depends_on=mapped_deps,
                acceptance_criteria=task.get("acceptance_criteria")
                or prd.acceptance_criteria[:3]
                or ["功能实现完成", "测试通过"],
                verify_command=_default_verify_command(self.config),
                scope_files=task.get("scope_files") or prd.related_files or [],
                prd_ref=prd.slug,
                spec_ref=prd.slug if spec else "—",
            )
            docs.append(doc)
            id_map[task.get("task_id", f"T{index}")] = issue_id
            existing.add(issue_id)

        try:
            docs = validate_dag(docs)
        except (DependencyCycleError, ValueError):
            raise

        paths = []
        for doc in docs:
            path = self.store.save_issue(doc)
            paths.append(str(path))

        return docs, paths

    def list_open_issues(self) -> list[IssueDocument]:
        return [
            issue
            for issue in self.store.list_issues()
            if issue.status in (IssueStatus.OPEN, IssueStatus.IN_PROGRESS)
        ]


def _issues_for_slug(store: GoalStore, slug: str) -> list[IssueDocument]:
    return sorted(
        [
            issue
            for issue in store.list_issues()
            if issue.prd_ref == slug
            or (
                issue.spec_ref
                and issue.spec_ref not in {"—", "-"}
                and issue.spec_ref == slug
            )
        ],
        key=lambda issue: issue.id,
    )


def _build_task_id_map(
    tasks: list[dict],
    existing: list[IssueDocument],
) -> dict[str, str]:
    by_title = {issue.title: issue.id for issue in existing}
    id_map: dict[str, str] = {}
    for task in tasks:
        task_id = task.get("task_id")
        if not task_id:
            continue
        title = task["title"]
        if title in by_title:
            id_map[task_id] = by_title[title]
    return id_map


def _build_tasks(
    prd: PrdDocument,
    spec: SpecDocument | None,
) -> list[dict]:
    tasks: list[dict] = []

    if spec and spec.implementation_plan:
        prev_id: str | None = None
        for index, step in enumerate(spec.implementation_plan, start=1):
            task_id = f"T{index}"
            depends = [prev_id] if prev_id else []
            tasks.append(
                {
                    "task_id": task_id,
                    "title": step,
                    "description": step,
                    "acceptance_criteria": [step, "测试通过"],
                    "depends_on": depends,
                    "scope_files": prd.related_files,
                }
            )
            prev_id = task_id
        return tasks

    if len(prd.acceptance_criteria) > 1:
        prev_id = None
        for index, criterion in enumerate(prd.acceptance_criteria, start=1):
            task_id = f"T{index}"
            depends = [prev_id] if prev_id else []
            tasks.append(
                {
                    "task_id": task_id,
                    "title": criterion[:80],
                    "description": criterion,
                    "acceptance_criteria": [criterion],
                    "depends_on": depends,
                    "scope_files": prd.related_files,
                }
            )
            prev_id = task_id
        return tasks

    return []


def _default_verify_command(config: AgentConfig) -> str:
    workspace = config.workspace_path()
    if (workspace / "pyproject.toml").is_file():
        return "pytest -q"
    if (workspace / "package.json").is_file():
        return "npm test"
    return "pytest -q"


def _guess_scope_files(description: str) -> list[str]:
    patterns = [
        r"([\w./-]+\.py)",
        r"([\w./-]+\.ts)",
        r"([\w./-]+\.tsx)",
    ]
    found: list[str] = []
    for pattern in patterns:
        for match in re.findall(pattern, description):
            if match not in found:
                found.append(match)
    return found[:5]
