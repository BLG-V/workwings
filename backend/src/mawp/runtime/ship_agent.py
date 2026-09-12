"""Ship Agent（C）：生成交付说明；禁止自动 push / merge。

outputs 键名与 docs/w4-ad-deliver-yaml-align.md 冻结契约对齐。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mawp.runtime.agents import AgentRunContext
from mawp.storage.store import utc_now_iso


def _testing_line(outputs: dict[str, Any]) -> str:
    testing = outputs.get("testing") or {}
    if not testing:
        return "- Testing: (未执行)"
    status = testing.get("status") or ("pass" if testing.get("passed") else "fail")
    summary = testing.get("log_summary") or ""
    attempt = testing.get("attempt")
    return f"- Testing: {status} (attempt={attempt}) {summary}".rstrip()


def _review_line(outputs: dict[str, Any]) -> str:
    review = outputs.get("review") or {}
    if not review:
        return "- Review: (未执行)"
    return (
        f"- Review: {review.get('status')} "
        f"(blocking={review.get('blocking_count', 0)})"
    )


def build_delivery_notes(
    input_data: dict[str, Any],
    ctx: AgentRunContext,
) -> str:
    goal = str(
        input_data.get("goal")
        or ctx.params.get("goal")
        or "deliver"
    )
    preset = input_data.get("delivery_notes")
    coding = ctx.nodes_outputs.get("coding") or {}
    changed = coding.get("changed_files") or []
    human = ctx.nodes_outputs.get("human_review") or {}

    lines = [
        f"# Delivery Notes — {goal}",
        "",
        f"- run_id: {ctx.run_id}",
        f"- generated_at: {utc_now_iso()}",
        _testing_line(ctx.nodes_outputs),
        _review_line(ctx.nodes_outputs),
        f"- Coding files: {', '.join(str(p) for p in changed) or '-'}",
    ]
    if human.get("decision"):
        lines.append(f"- Human decision: {human.get('decision')}")
    lines.extend(
        [
            "",
            "## 人工交付清单（禁止自动 push/merge）",
            "1. 检查 git status / diff",
            "2. 人工 commit（可用下方建议信息）",
            "3. 人工 push / 开 PR / merge —— **平台不会代劳**",
            "",
        ]
    )
    if preset:
        lines.extend(["## 备注", str(preset), ""])
    return "\n".join(lines)


def run_ship_agent(
    input_data: dict[str, Any],
    ctx: AgentRunContext,
    *,
    workspace: Path | None = None,
) -> dict[str, Any]:
    """生成交付说明；**永不**执行 git push / merge。"""
    notes = build_delivery_notes(input_data, ctx)
    coding = ctx.nodes_outputs.get("coding") or {}
    testing = ctx.nodes_outputs.get("testing") or {}
    goal = str(input_data.get("goal") or ctx.params.get("goal") or "deliver")

    commit_message = str(
        input_data.get("commit_message")
        or f"feat: {goal} (run {ctx.run_id})"
    )
    checklist = [
        "审查 delivery_notes",
        "人工 git commit",
        "人工 git push（如需要）",
        "人工创建/合并 PR（如需要）",
    ]

    artifact: str | None = None
    if workspace is not None:
        out_dir = Path(workspace) / ".mawp" / "deliveries"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{ctx.run_id}.md"
        path.write_text(notes, encoding="utf-8")
        artifact = str(path.relative_to(Path(workspace))) if path.is_relative_to(Path(workspace)) else str(path)

    return {
        "status": "ok",
        "delivery_notes": notes,
        "auto_push": False,
        "auto_merge": False,
        "commit_message": commit_message,
        "checklist": checklist,
        "testing_passed": bool(testing.get("passed")),
        "changed_files": list(coding.get("changed_files") or []),
        "artifact": artifact,
    }
