"""CLI 进度包装：deliver 时打印当前 Agent（不改引擎调度逻辑）。"""

from __future__ import annotations

from typing import Any, Callable

from rich.console import Console

from mawp.runtime.agents import AgentResult, AgentRunContext, AgentRunner


class ProgressAgentRunner:
    """装饰任意 AgentRunner，在执行前后输出当前 Agent。"""

    def __init__(
        self,
        inner: AgentRunner,
        console: Console | None = None,
        *,
        on_start: Callable[[str, AgentRunContext], None] | None = None,
    ):
        self.inner = inner
        self.console = console
        self.on_start = on_start
        self.history: list[dict[str, Any]] = []

    def run(
        self,
        agent: str,
        input_data: dict[str, Any],
        ctx: AgentRunContext,
    ) -> AgentResult:
        name = (agent or "").strip() or "(unknown)"
        if self.on_start is not None:
            self.on_start(name, ctx)
        elif self.console is not None:
            self.console.print(
                f"[cyan]>> Agent[/cyan] [bold]{name}[/bold]  "
                f"node=[bold]{ctx.node_id}[/bold]"
            )

        result = self.inner.run(agent, input_data, ctx)
        self.history.append(
            {
                "agent": name,
                "node_id": ctx.node_id,
                "success": result.success,
                "status": (result.output or {}).get("status"),
            }
        )

        if self.console is not None:
            if not result.success:
                self.console.print(f"   [red]fail[/red] {result.error}")
            else:
                out = result.output or {}
                hint = out.get("status") or out.get("log_summary") or "ok"
                if name.lower() == "testing":
                    hint = (
                        f"{out.get('status')} "
                        f"passed={out.get('passed')} "
                        f"attempt={out.get('attempt')}"
                    )
                elif name.lower() == "ship":
                    hint = "delivery_notes ready (auto_push=false)"
                self.console.print(f"   [green]ok[/green] {hint}")
        return result
