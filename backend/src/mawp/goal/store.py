from __future__ import annotations

import re
from pathlib import Path

from mawp.config.loader import AgentConfig
from mawp.goal.models import IssueDocument, IssueStatus, PrdDocument, SpecDocument
from mawp.goal.paths import GoalPaths


class GoalStore:
    """读写 `.goal/` 下的 PRD、SPEC、Issue 文档。"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.paths = GoalPaths(config)

    def init_layout(self) -> Path:
        self.paths.ensure_layout()
        return self.paths.base

    def save_prd(self, doc: PrdDocument) -> Path:
        self.paths.ensure_layout()
        path = self.paths.prd_path(doc.slug)
        path.write_text(doc.to_markdown(), encoding="utf-8")
        return path

    def save_spec(self, doc: SpecDocument) -> Path:
        self.paths.ensure_layout()
        path = self.paths.spec_path(doc.slug)
        path.write_text(doc.to_markdown(), encoding="utf-8")
        return path

    def save_issue(self, doc: IssueDocument) -> Path:
        self.paths.ensure_layout()
        path = self.paths.issue_path(doc.id)
        path.write_text(doc.to_markdown(), encoding="utf-8")
        return path

    def load_prd(self, slug: str) -> PrdDocument:
        path = self.paths.prd_path(slug)
        if not path.is_file():
            raise FileNotFoundError(f"PRD 不存在: {path}")
        text = path.read_text(encoding="utf-8")
        return _parse_prd(slug, text)

    def load_spec(self, slug: str) -> SpecDocument:
        path = self.paths.spec_path(slug)
        if not path.is_file():
            raise FileNotFoundError(f"SPEC 不存在: {path}")
        text = path.read_text(encoding="utf-8")
        return _parse_spec(slug, text)

    def load_issue(self, issue_id: str) -> IssueDocument:
        path = self.paths.issue_path(issue_id)
        if not path.is_file():
            raise FileNotFoundError(f"Issue 不存在: {path}")
        text = path.read_text(encoding="utf-8")
        return _parse_issue(issue_id, text)

    def list_issues(self) -> list[IssueDocument]:
        issues_dir = self.paths.issues_dir
        if not issues_dir.is_dir():
            return []
        docs: list[IssueDocument] = []
        for path in sorted(issues_dir.glob("GW-*.md")):
            docs.append(_parse_issue(path.stem, path.read_text(encoding="utf-8")))
        return docs

    def next_issue_id(self) -> str:
        existing = self.list_issues()
        if not existing:
            return "GW-001"
        numbers = []
        for issue in existing:
            match = re.match(r"GW-(\d+)", issue.id)
            if match:
                numbers.append(int(match.group(1)))
        next_num = max(numbers, default=0) + 1
        return f"GW-{next_num:03d}"

    def prd_exists(self, slug: str) -> bool:
        return self.paths.prd_path(slug).is_file()

    def spec_exists(self, slug: str) -> bool:
        return self.paths.spec_path(slug).is_file()


def _extract_section(text: str, heading: str) -> str:
    pattern = rf"^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)"
    match = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else ""


def _extract_bullets(section: str) -> list[str]:
    items: list[str] = []
    for line in section.splitlines():
        line = line.strip()
        if line.startswith("- [ ] "):
            value = line[6:].strip()
        elif line.startswith("- "):
            value = line[2:].strip()
        else:
            continue
        if value and value not in ("（待补充）", "（实现时确定）"):
            items.append(value)
    return items


def _parse_prd(slug: str, text: str) -> PrdDocument:
    title_match = re.search(r"^# PRD:\s*(.+)$", text, flags=re.MULTILINE)
    title = title_match.group(1).strip() if title_match else slug
    meta = _extract_section(text, "元信息")
    desc_match = re.search(r"- 描述:\s*(.+)", meta)
    description = desc_match.group(1).strip() if desc_match else _extract_section(text, "背景")
    return PrdDocument(
        slug=slug,
        title=title,
        description=description,
        goals=_extract_bullets(_extract_section(text, "目标")),
        non_goals=_extract_bullets(_extract_section(text, "非目标")),
        user_stories=_extract_bullets(_extract_section(text, "用户故事")),
        functional_requirements=_extract_bullets(_extract_section(text, "功能需求")),
        non_functional_requirements=_extract_bullets(
            _extract_section(text, "非功能需求")
        ),
        acceptance_criteria=_extract_bullets(_extract_section(text, "验收标准")),
        open_questions=_extract_bullets(_extract_section(text, "开放问题")),
        affected_modules=_extract_bullets(_extract_section(text, "影响模块")),
        risks=_extract_bullets(_extract_section(text, "风险")),
        related_files=_extract_bullets(_extract_section(text, "关联文件")),
        body=text,
    )


def _parse_spec(slug: str, text: str) -> SpecDocument:
    title_match = re.search(r"^# SPEC:\s*(.+)$", text, flags=re.MULTILINE)
    title = title_match.group(1).strip() if title_match else slug
    meta = _extract_section(text, "元信息")
    prd_ref_match = re.search(r"- 关联 PRD:\s*(.+)", meta)
    return SpecDocument(
        slug=slug,
        title=title,
        prd_ref=prd_ref_match.group(1).strip() if prd_ref_match else "",
        architecture=_extract_section(text, "架构设计"),
        api_contracts=_extract_section(text, "API 契约"),
        data_model=_extract_section(text, "数据模型"),
        error_handling=_extract_section(text, "错误处理"),
        security=_extract_section(text, "安全策略"),
        testing_strategy=_extract_section(text, "测试策略"),
        implementation_plan=_extract_bullets(_extract_section(text, "实施计划")),
        body=text,
    )


def _parse_issue(issue_id: str, text: str) -> IssueDocument:
    title_match = re.search(rf"^# Issue {re.escape(issue_id)}:\s*(.+)$", text, flags=re.MULTILINE)
    title = title_match.group(1).strip() if title_match else issue_id
    meta = _extract_section(text, "元信息")
    status_match = re.search(r"- 状态:\s*(\w+)", meta)
    priority_match = re.search(r"- 优先级:\s*(\w+)", meta)
    deps_match = re.search(r"- 依赖:\s*(.+)", meta)
    prd_ref_match = re.search(r"- 关联 PRD:\s*(.+)", meta)
    spec_ref_match = re.search(r"- 关联 SPEC:\s*(.+)", meta)

    deps_raw = deps_match.group(1).strip() if deps_match else "无"
    depends_on: list[str] = []
    if deps_raw and deps_raw not in ("无", "—"):
        depends_on = [part.strip() for part in deps_raw.split(",") if part.strip()]

    verify_section = _extract_section(text, "验证命令")
    verify_match = re.search(r"```bash\s*\n(.*?)\n```", verify_section, flags=re.DOTALL)
    verify_command = verify_match.group(1).strip() if verify_match else "pytest -q"

    status_value = status_match.group(1).strip() if status_match else IssueStatus.OPEN.value
    try:
        status = IssueStatus(status_value)
    except ValueError:
        status = IssueStatus.OPEN

    return IssueDocument(
        id=issue_id,
        title=title,
        description=_extract_section(text, "描述"),
        status=status,
        priority=priority_match.group(1).strip() if priority_match else "P0",
        depends_on=depends_on,
        acceptance_criteria=_extract_bullets(_extract_section(text, "验收标准")),
        verify_command=verify_command,
        scope_files=_extract_bullets(_extract_section(text, "影响文件（预估）")),
        prd_ref=prd_ref_match.group(1).strip() if prd_ref_match else "",
        spec_ref=spec_ref_match.group(1).strip() if spec_ref_match else "",
        body=text,
    )
