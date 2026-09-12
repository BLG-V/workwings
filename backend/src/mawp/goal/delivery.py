from __future__ import annotations

from pathlib import Path

from mawp.config.loader import AgentConfig
from mawp.gstack.models import ReviewReport, ReviewStatus
from mawp.gstack.store import ReviewStore
from mawp.goal.models import IssueDocument


def _conventional_scope(issue: IssueDocument) -> str:
    for path in issue.scope_files:
        parts = path.replace("\\", "/").split("/")
        if len(parts) >= 2 and parts[0] == "src":
            return parts[1]
        if parts[0]:
            return parts[0].replace(".py", "").replace(".ts", "")
    for ref in (issue.prd_ref, issue.spec_ref):
        if ref and ref not in {"—", "-"}:
            return ref.split("-")[0][:20]
    return "core"


def _commit_type(title: str, description: str) -> str:
    text = f"{title} {description}".lower()
    if any(word in text for word in ("fix", "修复", "bug")):
        return "fix"
    if any(word in text for word in ("refactor", "重构")):
        return "refactor"
    if any(word in text for word in ("test", "测试")):
        return "test"
    return "feat"


def generate_commit_message(issue: IssueDocument) -> str:
    scope = _conventional_scope(issue)
    ctype = _commit_type(issue.title, issue.description)
    subject = issue.title.strip()[:72]
    lines = [
        f"{ctype}({scope}): {issue.id} {subject}",
        "",
        issue.description.strip() or subject,
        "",
        f"Verify: {issue.verify_command or 'pytest -q'}",
        "",
        f"Refs: {issue.id}",
    ]
    return "\n".join(lines).strip() + "\n"


def generate_pr_body(
    issue: IssueDocument,
    *,
    review_report: ReviewReport | None,
    qa_report: ReviewReport | None,
) -> str:
    sections = [
        f"# Pull Request: {issue.id} — {issue.title}",
        "",
        "## Summary",
        issue.description.strip() or issue.title,
        "",
        "## Acceptance Criteria",
    ]
    for item in issue.acceptance_criteria or ["见 Issue 描述"]:
        sections.append(f"- [x] {item}")

    sections.extend(["", "## Verification", f"- Command: `{issue.verify_command or 'pytest -q'}`"])
    if qa_report:
        sections.append(f"- QA: **{qa_report.status.value}** — {qa_report.summary}")

    sections.extend(["", "## Review"])
    if review_report:
        sections.append(
            f"- Code review: **{review_report.status.value}** — "
            f"{review_report.summary or '无摘要'}"
        )
        blocking = review_report.blocking_count
        if blocking:
            sections.append(f"- Blocking findings: {blocking}")
    else:
        sections.append("- Code review: 未找到报告")

    if issue.scope_files:
        sections.extend(["", "## Files (scope)", ""])
        for path in issue.scope_files:
            sections.append(f"- `{path}`")

    sections.extend(["", f"---", f"Issue: `{issue.id}`"])
    return "\n".join(sections) + "\n"


def generate_ship_summary(
    issue: IssueDocument,
    archive_name: str,
    *,
    review_report: ReviewReport | None,
    qa_report: ReviewReport | None,
    iterations: int | None = None,
) -> str:
    lines = [
        f"# Ship Summary: {issue.id}",
        "",
        f"- 标题: {issue.title}",
        f"- 归档: {archive_name}",
        f"- 验证: {issue.verify_command}",
        f"- 状态: reviewed → shipped",
    ]
    if iterations is not None:
        lines.append(f"- Autoresearch 迭代: {iterations}")
    if review_report:
        lines.append(f"- Review: {review_report.status.value}")
    if qa_report:
        lines.append(f"- QA: {qa_report.status.value}")
    lines.append("")
    lines.append("交付物: SHIP.md, PR.md, COMMIT_MSG.txt, reviews/, results.jsonl")
    return "\n".join(lines) + "\n"


def count_autoresearch_iterations(config: AgentConfig, issue_id: str) -> int:
    results_path = config.workspace_path() / config.autoresearch.results_path
    if not results_path.is_file():
        results_path = config.workspace_path() / ".autoresearch" / "results.jsonl"
    if not results_path.is_file():
        return 0
    count = 0
    for line in results_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        import json

        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("issue_id") == issue_id:
            count += 1
    return count
