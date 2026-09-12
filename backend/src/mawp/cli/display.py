"""CLI 展示层：Run 等待提示与摘要（不改引擎）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from mawp.storage.store import RunRecord


def parse_iso(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def duration_label(record: RunRecord) -> str:
    start = parse_iso(record.created_at)
    end = parse_iso(record.updated_at)
    if start is None or end is None:
        return "-"
    secs = max(0.0, (end - start).total_seconds())
    if secs < 1:
        return f"{secs * 1000:.0f} ms"
    if secs < 60:
        return f"{secs:.1f} s"
    mins, rem = divmod(secs, 60)
    return f"{int(mins)} m {rem:.0f} s"


def status_style(status: str) -> str:
    mapping = {
        "DONE": "green",
        "WAITING_USER": "yellow",
        "FAILED": "red",
        "CANCELLED": "red",
        "RUNNING": "cyan",
        "INIT": "dim",
    }
    return mapping.get(status, "white")


def next_step_commands(run_id: str, allowed: list[str] | None = None) -> list[str]:
    actions = allowed or ["approve", "reject", "input"]
    cmds: list[str] = []
    for action in actions:
        if action == "input":
            cmds.append(f'platform input {run_id} --text "..."')
        elif action in {"approve", "reject"}:
            cmds.append(f"platform {action} {run_id}")
    return cmds


def print_waiting_panel(
    console: Console,
    record: RunRecord,
    checkpoint: dict[str, Any] | None = None,
    *,
    after_approve_hint: str | None = None,
) -> None:
    cp = checkpoint or record.checkpoint or {}
    reason = cp.get("reason") or "(未提供 reason)"
    allowed = cp.get("allowed") or ["approve", "reject", "input"]
    if isinstance(allowed, str):
        allowed = [allowed]
    cmds = next_step_commands(record.run_id, list(allowed))

    hint = after_approve_hint or "approve 后继续执行（如进入 Ship）"
    body = (
        f"[bold]run_id[/bold]  {record.run_id}\n"
        f"[bold]node[/bold]    {record.current_node_id or '-'}\n"
        f"[bold]reason[/bold]  {reason}\n"
        f"[bold]allowed[/bold] {', '.join(str(a) for a in allowed)}\n\n"
        f"[bold]下一步[/bold]\n"
        + "\n".join(f"  - {c}" for c in cmds)
        + f"\n\n[dim]{hint}[/dim]"
    )
    console.print(
        Panel(
            body,
            title="[yellow]WAITING_USER - 等待人工确认[/yellow]",
            border_style="yellow",
        )
    )


def _agent_summary_rows(record: RunRecord) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    outs = record.node_outputs or {}
    testing = outs.get("testing") or {}
    if testing:
        rows.append(
            (
                "testing",
                f"{testing.get('status')} passed={testing.get('passed')} "
                f"attempt={testing.get('attempt')}",
            )
        )
        if testing.get("log_summary"):
            rows.append(("test_log", str(testing.get("log_summary"))[:120]))
    review = outs.get("review") or {}
    if review:
        rows.append(
            (
                "review",
                f"{review.get('status')} blocking={review.get('blocking_count', 0)}",
            )
        )
    ship = outs.get("ship") or {}
    if ship:
        rows.append(
            (
                "ship",
                f"status={ship.get('status')} auto_push={ship.get('auto_push')} "
                f"auto_merge={ship.get('auto_merge')}",
            )
        )
    return rows


def print_run_summary(
    console: Console,
    record: RunRecord,
    *,
    checkpoint: dict[str, Any] | None = None,
    events: list[dict[str, Any]] | None = None,
) -> None:
    style = status_style(record.status)
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("k", style="bold cyan", width=16)
    table.add_column("v")
    table.add_row("run_id", record.run_id)
    table.add_row("workflow", record.workflow_id or "-")
    table.add_row("status", f"[{style}]{record.status}[/{style}]")
    table.add_row("current_node", record.current_node_id or "-")
    table.add_row("duration", duration_label(record))
    table.add_row("created_at", record.created_at)
    table.add_row("updated_at", record.updated_at)

    for key, value in _agent_summary_rows(record):
        table.add_row(key, value)

    if record.status == "WAITING_USER":
        cp = checkpoint or record.checkpoint or {}
        table.add_row("wait_reason", str(cp.get("reason") or "-"))
        allowed = cp.get("allowed") or []
        table.add_row(
            "allowed",
            ", ".join(str(a) for a in allowed) if allowed else "-",
        )
    if record.failed_node_id:
        table.add_row("failed_node", record.failed_node_id)
    if record.error:
        table.add_row("error", f"[red]{record.error}[/red]")

    event_count = len(events) if events is not None else None
    if event_count is not None:
        table.add_row("events", str(event_count))

    console.print(Panel(table, title="Run 摘要", border_style=style))

    if record.status == "WAITING_USER":
        cp = checkpoint or record.checkpoint or {}
        allowed = cp.get("allowed") or ["approve", "reject", "input"]
        if isinstance(allowed, str):
            allowed = [allowed]
        cmds = next_step_commands(record.run_id, list(allowed))
        console.print("[yellow]下一步命令：[/yellow]")
        for cmd in cmds:
            console.print(f"  [bold]{cmd}[/bold]")
        if record.current_node_id == "human_review":
            console.print(
                "[dim]提示：approve 后将进入 Ship，再 DONE（UC-07）[/dim]"
            )


def print_ship_panel(console: Console, ship_out: dict[str, Any]) -> None:
    notes = str(ship_out.get("delivery_notes") or "").strip()
    preview = notes if len(notes) <= 800 else notes[:800] + "\n..."
    body = (
        f"[bold]auto_push[/bold]=[red]{ship_out.get('auto_push', False)}[/red]  "
        f"[bold]auto_merge[/bold]=[red]{ship_out.get('auto_merge', False)}[/red]\n"
        f"[bold]artifact[/bold]={ship_out.get('artifact') or '-'}\n\n"
        f"{preview}"
    )
    console.print(
        Panel(
            body,
            title="[green]Ship 交付说明（需人工 push/merge）[/green]",
            border_style="green",
        )
    )
    console.print(
        "[yellow]Ship 完成后如仍停在人工节点，请执行[/yellow] "
        "[bold]platform approve <run_id>[/bold]"
    )
