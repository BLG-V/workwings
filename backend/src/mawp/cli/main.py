from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from mawp import __version__
from mawp.autoresearch.debug import ResearchDebugError, ResearchDebugService
from mawp.autoresearch.fix import ResearchFixError, ResearchFixService
from mawp.autoresearch.loop import AutoresearchLoop, ResumeNotAvailableError
from mawp.autoresearch.program import ProgramService
from mawp.cli.display import (
    print_run_summary,
    print_ship_panel,
    print_waiting_panel,
)
from mawp.config.loader import AgentConfig, load_config
from mawp.goal.approve import ApproveError, ApproveService
from mawp.goal.issues import IssuesService
from mawp.goal.loop import GoalLoopService
from mawp.goal.prd import PrdService
from mawp.goal.ship import ShipService
from mawp.goal.spec import SpecService
from mawp.goal.store import GoalStore
from mawp.goal.transitions import InvalidTransitionError
from mawp.goal.deps import (
    DependencyNotReadyError,
    IssueNotRunnableError,
    assert_ready_for_goal,
)
from mawp.gstack.eng_review import EngReviewService
from mawp.gstack.models import ReviewStatus
from mawp.gstack.pipeline import ReviewPipeline

console = Console()
app = typer.Typer(
    name="platform",
    help=(
        "MAWP 多 Agent 工作流平台\n\n"
        "主命令: validate / run / approve / deliver / app / status\n"
        "（legacy Goal 命令仍可用，但不在 --help 中展示）"
    ),
    no_args_is_help=True,
)

research_app = typer.Typer(help="Autoresearch 自主迭代（legacy）", hidden=True)
app.add_typer(research_app, name="research", hidden=True)

apps_cmd = typer.Typer(help="App 装卸（W4 · 与 D 联调）")
app.add_typer(apps_cmd, name="app")


@dataclass
class AppContext:
    config: AgentConfig


def _get_context(ctx: typer.Context) -> AppContext:
    current: typer.Context | None = ctx
    while current is not None:
        if isinstance(current.obj, AppContext):
            return current.obj
        current = current.parent
    raise typer.Exit(code=1)


