from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from mawp.autoresearch.models import IterationRecord, ProgramConfig
from mawp.config.loader import AgentConfig
from mawp.goal.models import IssueDocument


def blocked_report_path(config: AgentConfig, issue_id: str) -> Path:
    return config.workspace_path() / ".autoresearch" / "reports" / f"{issue_id}-blocked.md"


def write_blocked_report(
    config: AgentConfig,
    issue: IssueDocument,
    program: ProgramConfig,
    *,
    reason: str,
    records: list[IterationRecord],
) -> Path:
    path = blocked_report_path(config, issue.id)
    path.parent.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        f"# Autoresearch 失败报告: {issue.id}",
        "",
        f"- 时间: {ts}",
        f"- 标题: {issue.title}",
        f"- 原因: {reason}",
        f"- 验证命令: `{program.metric_command}`",
        f"- 总迭代: {len(records)}",
        "",
        "## 迭代记录",
        "",
        "| 轮次 | 结果 | exit | 耗时(ms) | 变更文件 | 说明 |",
        "|------|------|------|----------|----------|------|",
    ]

    for record in records:
        files = ", ".join(record.files_changed[:3]) or "—"
        if len(record.files_changed) > 3:
            files += f" (+{len(record.files_changed) - 3})"
        summary = (record.error_summary or "通过").replace("|", "\\|")[:80]
        lines.append(
            f"| {record.iteration} | {record.status.value} | {record.exit_code} | "
            f"{record.duration_ms} | {files} | {summary} |"
        )

    if records:
        lines.extend(["", "## 最后一轮详情", ""])
        last = records[-1]
        if last.diff_summary:
            lines.append(f"- diff: {last.diff_summary}")
        if last.error_summary:
            lines.append(f"- error: {last.error_summary}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def summarize_diff(files_changed: list[str]) -> str:
    if not files_changed:
        return "无文件变更"
    head = files_changed[0]
    if len(files_changed) == 1:
        return f"1 file: {head}"
    return f"{len(files_changed)} files: {head} (+{len(files_changed) - 1} more)"