@app.callback()
def main(
    ctx: typer.Context,
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="配置文件路径（默认 ./mawp.config.yaml）",
        exists=False,
    ),
    workspace: Path | None = typer.Option(
        None,
        "--workspace",
        "-w",
        help="工作区根目录（覆盖配置中的 workspace）",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
) -> None:
    """MAWP platform CLI。"""
    try:
        cfg = load_config(config)
    except FileNotFoundError as exc:
        console.print(f"[red]错误:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if workspace is not None:
        cfg = cfg.model_copy(update={"workspace": str(workspace.resolve())})

    ctx.obj = AppContext(config=cfg)


@app.command("validate")
def validate_cmd(
    file: Path = typer.Argument(..., exists=True, dir_okay=False),
) -> None:
    """校验 workflow.yaml。"""
    from mawp.core.loader import load_workflow
    from mawp.core.validate import validate_workflow

    try:
        workflow = load_workflow(file)
    except Exception as exc:
        console.print(f"[red]加载失败:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    errors = validate_workflow(workflow)
    if errors:
        console.print(f"[red]校验失败[/red]（{len(errors)}）:")
        for err in errors:
            console.print(f"  - {err}")
        raise typer.Exit(code=1)

    console.print(f"[green]校验通过[/green] {workflow.id} @ {file}")


@app.command("run")
def run_cmd(
    ctx: typer.Context,
    workflow: Path = typer.Argument(..., exists=True, dir_okay=False),
    params: list[str] | None = typer.Option(
        None,
        "--params",
        "-p",
        help="覆盖参数，可重复：--params risk=low",
    ),
    param: list[str] | None = typer.Option(
        None,
        "--param",
        help="同 --params（兼容旧文档写法）",
    ),
) -> None:
    """执行工作流：platform run <workflow.yaml>。"""
    app_ctx = _get_context(ctx)
    from mawp.core.engine import WorkflowEngine

    overrides: dict[str, str] = {}
    for item in list(params or []) + list(param or []):
        if "=" not in item:
            console.print(f"[red]无效参数:[/red] {item}（应为 key=value）")
            raise typer.Exit(code=1)
        key, value = item.split("=", 1)
        overrides[key.strip()] = value.strip()

    engine = WorkflowEngine(app_ctx.config)
    try:
        record = engine.run(workflow, params_override=overrides or None)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    if record.status == "WAITING_USER":
        print_waiting_panel(console, record)
        # A 拍板：合法暂停 exit 0（见 docs/w3-ad-yaml-align.md）
        raise typer.Exit(code=0)

    print_run_summary(console, record)
    if record.status == "DONE":
        echo_out = (record.node_outputs.get("echo1") or {}).get("text")
        if echo_out is not None:
            console.print(f"echo1.text = {echo_out}")
        raise typer.Exit(code=0)
    if record.error:
        console.print(f"[red]error:[/red] {record.error}")
    raise typer.Exit(code=1)


def _resume_cmd(
    ctx: typer.Context,
    run_id: str,
    action: str,
    data: dict | None = None,
) -> None:
    app_ctx = _get_context(ctx)
    from mawp.core.engine import IllegalStateError, ResumeError, WorkflowEngine

    engine = WorkflowEngine(app_ctx.config)
    try:
        record = engine.resume(run_id, action, data=data)  # type: ignore[arg-type]
    except (IllegalStateError, ResumeError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    print_run_summary(console, record)
    if record.status == "WAITING_USER":
        print_waiting_panel(console, record)
        raise typer.Exit(code=0)
    if record.status == "DONE":
        raise typer.Exit(code=0)
    if record.error:
        console.print(f"[red]error:[/red] {record.error}")
    raise typer.Exit(code=1)


def _goal_approve_cmd(ctx: typer.Context, issue_id: str) -> None:
    """Legacy Goal：审查通过后授权交付。"""
    app_ctx = _get_context(ctx)
    from mawp.goal.transitions import assert_can_ship

    store = GoalStore(app_ctx.config)
    try:
        issue = store.load_issue(issue_id)
    except FileNotFoundError as exc:
        console.print(f"[red]错误:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    try:
        assert_can_ship(issue)
    except InvalidTransitionError as exc:
        console.print(f"[red]无法授权:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    service = ApproveService(app_ctx.config)
    path = service.approve(issue_id)
    console.print(
        Panel(
            f"Issue: {issue_id}\n"
            f"授权文件: {path}\n\n"
            f"下一步: [bold]platform ship {issue_id}[/bold]",
            title="交付已授权",
        )
    )


@app.command("approve")
def approve_cmd(
    ctx: typer.Context,
    target: str = typer.Argument(
        ...,
        help="Run ID（WAITING_USER 人工确认）或 legacy Issue ID（如 GW-001）",
    ),
) -> None:
    """人工确认 Run，或授权 legacy Issue 交付。

    - 若存在对应 Run → `platform approve <run_id>`（W3 human_checkpoint）
    - 否则按 Issue ID 走 legacy Goal 授权
    """
    app_ctx = _get_context(ctx)
    from mawp.storage.store import RunStore

    store = RunStore(app_ctx.config.workspace_path())
    if store.load_run(target) is not None:
        _resume_cmd(ctx, target, "approve")
        return
    _goal_approve_cmd(ctx, target)


@app.command("reject")
def reject_cmd(
    ctx: typer.Context,
    run_id: str = typer.Argument(..., help="Run ID"),
) -> None:
    """人工拒绝：platform reject <run_id>。"""
    _resume_cmd(ctx, run_id, "reject")


@app.command("input")
def input_cmd(
    ctx: typer.Context,
    run_id: str = typer.Argument(..., help="Run ID"),
    text: str = typer.Option(..., "--text", "-t", help="写入 outputs.input 的文本"),
) -> None:
    """人工输入：platform input <run_id> --text ..."""
    _resume_cmd(ctx, run_id, "input", data={"text": text})


@app.command("status")
def status_cmd(
    ctx: typer.Context,
    run_id: str = typer.Argument(..., help="Run ID"),
) -> None:
    """查询 Run 状态与摘要：platform status <run_id>。"""
    app_ctx = _get_context(ctx)
    from mawp.storage.store import RunStore

    store = RunStore(app_ctx.config.workspace_path())
    record = store.load_run(run_id)
    if record is None:
        console.print(f"[red]未找到 Run:[/red] {run_id}")
        raise typer.Exit(code=1)

    cp = None
    if record.status == "WAITING_USER":
        cp = record.checkpoint or store.load_checkpoint(run_id) or {}
    events = store.read_events(run_id)
    print_run_summary(console, record, checkpoint=cp, events=events)
    raise typer.Exit(code=0)


DEFAULT_DELIVER_WORKFLOW = Path("examples/deliver/workflow.yaml")


@app.command("deliver")
def deliver_cmd(
    ctx: typer.Context,
    workflow: Path | None = typer.Argument(
        None,
        exists=False,
        dir_okay=False,
        help="默认 examples/deliver/workflow.yaml",
    ),
    params: list[str] | None = typer.Option(
        None,
        "--params",
        "-p",
        help="覆盖参数，可重复：--params review_status=blocking",
    ),
    param: list[str] | None = typer.Option(
        None,
        "--param",
        help="同 --params",
    ),
) -> None:
    """UC-07 交付流：显示当前 Agent；Ship 后提示 approve；完善 Run 摘要。"""
    app_ctx = _get_context(ctx)
    from mawp.core.engine import WorkflowEngine
    from mawp.runtime.agents import MockAgentRunner
    from mawp.runtime.hybrid import HybridAgentRunner
    from mawp.runtime.progress import ProgressAgentRunner
    from mawp.storage.store import RunStore

    wf_path = workflow or DEFAULT_DELIVER_WORKFLOW
    if not wf_path.is_file():
        console.print(f"[red]找不到工作流:[/red] {wf_path}")
        raise typer.Exit(code=1)

    overrides: dict[str, str] = {}
    for item in list(params or []) + list(param or []):
        if "=" not in item:
            console.print(f"[red]无效参数:[/red] {item}（应为 key=value）")
            raise typer.Exit(code=1)
        key, value = item.split("=", 1)
        overrides[key.strip()] = value.strip()

    console.print(
        Panel(
            f"workflow: {wf_path}\n"
            f"params: {overrides or '(default)'}\n"
            "Agents: planner → … → coding/debug(B) → testing/ship(C) → [human?] → ship",
            title="deliver · UC-07",
            border_style="cyan",
        )
    )

    inner = HybridAgentRunner(
        app_ctx.config,
        fallback=MockAgentRunner(app_ctx.config.workspace_path()),
    )
    runner = ProgressAgentRunner(inner, console)
    engine = WorkflowEngine(app_ctx.config, agent_runner=runner)
    try:
        record = engine.run(wf_path, params_override=overrides or None)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    store = RunStore(app_ctx.config.workspace_path())
    events = store.read_events(record.run_id)
    print_run_summary(console, record, events=events)

    ship_out = (record.node_outputs or {}).get("ship") or {}
    if ship_out:
        print_ship_panel(console, ship_out)

    if record.status == "WAITING_USER":
        print_waiting_panel(
            console,
            record,
            after_approve_hint="UC-07：approve 后进入 Ship → DONE",
        )
        raise typer.Exit(code=0)

    if record.status == "DONE":
        if not ship_out:
            console.print("[dim]DONE（未产生 ship outputs）[/dim]")
        raise typer.Exit(code=0)

    if record.error:
        console.print(f"[red]error:[/red] {record.error}")
    raise typer.Exit(code=1)


@apps_cmd.command("list")
def app_list_cmd(ctx: typer.Context) -> None:
    """列出 apps/ 下可装卸 App。"""
    app_ctx = _get_context(ctx)
    from mawp.apps import AppRegistry

    registry = AppRegistry(app_ctx.config.workspace_path())
    apps = registry.list_apps()
    if not apps:
        console.print(
            "[yellow]未发现 App[/yellow] — 将 D 的 apps/demo-code-agent 放到 workspace/apps/"
        )
        raise typer.Exit(code=0)
    table = Table(title="Apps")
    table.add_column("id", style="cyan")
    table.add_column("name")
    table.add_column("version")
    table.add_column("enabled")
    table.add_column("entry")
    for info in apps:
        table.add_row(
            info.id,
            info.name,
            info.version,
            "yes" if info.enabled else "no",
            info.entry_workflow or "-",
        )
    console.print(table)


@apps_cmd.command("enable")
def app_enable_cmd(
    ctx: typer.Context,
    app_id: str = typer.Argument(..., help="App id（如 demo-code-agent）"),
) -> None:
    """启用 App（写入 .mawp/apps/enabled.json）。"""
    app_ctx = _get_context(ctx)
    from mawp.apps import AppRegistry

    registry = AppRegistry(app_ctx.config.workspace_path())
    try:
        info = registry.enable(app_id)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print(f"[green]已启用[/green] {info.id} ({info.name})")


@apps_cmd.command("disable")
def app_disable_cmd(
    ctx: typer.Context,
    app_id: str = typer.Argument(..., help="App id"),
) -> None:
    """停用 App。"""
    app_ctx = _get_context(ctx)
    from mawp.apps import AppRegistry

    registry = AppRegistry(app_ctx.config.workspace_path())
    try:
        info = registry.disable(app_id)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print(f"[yellow]已停用[/yellow] {info.id}")


@app.command("init", hidden=True)
def goal_init(ctx: typer.Context) -> None:
    """初始化 .goal/ 工作流目录结构（legacy）。"""
    app_ctx = _get_context(ctx)
    base = GoalStore(app_ctx.config).init_layout()
    console.print(f"[green]已初始化 Goal Workflow[/green] → {base.resolve()}")
    console.print("  .goal/prd/     — 产品需求文档")
    console.print("  .goal/spec/    — 技术规格")
    console.print("  .goal/issues/  — Issue 卡片")
    console.print("  .goal/archive/ — 已交付归档")
    console.print("\n下一步: [bold]platform prd \"功能描述\"[/bold]（legacy）")


@app.command("prd", hidden=True)
def prd(
    ctx: typer.Context,
    description: str = typer.Argument(..., help="功能描述 / 产品想法"),
    slug: str | None = typer.Option(None, "--slug", "-s", help="自定义 slug（默认自动生成）"),
) -> None:
    """① 规划：生成 PRD 文档。"""
    app_ctx = _get_context(ctx)
    service = PrdService(app_ctx.config)
    try:
        doc, path = service.generate(description, slug=slug)
    except FileExistsError as exc:
        console.print(f"[yellow]跳过:[/yellow] {exc}")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        console.print(f"[red]PRD 生成失败:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    body = (
        f"Slug: {doc.slug}\n"
        f"标题: {doc.title}\n"
        f"路径: {path}\n"
        f"验收标准: {len(doc.acceptance_criteria)} 条\n"
        f"开放问题: {len(doc.open_questions)} 条"
    )
    if doc.open_questions:
        body += "\n\n待澄清:\n" + "\n".join(f"  - {q}" for q in doc.open_questions[:5])
    console.print(Panel(body, title="PRD 已生成"))
    console.print(f"下一步: [bold]agent spec {doc.slug}[/bold]")


@app.command("spec", hidden=True)
def spec(
    ctx: typer.Context,
    slug: str = typer.Argument(..., help="PRD slug"),
) -> None:
    """② 设计：从 PRD 生成技术 SPEC。"""
    app_ctx = _get_context(ctx)
    service = SpecService(app_ctx.config)
    try:
        doc, path = service.generate(slug)
    except FileNotFoundError as exc:
        console.print(f"[red]错误:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except FileExistsError as exc:
        console.print(f"[yellow]跳过:[/yellow] {exc}")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        console.print(f"[red]SPEC 生成失败:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(
        Panel(
            f"Slug: {doc.slug}\n"
            f"关联 PRD: {doc.prd_ref}\n"
            f"路径: {path}\n"
            f"实施步骤: {len(doc.implementation_plan)} 条",
            title="SPEC 已生成",
        )
    )

    if app_ctx.config.gstack.enabled:
        eng = EngReviewService(app_ctx.config)
        eng_report = eng.review_spec(doc)
        console.print(
            f"[cyan]gstack plan-eng-review[/cyan]: {eng_report.status.value} "
            f"(blocking={eng_report.blocking_count})"
        )
        if eng_report.status == ReviewStatus.BLOCKED:
            for finding in eng_report.findings:
                if finding.severity == "blocking":
                    console.print(f"  [red]blocking[/red] {finding.message}")
            raise typer.Exit(code=1)

    console.print(f"下一步: [bold]agent issues {doc.slug}[/bold]")


@app.command("issues", hidden=True)
def issues(
    ctx: typer.Context,
    slug: str | None = typer.Argument(None, help="SPEC/PRD slug"),
    quick: str | None = typer.Option(
        None,
        "--quick",
        "-q",
        help="快速通道：跳过 PRD/SPEC，直接创建单个 Issue",
    ),
    continue_mode: bool = typer.Option(
        False,
        "--continue",
        "-c",
        help="增量追加：仅为新增实施步骤创建 Issue",
    ),
) -> None:
    """③ 拆解：生成 Issue 卡片。"""
    app_ctx = _get_context(ctx)
    service = IssuesService(app_ctx.config)

    if quick:
        try:
            doc, path = service.generate_quick(quick)
        except Exception as exc:
            console.print(f"[red]Issue 创建失败:[/red] {exc}")
            raise typer.Exit(code=1) from exc
        console.print(
            Panel(
                f"Issue: {doc.id}\n"
                f"标题: {doc.title}\n"
                f"路径: {path}\n"
                f"验证: {doc.verify_command}",
                title="快速 Issue 已创建",
            )
        )
        console.print(f"下一步: [bold]agent goal {doc.id}[/bold]")
        return

    if not slug:
        console.print("[red]错误:[/red] 请提供 slug 或使用 --quick")
        raise typer.Exit(code=1)

    try:
        if continue_mode:
            docs, paths = service.generate_continue(slug)
        else:
            docs, paths = service.generate_from_slug(slug)
    except FileNotFoundError as exc:
        console.print(f"[red]错误:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        console.print(f"[red]Issue 拆解失败:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if continue_mode and not docs:
        console.print(f"[yellow]无新增 Issue[/yellow] — slug={slug} 的实施步骤均已拆解")
        return

    title = "增量 Issue" if continue_mode else f"Issue 卡片 ({len(docs)} 个)"
    table = Table(title=title)
    table.add_column("ID", style="cyan")
    table.add_column("标题")
    table.add_column("依赖")
    table.add_column("验证命令")
    for doc in docs:
        table.add_row(
            doc.id,
            doc.title[:40],
            ", ".join(doc.depends_on) or "—",
            doc.verify_command[:30],
        )
    console.print(table)
    if paths:
        console.print(f"已写入: {paths[0]} …")
    if docs:
        console.print(f"下一步: [bold]agent goal {docs[0].id}[/bold]")


@app.command("goal", hidden=True)
def goal(
    ctx: typer.Context,
    issue_id: str = typer.Argument(..., help="Issue ID（如 GW-001）"),
    max_iterations: int | None = typer.Option(
        None, "--max-iterations", "-n", help="最大迭代次数"
    ),
    resume: bool = typer.Option(
        False, "--resume", help="从 autoresearch checkpoint 恢复"
    ),
) -> None:
    """④ 实现：选取 Issue 并通过 autoresearch 自主迭代完成。"""
    app_ctx = _get_context(ctx)
    store = GoalStore(app_ctx.config)
    try:
        issue = store.load_issue(issue_id)
    except FileNotFoundError as exc:
        console.print(f"[red]错误:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    loop = AutoresearchLoop(app_ctx.config)
    program_service = ProgramService(app_ctx.config)

    if resume:
        try:
            program, program_path = program_service.from_issue(issue)
            if max_iterations is not None:
                program = program.model_copy(update={"max_iterations": max_iterations})
            ctx_state = loop.store.get_resume_context(issue_id)
            start = ctx_state.get("next_iteration") if ctx_state else "?"
            console.print(
                f"[cyan]恢复 Autoresearch[/cyan] Issue {issue_id} | "
                f"从第 {start} 轮继续"
            )
            result = loop.resume_for_issue(issue_id, program)
        except ResumeNotAvailableError as exc:
            console.print(f"[red]无法恢复:[/red] {exc}")
            raise typer.Exit(code=1) from exc
    else:
        try:
            assert_ready_for_goal(issue, store)
        except (DependencyNotReadyError, IssueNotRunnableError, ValueError) as exc:
            console.print(f"[red]无法启动 goal:[/red] {exc}")
            raise typer.Exit(code=1) from exc

        program, program_path = program_service.from_issue(issue)
        if max_iterations is not None:
            program = program.model_copy(update={"max_iterations": max_iterations})

        console.print(
            f"[cyan]Autoresearch[/cyan] Issue {issue.id} | "
            f"验证: {program.metric_command} | "
            f"最多 {program.max_iterations} 轮"
        )
        console.print(f"program.md → {program_path}")
        result = loop.run_for_issue(issue, program)

    table = Table(title="迭代记录")
    table.add_column("轮次", style="cyan")
    table.add_column("结果")
    table.add_column("exit")
    table.add_column("说明")
    for record in result.records:
        table.add_row(
            str(record.iteration),
            record.status.value,
            str(record.exit_code),
            (record.error_summary or "通过")[:60],
        )
    console.print(table)

    if result.success:
        console.print(
            Panel(
                f"Issue: {issue.id} — {issue.title}\n"
                f"状态: done\n"
                f"通过轮次: {result.passed_at}\n"
                f"总迭代: {result.iterations}\n"
                f"Commit: {result.commit_sha or '（未使用 Git）'}",
                title="Goal 实现完成",
            )
        )
        console.print(f"下一步: [bold]agent review {issue.id}[/bold]")
        return

    console.print(
        Panel(
            f"Issue: {issue.id}\n"
            f"状态: blocked\n"
            f"原因: {result.blocked_reason}\n"
            f"总迭代: {result.iterations}\n"
            f"失败报告: {result.blocked_report_path or '—'}\n"
            f"可恢复: [bold]agent goal {issue.id} --resume[/bold]",
            title="Goal 实现未完成",
            border_style="red",
        )
    )
    raise typer.Exit(code=1)


@app.command("review", hidden=True)
def review_cmd(
    ctx: typer.Context,
    issue_id: str = typer.Argument(..., help="Issue ID"),
    fix: bool | None = typer.Option(
        None,
        "--fix/--no-fix",
        help="blocking 时自动触发 autoresearch 修复",
    ),
) -> None:
    """⑤ 审查：gstack review + qa 质量门禁。"""
    app_ctx = _get_context(ctx)
    pipeline = ReviewPipeline(app_ctx.config)
    try:
        result = pipeline.run(issue_id, auto_fix=fix)
    except FileNotFoundError as exc:
        console.print(f"[red]错误:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except InvalidTransitionError as exc:
        console.print(f"[red]无法审查:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    table = Table(title="gstack 审查结果")
    table.add_column("阶段", style="cyan")
    table.add_column("状态")
    table.add_column("blocking")
    table.add_row(
        "review",
        result.review_report.status.value,
        str(result.review_report.blocking_count),
    )
    table.add_row(
        "qa",
        result.qa_report.status.value,
        str(result.qa_report.blocking_count),
    )
    console.print(table)

    if result.fix_attempted:
        console.print(
            f"自动修复: {'成功' if result.fix_success else '未完全解决'}"
        )

    if result.blocking_findings:
        console.print("\n[red]Blocking 问题:[/red]")
        for finding in result.blocking_findings[:8]:
            console.print(f"  - [{finding.category}] {finding.message}")

    if result.passed:
        console.print(
            Panel(
                f"Issue: {issue_id}\n"
                f"状态: reviewed\n"
                f"review: {result.review_report.summary[:120]}",
                title="审查通过",
            )
        )
        console.print(f"下一步: [bold]agent approve {issue_id}[/bold] → [bold]agent ship {issue_id}[/bold]")
        return

    console.print("[red]审查未通过[/red] — 请修复后重新运行 agent review")
    raise typer.Exit(code=1)


@app.command("ship", hidden=True)
def ship_cmd(
    ctx: typer.Context,
    issue_id: str = typer.Argument(..., help="Issue ID"),
) -> None:
    """⑥ 交付：归档 Issue（须先通过 agent review）。"""
    app_ctx = _get_context(ctx)
    service = ShipService(app_ctx.config)
    try:
        archive_dir, summary = service.ship(issue_id)
    except FileNotFoundError as exc:
        console.print(f"[red]错误:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except PermissionError as exc:
        console.print(f"[red]交付被拒绝:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except ApproveError as exc:
        console.print(f"[red]交付被拒绝:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(
        Panel(
            f"Issue: {issue_id}\n"
            f"归档目录: {archive_dir}\n\n{summary}",
            title="交付完成",
        )
    )


def _run_research_loop(
    config: AgentConfig,
    issue_id: str,
    *,
    max_iterations: int | None = None,
    resume: bool = False,
) -> None:
    loop = AutoresearchLoop(config)
    program_service = ProgramService(config)

    if resume:
        try:
            issue = GoalStore(config).load_issue(issue_id)
            program, _ = program_service.from_issue(issue)
            if max_iterations is not None:
                program = program.model_copy(update={"max_iterations": max_iterations})
            ctx_state = loop.store.get_resume_context(issue_id)
            start = ctx_state.get("next_iteration") if ctx_state else "?"
            console.print(f"[cyan]恢复[/cyan] Issue {issue_id} 从第 {start} 轮继续")
            result = loop.resume_for_issue(issue_id, program)
        except FileNotFoundError as exc:
            console.print(f"[red]错误:[/red] {exc}")
            raise typer.Exit(code=1) from exc
        except ResumeNotAvailableError as exc:
            console.print(f"[red]无法恢复:[/red] {exc}")
            raise typer.Exit(code=1) from exc
    else:
        store = GoalStore(config)
        try:
            issue = store.load_issue(issue_id)
        except FileNotFoundError as exc:
            console.print(f"[red]错误:[/red] {exc}")
            raise typer.Exit(code=1) from exc

        ar_path = config.workspace_path() / ".autoresearch" / "program.md"
        if ar_path.is_file():
            program = program_service.load()
            if program.issue_id != issue_id:
                program, _ = program_service.from_issue(issue)
        else:
            program, _ = program_service.from_issue(issue)

        if max_iterations is not None:
            program = program.model_copy(update={"max_iterations": max_iterations})

        result = loop.run_for_issue(issue, program)

    if result.success:
        console.print(
            f"[green]通过[/green] — {issue_id} 第 {result.passed_at} 轮 | "
            f"commit={result.commit_sha or 'n/a'}"
        )
        return

    console.print(f"[red]未通过[/red] — {result.blocked_reason}")
    if loop.can_resume(issue_id):
        console.print(f"可恢复: [bold]agent research resume {issue_id}[/bold]")
    raise typer.Exit(code=1)


@research_app.callback(invoke_without_command=True)
def research_group(
    ctx: typer.Context,
    issue_id: str | None = typer.Argument(
        None,
        help="Issue ID（省略子命令时等同于 research run）",
    ),
    max_iterations: int | None = typer.Option(
        None,
        "--max-iterations",
        "-n",
        help="最大迭代次数",
    ),
) -> None:
    """Autoresearch 自主迭代（agent research <id> 等同于 agent research run <id>）。"""
    if ctx.invoked_subcommand is not None:
        return
    if issue_id is None:
        console.print(ctx.get_help())
        raise typer.Exit()
    app_ctx = _get_context(ctx)
    _run_research_loop(app_ctx.config, issue_id, max_iterations=max_iterations)


@research_app.command("plan")
def research_plan(
    ctx: typer.Context,
    issue_id: str = typer.Argument(..., help="Issue ID"),
) -> None:
    """生成 autoresearch program.md。"""
    app_ctx = _get_context(ctx)
    service = ProgramService(app_ctx.config)
    try:
        program, path = service.plan_for_issue_id(issue_id)
    except FileNotFoundError as exc:
        console.print(f"[red]错误:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(
        Panel(
            f"Issue: {program.issue_id}\n"
            f"验证: {program.metric_command}\n"
            f"Scope: {len(program.scope_files)} 个文件\n"
            f"路径: {path}",
            title="program.md 已生成",
        )
    )
    console.print(f"下一步: [bold]agent research {issue_id}[/bold]")


@research_app.command("run")
def research_run(
    ctx: typer.Context,
    issue_id: str = typer.Argument(..., help="Issue ID"),
    max_iterations: int | None = typer.Option(
        None, "--max-iterations", "-n", help="最大迭代次数"
    ),
) -> None:
    """运行 autoresearch 自主迭代循环。"""
    app_ctx = _get_context(ctx)
    _run_research_loop(app_ctx.config, issue_id, max_iterations=max_iterations)


@research_app.command("resume")
def research_resume(
    ctx: typer.Context,
    issue_id: str = typer.Argument(..., help="Issue ID"),
    max_iterations: int | None = typer.Option(
        None, "--max-iterations", "-n", help="最大迭代次数"
    ),
) -> None:
    """从 autoresearch checkpoint 恢复自主迭代。"""
    app_ctx = _get_context(ctx)
    _run_research_loop(
        app_ctx.config,
        issue_id,
        max_iterations=max_iterations,
        resume=True,
    )


@research_app.command("fix")
def research_fix(
    ctx: typer.Context,
    issue_id: str = typer.Argument(..., help="Issue ID"),
) -> None:
    """针对 gstack blocking 审查意见运行 autoresearch 修复循环。"""
    app_ctx = _get_context(ctx)
    service = ResearchFixService(app_ctx.config)
    try:
        result = service.run_fix(issue_id)
    except FileNotFoundError as exc:
        console.print(f"[red]错误:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except ResearchFixError as exc:
        console.print(f"[red]无法修复:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if result.success:
        console.print(
            Panel(
                f"Issue: {issue_id}\n"
                f"修复轮次: {result.passed_at}\n"
                f"总迭代: {result.iterations}\n\n"
                f"下一步: [bold]agent review {issue_id}[/bold]",
                title="Blocking 修复完成",
            )
        )
        return

    console.print(f"[red]修复未成功[/red] — {result.blocked_reason}")
    raise typer.Exit(code=1)


@research_app.command("debug")
def research_debug(
    ctx: typer.Context,
    issue_id: str = typer.Argument(..., help="Issue ID"),
    max_iterations: int | None = typer.Option(
        None, "--max-iterations", "-n", help="最大调试迭代次数（默认 15）"
    ),
) -> None:
    """测试失败时的假设-验证式调试循环。"""
    app_ctx = _get_context(ctx)
    service = ResearchDebugService(app_ctx.config)
    try:
        result = service.run_debug(issue_id, max_iterations=max_iterations)
    except FileNotFoundError as exc:
        console.print(f"[red]错误:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except ResearchDebugError as exc:
        console.print(f"[red]无法调试:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if result.success:
        console.print(
            Panel(
                f"Issue: {issue_id}\n"
                f"调试轮次: {result.passed_at}\n"
                f"总迭代: {result.iterations}\n\n"
                f"下一步: [bold]agent review {issue_id}[/bold]",
                title="Debug 完成",
            )
        )
        return

    console.print(f"[red]调试未成功[/red] — {result.blocked_reason}")
    raise typer.Exit(code=1)


@app.command("loop", hidden=True)
def loop_cmd(
    ctx: typer.Context,
    slug: str = typer.Argument(..., help="PRD/SPEC slug"),
    review: bool = typer.Option(False, "--review", help="每个 Issue goal 后自动 review"),
    no_resume: bool = typer.Option(
        False, "--no-resume", help="忽略 checkpoint，从头开始"
    ),
) -> None:
    """批量实现：按依赖顺序对 slug 下所有 Issue 执行 goal。"""
    app_ctx = _get_context(ctx)
    service = GoalLoopService(app_ctx.config)
    try:
        result = service.run(slug, resume=not no_resume, run_review=review)
    except FileNotFoundError as exc:
        console.print(f"[red]错误:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    table = Table(title=f"Loop 结果 — {slug}")
    table.add_column("Issue", style="cyan")
    table.add_column("状态")
    for issue_id in result.completed:
        table.add_row(issue_id, "done")
    if result.reviewed:
        for issue_id in result.reviewed:
            if issue_id in result.completed:
                continue
            table.add_row(issue_id, "reviewed")
    console.print(table)

    if result.success:
        console.print(
            Panel(
                f"slug: {slug}\n"
                f"完成: {len(result.completed)} 个 Issue\n"
                f"review: {len(result.reviewed)} 个",
                title="Loop 完成",
            )
        )
        if result.completed:
            console.print(f"下一步: [bold]agent review {result.completed[-1]}[/bold]")
        return

    console.print(
        Panel(
            f"失败 Issue: {result.failed_issue_id}\n"
            f"原因: {result.blocked_reason}\n"
            f"已完成: {', '.join(result.completed) or '无'}",
            title="Loop 中断",
            border_style="red",
        )
    )
    raise typer.Exit(code=1)


@app.command("index", hidden=True)
def index(
    ctx: typer.Context,
    force: bool = typer.Option(False, "--force", help="强制重建索引"),
) -> None:
    """构建代码库 RAG 索引。"""
    app_ctx = _get_context(ctx)
    from mawp.rag.service import RAGService

    rag = RAGService(app_ctx.config)
    try:
        stats = rag.build_index(force=force)
    except Exception as exc:
        console.print(f"[red]索引失败:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if not stats.rebuilt:
        console.print("[green]索引已存在[/green]，使用 --force 重建")
        console.print(
            f"  文件: {stats.files_indexed} | 块: {stats.chunks_indexed} | 路径: {stats.index_path}"
        )
        return

    table = Table(title="RAG 索引完成")
    table.add_column("指标", style="cyan")
    table.add_column("值")
    table.add_row("扫描文件", str(stats.files_scanned))
    table.add_row("已索引文件", str(stats.files_indexed))
    table.add_row("代码块", str(stats.chunks_indexed))
    table.add_row("跳过", str(stats.skipped))
    table.add_row("耗时", f"{stats.duration_ms} ms")
    table.add_row("Collection", stats.collection)
    table.add_row("存储路径", stats.index_path)
    console.print(table)


@app.command("web", hidden=True)
def web_serve(
    ctx: typer.Context,
    host: str = typer.Option("127.0.0.1", "--host", "-H", help="监听地址"),
    port: int = typer.Option(8080, "--port", "-p", help="监听端口"),
    reload: bool = typer.Option(False, "--reload", help="开发模式热重载"),
) -> None:
    """启动 Web UI 进度面板。"""
    try:
        import uvicorn
    except ImportError as exc:
        console.print(
            '[red]缺少 Web 依赖[/red] — 请运行: pip install -e ".[web]"'
        )
        raise typer.Exit(code=1) from exc

    from mawp.api.app import create_app

    app_ctx = _get_context(ctx)
    api = create_app(app_ctx.config)
    url = f"http://{host}:{port}"
    console.print(f"[green]Web UI[/green] → {url}")
    console.print(f"工作区: {app_ctx.config.workspace_path()}")
    uvicorn.run(api, host=host, port=port, reload=reload)


@app.command("version")
def version() -> None:
    """显示版本号。"""
    console.print(f"ai-code-agent {__version__}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
