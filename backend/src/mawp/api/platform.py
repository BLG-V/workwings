"""Platform HTTP API：供 agentflow 前端调用的工作流桥接层。"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Annotated, Any, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Query
import json
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from mawp.config.loader import AgentConfig, DEFAULT_AGENT_MODELS, load_config
from mawp.core.engine import IllegalStateError, ResumeError, WorkflowEngine
from mawp.core.loader import load_workflow
from mawp.core.validate import validate_workflow
from mawp.llm.factory import resolve_api_key
from mawp.storage.store import RunStore
from mawp.auth.routes import router as auth_router
from mawp.asr.routes import router as asr_router
from mawp.image.routes import router as image_router
from mawp.runtime.deploy_scaffolder import scaffold_deploy_files
from mawp.runtime.cicd_scaffolder import scaffold_cicd
from mawp.runtime.web_scaffold import placeholder_portal_html, write_theme_css
from mawp.advanced import AdvancedProjectStore
from mawp.runtime.version_manager import (
    create_version_snapshot,
    list_versions,
    get_version_detail,
    rollback_to_version,
    diff_versions,
)


class ValidateBody(BaseModel):
    path: str | None = None
    yaml_text: str | None = None


class RunBody(BaseModel):
    path: str
    params: dict[str, Any] = Field(default_factory=dict)
    async_mode: bool = False


class ResumeBody(BaseModel):
    action: str = "approve"
    data: dict[str, Any] | None = None


class DeliverBody(BaseModel):
    goal: str
    pass_on_attempt: int = 1
    review_status: str = "pass"
    async_mode: bool = True
    project_mode: bool = False
    project_root: str | None = None
    project_title: str | None = None
    frontend_dir: str | None = None
    srs_excerpt: str | None = None
    phase_id: str | None = None
    create_workspace: bool = True


class UpdateModelsBody(BaseModel):
    models: dict[str, str] = Field(default_factory=dict)


class SnapshotBody(BaseModel):
    project_root: str
    run_id: str = ""
    goal: str = ""


class RetryRunBody(BaseModel):
    from_failed_node: bool = True


class SaveFileBody(BaseModel):
    project_root: str
    path: str
    content: str


DELIVER_WORKFLOW = "apps/demo-code-agent/workflows/deliver.yaml"

# Studio 阶段 ← deliver 节点
STAGE_NODE_MAP = {
    "requirement": "requirement",
    "architecture": "planner",  # 无独立架构 Agent，用 planner 任务分解兜底
    "code": "coding",
    "test": "testing",
    "deploy": "ship",
}


def _stages_from_outputs(node_outputs: dict[str, Any] | None) -> dict[str, Any]:
    outs = node_outputs or {}
    coding = outs.get("coding") or {}
    frontend = outs.get("frontend") or {}
    planner = outs.get("planner") or {}
    requirement = outs.get("requirement") or {}
    testing = outs.get("testing") or {}
    ship = outs.get("ship") or {}
    review = outs.get("review") or {}
    return {
        "requirement": requirement,
        "architecture": {
            "tasks": planner.get("tasks") or [],
            "count": planner.get("count")
            or len(planner.get("tasks") or []),
            "status": planner.get("status") or "ok",
            "goal_hint": (requirement.get("summary") or "")[:120],
            "from": "planner",
        },
        "code": {
            **coding,
            "frontend": frontend,
        },
        "test": testing,
        "deploy": {
            **ship,
            "review": review,
        },
        "raw": outs,
    }


def _resolve_workflow_path(config: AgentConfig, raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = (config.workspace_path() / path).resolve()
    else:
        path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"工作流文件不存在: {path}")
    return path


def create_platform_app(config: AgentConfig | None = None) -> FastAPI:
    config = config or load_config()
    app = FastAPI(
        title="智流 MAWP Platform API",
        description="多 Agent 工作流内核 HTTP 桥接（供前端 UI 调用）",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_router)
    app.include_router(asr_router)
    app.include_router(image_router)

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "mawp-platform",
            "workspace": str(config.workspace_path()),
            "llm": {
                "provider": config.llm.provider,
                "model": config.llm.model,
                "has_api_key": bool(resolve_api_key(config)),
            },
            "agent_models": dict(config.agents.models or DEFAULT_AGENT_MODELS),
        }

    @app.get("/api/platform/info")
    def platform_info() -> dict[str, Any]:
        examples = config.workspace_path() / "examples"
        workflows: list[dict[str, str]] = []
        if examples.is_dir():
            for path in sorted(examples.glob("*/workflow.yaml")):
                workflows.append(
                    {
                        "id": path.parent.name,
                        "path": str(path.relative_to(config.workspace_path())),
                    },
                )
        return {
            "workspace": str(config.workspace_path()),
            "example_workflows": workflows,
            "agent_models": dict(config.agents.models or DEFAULT_AGENT_MODELS),
            "default_llm_model": config.llm.model,
        }

    # 可用模型列表
    AVAILABLE_MODELS: list[dict[str, str]] = [
        {"id": "deepseek-chat", "label": "DeepSeek Chat（快速·便宜）", "tier": "fast"},
        {"id": "deepseek-reasoner", "label": "DeepSeek Reasoner（推理·强）", "tier": "strong"},
        {"id": "deepseek-v4-flash", "label": "DeepSeek V4 Flash（快速）", "tier": "fast"},
        {"id": "deepseek-v4-pro", "label": "DeepSeek V4 Pro（强力·贵）", "tier": "strong"},
        {"id": "gpt-4o-mini", "label": "GPT-4o mini（快速·便宜）", "tier": "fast"},
        {"id": "gpt-4o", "label": "GPT-4o（强力·贵）", "tier": "strong"},
        {"id": "claude-3-5-sonnet", "label": "Claude 3.5 Sonnet（强力）", "tier": "strong"},
        {"id": "claude-3-haiku", "label": "Claude 3 Haiku（快速·便宜）", "tier": "fast"},
    ]

    @app.get("/api/platform/models")
    def list_models() -> dict[str, Any]:
        """列出可用模型和当前各 Agent 的模型配置。"""
        return {
            "available_models": AVAILABLE_MODELS,
            "current": dict(config.agents.models or DEFAULT_AGENT_MODELS),
            "default_llm_model": config.llm.model,
        }

    @app.post("/api/platform/models")
    def update_models(body: UpdateModelsBody) -> dict[str, Any]:
        """更新各 Agent 的模型配置（运行时生效，不持久化到文件）。"""
        for agent_name, model_id in body.models.items():
            if agent_name in DEFAULT_AGENT_MODELS:
                config.agents.models[agent_name] = str(model_id)
        return {
            "ok": True,
            "current": dict(config.agents.models or DEFAULT_AGENT_MODELS),
        }

    def _observe_run(store: RunStore, run: Any) -> dict[str, Any]:
        from mawp.runtime.run_observe import summarize_run_observe

        return summarize_run_observe(
            store.read_events(run.run_id),
            status=run.status,
            error=run.error,
            heal=run.heal,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )

    @app.get("/api/platform/runs")
    def list_runs(limit: int = 50) -> dict[str, Any]:
        store = RunStore(config.workspace_path())
        runs = store.list_runs(limit=limit)
        out: list[dict[str, Any]] = []
        for r in runs:
            row = r.to_dict()
            row["observe"] = _observe_run(store, r)
            out.append(row)
        return {"runs": out}

    @app.get("/api/platform/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        store = RunStore(config.workspace_path())
        run = store.load_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"run 不存在: {run_id}")
        events = store.read_events(run_id)
        payload = run.to_dict()
        payload["observe"] = _observe_run(store, run)
        return {"run": payload, "events": events, "observe": payload["observe"]}

    @app.post("/api/platform/workflows/validate")
    def validate(body: ValidateBody) -> dict[str, Any]:
        try:
            if body.yaml_text:
                import tempfile

                with tempfile.NamedTemporaryFile(
                    mode="w",
                    suffix=".yaml",
                    delete=False,
                    encoding="utf-8",
                ) as tmp:
                    tmp.write(body.yaml_text)
                    path = Path(tmp.name)
                try:
                    workflow = load_workflow(path)
                finally:
                    path.unlink(missing_ok=True)
            elif body.path:
                path = _resolve_workflow_path(config, body.path)
                workflow = load_workflow(path)
            else:
                raise HTTPException(status_code=400, detail="需要 path 或 yaml_text")
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"加载失败: {exc}") from exc

        errors = validate_workflow(workflow)
        return {
            "ok": len(errors) == 0,
            "workflow_id": workflow.id,
            "errors": errors,
        }

    @app.post("/api/platform/workflows/run")
    def run_workflow(body: RunBody) -> dict[str, Any]:
        try:
            path = _resolve_workflow_path(config, body.path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        engine = WorkflowEngine(config)
        try:
            if body.async_mode:
                record = engine.run_async(path, params_override=body.params or None)
            else:
                record = engine.run(path, params_override=body.params or None)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"执行失败: {exc}") from exc

        return {"run": record.to_dict()}

    @app.post("/api/platform/studio/deliver")
    def studio_deliver(body: DeliverBody) -> dict[str, Any]:
        goal = (body.goal or "").strip()
        if not goal:
            raise HTTPException(status_code=400, detail="goal 不能为空")
        try:
            path = _resolve_workflow_path(config, DELIVER_WORKFLOW)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        project_mode = bool(body.project_mode)
        project_root = (body.project_root or "").strip() or None
        frontend_dir = (body.frontend_dir or "").strip() or None
        project_title = (body.project_title or "").strip() or None

        if project_mode and not project_root and body.create_workspace:
            from uuid import uuid4

            project_root = f"workspaces/studio-{uuid4().hex[:10]}"
            ws = config.workspace_path() / project_root
            (ws / "docs").mkdir(parents=True, exist_ok=True)
            (ws / "apps" / "api").mkdir(parents=True, exist_ok=True)
            (ws / "apps" / "web").mkdir(parents=True, exist_ok=True)
            (ws / "README.md").write_text(
                f"# {project_title or 'Studio 大项目'}\n\nGoal:\n\n{goal}\n",
                encoding="utf-8",
            )
            (ws / "docs" / "GOAL.md").write_text(goal, encoding="utf-8")
            (ws / "apps" / "api" / "main.py").write_text(
                'from fastapi import FastAPI\nfrom fastapi.middleware.cors import CORSMiddleware\n\n'
                'app = FastAPI(title="Studio Project API", version="0.1.0")\n'
                'app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])\n\n'
                '@app.get("/health")\ndef health():\n    return {"status": "ok", "service": "studio-project-api"}\n',
                encoding="utf-8",
            )
            (ws / "apps" / "api" / "requirements.txt").write_text(
                "fastapi>=0.115.0\nuvicorn[standard]>=0.30.0\npydantic>=2.0\n",
                encoding="utf-8",
            )
            write_theme_css(ws / "apps" / "web")
            (ws / "apps" / "web" / "index.html").write_text(
                placeholder_portal_html(
                    project_title or "Studio 项目",
                    "点击平台「生成」以写入业务逻辑。",
                    badge="待生成",
                ),
                encoding="utf-8",
            )
            (ws / "apps" / "web" / "app.js").write_text(
                "console.log('studio web placeholder');\n",
                encoding="utf-8",
            )
            (ws / "apps" / "web" / "package.json").write_text(
                json.dumps(
                    {
                        "name": "studio-web",
                        "private": True,
                        "type": "module",
                        "scripts": {
                            "dev": "npx --yes serve -l 5175 .",
                            "build": "echo 'Static site - no build required'",
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            # 生成部署脚手架
            try:
                scaffold_deploy_files(
                    ws,
                    project_id=project_root.replace("/", "-"),
                    goal=goal,
                    has_frontend=True,
                    has_backend=True,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[WARN] 部署脚手架生成失败: {exc}")

            # 生成 CI/CD 流水线
            try:
                scaffold_cicd(ws, platform="github")
            except Exception as exc:  # noqa: BLE001
                print(f"[WARN] CI/CD 生成失败: {exc}")

        if project_mode and project_root and not frontend_dir:
            frontend_dir = f"{project_root.rstrip('/')}/apps/web"
        if not frontend_dir:
            frontend_dir = "apps/demo-code-agent/frontend"

        params: dict[str, Any] = {
            "goal": goal,
            "pass_on_attempt": body.pass_on_attempt,
            "review_status": body.review_status,
            "frontend_dir": frontend_dir,
            "project_mode": project_mode,
            "coding_max_tasks": 5,
        }
        if project_root:
            params["project_root"] = project_root.replace("\\", "/")
        if project_title:
            params["project_title"] = project_title
        if body.srs_excerpt:
            params["srs_excerpt"] = body.srs_excerpt[:14000]
        if body.phase_id:
            params["phase_id"] = body.phase_id
        if project_mode and project_root:
            ensure_project_metric(config.workspace_path(), params, write_acceptance=True)

        engine = WorkflowEngine(config)
        try:
            if body.async_mode:
                record = engine.run_async(path, params_override=params)
            else:
                record = engine.run(path, params_override=params)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"执行失败: {exc}") from exc

        return {
            "run": record.to_dict(),
            "stages": _stages_from_outputs(record.node_outputs),
            "workflow": DELIVER_WORKFLOW,
            "project_mode": project_mode,
            "project_root": project_root,
            "frontend_dir": frontend_dir,
        }

    @app.get("/api/platform/studio/runs/{run_id}/stages")
    def studio_stages(run_id: str) -> dict[str, Any]:
        store = RunStore(config.workspace_path())
        run = store.load_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"run 不存在: {run_id}")
        return {
            "run": run.to_dict(),
            "stages": _stages_from_outputs(run.node_outputs),
            "stage_node_map": STAGE_NODE_MAP,
        }

    @app.get("/api/platform/studio/runs/{run_id}/stream")
    def studio_run_stream(run_id: str):
        """SSE 端点：实时推送工作流执行事件。"""
        import asyncio
        import time as _time

        store = RunStore(config.workspace_path())

        def event_generator():
            last_event_count = 0
            start_time = _time.monotonic()
            max_wait = 1800  # 30 分钟超时

            while True:
                if _time.monotonic() - start_time > max_wait:
                    yield f"event: timeout\ndata: {json.dumps({'run_id': run_id, 'timeout': True})}\n\n"
                    return

                run = store.load_run(run_id)
                if run is None:
                    yield f"event: error\ndata: {json.dumps({'error': 'run not found'})}\n\n"
                    return

                events = store.read_events(run_id)
                new_events = events[last_event_count:]
                last_event_count = len(events)

                for evt in new_events:
                    yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"

                # 推送当前状态快照
                status_snapshot = {
                    "type": "status",
                    "run_id": run_id,
                    "status": run.status,
                    "current_node_id": run.current_node_id,
                    "completed_nodes": len(run.node_outputs),
                    "total_nodes": 8,
                    "node_outputs_keys": list(run.node_outputs.keys()),
                    "failed_node_id": run.failed_node_id,
                    "error": run.error,
                    "ts": _time.time(),
                }
                yield f"event: status\ndata: {json.dumps(status_snapshot, ensure_ascii=False)}\n\n"

                terminal = {"DONE", "FAILED", "CANCELLED", "WAITING_USER"}
                if run.status.upper() in terminal:
                    yield f"event: done\ndata: {json.dumps({'run_id': run_id, 'status': run.status, 'final': True})}\n\n"
                    return

                _time.sleep(0.5)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get("/api/platform/studio/project/tree")
    def studio_project_tree(
        project_root: str = Query(...),
        max_files: int = 500,
    ) -> dict[str, Any]:
        root = (project_root or "").strip().replace("\\", "/").lstrip("/")
        if not root:
            raise HTTPException(status_code=400, detail="project_root 不能为空")
        ws = config.workspace_path() / root
        if not ws.is_dir():
            raise HTTPException(status_code=404, detail="工作区目录不存在")

        skip = {"node_modules", ".git", "__pycache__", ".venv", "venv", ".mawp"}
        paths: list[str] = []
        for path in sorted(ws.rglob("*")):
            if not path.is_file():
                continue
            if skip.intersection(path.relative_to(ws).parts):
                continue
            paths.append(path.relative_to(ws).as_posix())
            if len(paths) >= max(50, min(max_files, 2000)):
                break
        return {"project_root": root, "workspace": str(ws), "paths": paths, "truncated": len(paths) >= max_files}

    @app.get("/api/platform/studio/project/file")
    def studio_project_file(
        project_root: str = Query(...),
        path: str = Query(...),
        max_chars: int = 120_000,
    ) -> dict[str, Any]:
        root = (project_root or "").strip().replace("\\", "/").lstrip("/")
        rel = (path or "").replace("\\", "/").lstrip("/")
        if not root or not rel or ".." in rel.split("/"):
            raise HTTPException(status_code=400, detail="非法路径")
        ws = (config.workspace_path() / root).resolve()
        target = (ws / rel).resolve()
        try:
            target.relative_to(ws)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="路径越界") from exc
        if not target.is_file():
            raise HTTPException(status_code=404, detail="文件不存在")
        if target.stat().st_size > 2_000_000:
            raise HTTPException(status_code=400, detail="文件过大，请本地打开")
        try:
            text = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=415, detail="暂不支持预览二进制文件") from None
        truncated = len(text) > max_chars
        if truncated:
            text = text[:max_chars]
        return {"project_root": root, "path": rel, "content": text, "truncated": truncated, "size": target.stat().st_size}

    @app.get("/api/platform/studio/project/zip")
    def studio_project_zip(project_root: str = Query(...)) -> Response:
        root = (project_root or "").strip().replace("\\", "/").lstrip("/")
        if not root:
            raise HTTPException(status_code=400, detail="project_root 不能为空")
        ws = (config.workspace_path() / root).resolve()
        if not ws.is_dir():
            raise HTTPException(status_code=404, detail="工作区目录不存在")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(ws.rglob("*")):
                if not path.is_file():
                    continue
                parts = set(path.relative_to(ws).parts)
                if parts & {"node_modules", ".git", "__pycache__", ".venv", "venv", ".mawp"}:
                    continue
                zf.write(path, arcname=path.relative_to(ws).as_posix())
        data = buf.getvalue()
        filename = f"{Path(root).name or 'project'}.zip"
        return Response(content=data, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{filename}"'})

    # —— 版本管理 API ——

    @app.get("/api/platform/studio/project/versions")
    def studio_project_versions(project_root: str = Query(...)) -> dict[str, Any]:
        """列出所有版本快照。"""
        from mawp.runtime.version_manager import list_version_snapshots

        root = (project_root or "").strip().replace("\\", "/").lstrip("/")
        if not root:
            raise HTTPException(status_code=400, detail="project_root 不能为空")
        ws = (config.workspace_path() / root).resolve()
        if not ws.is_dir():
            raise HTTPException(status_code=404, detail="工作区目录不存在")
        return list_version_snapshots(ws)

    @app.post("/api/platform/studio/project/versions/create")
    def studio_project_version_create(
        project_root: str = Query(...),
        label: str = Query(default=""),
        note: str = Query(default=""),
        run_id: str = Query(default=""),
    ) -> dict[str, Any]:
        """手动创建版本快照。"""
        from mawp.runtime.version_manager import create_version_snapshot

        root = (project_root or "").strip().replace("\\", "/").lstrip("/")
        if not root:
            raise HTTPException(status_code=400, detail="project_root 不能为空")
        ws = (config.workspace_path() / root).resolve()
        if not ws.is_dir():
            raise HTTPException(status_code=404, detail="工作区目录不存在")
        return create_version_snapshot(ws, run_id=run_id or None, label=label or None, note=note or None)

    @app.get("/api/platform/studio/project/versions/{snapshot_id}/diff")
    def studio_project_version_diff(
        project_root: str = Query(...),
        snapshot_id: str = "",
        path: str = Query(default=""),
    ) -> dict[str, Any]:
        """对比指定版本与当前项目。"""
        from mawp.runtime.version_manager import diff_snapshot_to_current

        root = (project_root or "").strip().replace("\\", "/").lstrip("/")
        if not root:
            raise HTTPException(status_code=400, detail="project_root 不能为空")
        ws = (config.workspace_path() / root).resolve()
        if not ws.is_dir():
            raise HTTPException(status_code=404, detail="工作区目录不存在")
        return diff_snapshot_to_current(ws, snapshot_id, rel_path=path or None)

    @app.post("/api/platform/studio/project/versions/{snapshot_id}/restore")
    def studio_project_version_restore(
        project_root: str = Query(...),
        snapshot_id: str = "",
    ) -> dict[str, Any]:
        """回滚到指定版本。"""
        from mawp.runtime.version_manager import restore_version_snapshot

        root = (project_root or "").strip().replace("\\", "/").lstrip("/")
        if not root:
            raise HTTPException(status_code=400, detail="project_root 不能为空")
        ws = (config.workspace_path() / root).resolve()
        if not ws.is_dir():
            raise HTTPException(status_code=404, detail="工作区目录不存在")
        # 回滚前先创建当前状态的快照
        from mawp.runtime.version_manager import create_version_snapshot

        create_version_snapshot(ws, label=f"pre-restore-{snapshot_id}", note="auto snapshot before restore")
        return restore_version_snapshot(ws, snapshot_id)

    @app.get("/api/platform/studio/project/diff")
    def studio_project_diff(
        project_root: str = Query(...),
        path: str = Query(...),
    ) -> dict[str, Any]:
        """获取文件相对于上一次保存的 diff（需要传入 old_content 进行比较）。"""
        import difflib

        root = (project_root or "").strip().replace("\\", "/").lstrip("/")
        rel = (path or "").replace("\\", "/").lstrip("/")
        if not root or not rel or ".." in rel.split("/"):
            raise HTTPException(status_code=400, detail="非法路径")
        ws = (config.workspace_path() / root).resolve()
        target = (ws / rel).resolve()
        try:
            target.relative_to(ws)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="路径越界") from exc
        if not target.is_file():
            raise HTTPException(status_code=404, detail="文件不存在")
        try:
            new_content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=415, detail="暂不支持 diff 二进制文件") from None
        return {
            "project_root": root,
            "path": rel,
            "exists": True,
            "size": target.stat().st_size,
            "content": new_content,
        }

    @app.post("/api/platform/studio/project/diff-compare")
    def studio_project_diff_compare(
        project_root: str = Query(...),
        path: str = Query(...),
        old_content: str = Query(default=""),
    ) -> dict[str, Any]:
        """比较文件内容 diff。"""
        import difflib

        root = (project_root or "").strip().replace("\\", "/").lstrip("/")
        rel = (path or "").replace("\\", "/").lstrip("/")
        if not root or not rel or ".." in rel.split("/"):
            raise HTTPException(status_code=400, detail="非法路径")
        ws = (config.workspace_path() / root).resolve()
        target = (ws / rel).resolve()
        try:
            target.relative_to(ws)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="路径越界") from exc
        if not target.is_file():
            raise HTTPException(status_code=404, detail="文件不存在")
        try:
            new_content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=415, detail="暂不支持 diff 二进制文件") from None

        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = list(difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{rel}", tofile=f"b/{rel}"))
        return {
            "project_root": root,
            "path": rel,
            "has_diff": len(diff) > 0,
            "diff": "".join(diff),
            "old_size": len(old_content.encode("utf-8")),
            "new_size": len(new_content.encode("utf-8")),
        }

    @app.post("/api/platform/studio/project/save")
    def studio_project_save(body: SaveFileBody) -> dict[str, Any]:
        """保存文件到项目工作区（在线编辑回写）。"""
        root = (body.project_root or "").strip().replace("\\", "/").lstrip("/")
        rel = (body.path or "").replace("\\", "/").lstrip("/")
        if not root or not rel or ".." in rel.split("/"):
            raise HTTPException(status_code=400, detail="非法路径")
        ws = (config.workspace_path() / root).resolve()
        target = (ws / rel).resolve()
        try:
            target.relative_to(ws)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="路径越界") from exc
        target.parent.mkdir(parents=True, exist_ok=True)
        existed = target.is_file()
        old_size = target.stat().st_size if existed else 0
        target.write_text(body.content, encoding="utf-8")
        new_size = target.stat().st_size
        return {
            "project_root": root,
            "path": rel,
            "saved": True,
            "created": not existed,
            "old_size": old_size,
            "new_size": new_size,
        }

    @app.post("/api/platform/runs/{run_id}/retry")
    def retry_failed_run(
        run_id: str,
        body: RetryRunBody | None = None,
    ) -> dict[str, Any]:
        """重试失败的工作流运行。"""
        store = RunStore(config.workspace_path())
        run = store.load_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"run 不存在: {run_id}")
        if run.status != "FAILED":
            raise HTTPException(status_code=400, detail=f"run 状态为 {run.status}，只有 FAILED 才能重试")

        # 保留已有 outputs，从失败节点重新开始
        run.status = "RUNNING"
        run.error = None
        run.failed_node_id = None
        store.save_run(run)
        store.append_event(
            run_id,
            {"type": "retry_start", "from_node": run.current_node_id},
        )

        engine = WorkflowEngine(config)
        try:
            record = engine.resume(run_id, "approve", data=None)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"重试失败: {exc}") from exc
        return {
            "run": record.to_dict(),
            "stages": _stages_from_outputs(record.node_outputs),
        }

    @app.post("/api/platform/runs/{run_id}/resume")
    def resume_run(run_id: str, body: ResumeBody) -> dict[str, Any]:
        action = (body.action or "approve").strip().lower()
        if action not in {"approve", "reject", "input"}:
            raise HTTPException(status_code=400, detail="action 须为 approve/reject/input")
        engine = WorkflowEngine(config)
        try:
            record = engine.resume(run_id, action, data=body.data)  # type: ignore[arg-type]
        except (IllegalStateError, ResumeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"恢复失败: {exc}") from exc
        return {
            "run": record.to_dict(),
            "stages": _stages_from_outputs(record.node_outputs),
        }

    # —— 高级项目（分期交付）——
    adv_store = AdvancedProjectStore(config.workspace_path())

    @app.get("/api/platform/advanced/projects")
    def list_advanced_projects() -> dict[str, Any]:
        items = [p.to_dict() for p in adv_store.list_projects()]
        return {"projects": items}

    @app.get("/api/platform/advanced/projects/{project_id}")
    def get_advanced_project(project_id: str) -> dict[str, Any]:
        project = adv_store.load(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="高级项目不存在")
        return {"project": project.to_dict()}

    @app.post("/api/platform/advanced/projects")
    async def create_advanced_project(
        title: Annotated[str, Form()] = "",
        text: Annotated[str, Form()] = "",
        file: Annotated[Optional[UploadFile], File()] = None,
    ) -> dict[str, Any]:
        from mawp.advanced import extract_plaintext, scaffold_project

        raw = b""
        filename = "pasted.txt"
        if file is not None and file.filename:
            filename = str(file.filename)
            raw = await file.read()

        try:
            if raw:
                srs = extract_plaintext(filename, raw)
            else:
                srs = text.strip()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        if len(srs) < 40:
            raise HTTPException(status_code=400, detail="需求文本过短，请上传完整 SRS/DOCX")

        project_title = title.strip() or Path(filename).stem or "高级项目"
        project = scaffold_project(
            adv_store,
            title=project_title,
            srs_text=srs,
            source_filename=filename,
        )
        return {"project": project.to_dict()}

    @app.post("/api/platform/advanced/projects/{project_id}/generate")
    def generate_advanced_phase(
        project_id: str,
        use_agents: bool = True,
        async_mode: bool = False,
        verify_only: bool = False,
    ) -> dict[str, Any]:
        from mawp.advanced import generate_current_phase

        try:
            result = generate_current_phase(
                adv_store,
                project_id,
                config=config,
                use_agents=use_agents,
                async_mode=async_mode,
                verify_only=verify_only,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"生成失败: {exc}") from exc
        return result

    @app.post("/api/platform/advanced/projects/{project_id}/generate-remaining")
    def generate_advanced_remaining(
        project_id: str,
        use_agents: bool = True,
        max_phases: int = 8,
        stop_on_smoke_fail: bool = True,
        parallel_workers: int = 2,
    ) -> dict[str, Any]:
        """按依赖波次生成剩余里程碑（默认可沙箱并行；冒烟失败可提前停）。"""
        from mawp.advanced import generate_remaining_phases

        try:
            return generate_remaining_phases(
                adv_store,
                project_id,
                config=config,
                use_agents=use_agents,
                max_phases=max_phases,
                stop_on_smoke_fail=stop_on_smoke_fail,
                parallel_workers=parallel_workers,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"批量生成失败: {exc}") from exc

    @app.get("/api/platform/advanced/projects/{project_id}/export.zip")
    def export_advanced_project_zip(project_id: str) -> Response:
        project = adv_store.load(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="高级项目不存在")
        workspace = Path(project.workspace)
        if not workspace.is_dir():
            raise HTTPException(status_code=404, detail="工作区目录不存在")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(workspace.rglob("*")):
                if not path.is_file():
                    continue
                # 跳过体积过大的缓存目录
                parts = set(path.relative_to(workspace).parts)
                if parts & {"node_modules", ".git", "__pycache__", ".venv", "venv"}:
                    continue
                arc = path.relative_to(workspace).as_posix()
                zf.write(path, arcname=arc)
        data = buf.getvalue()
        filename = f"{project.id}.zip"
        return Response(
            content=data,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )

    @app.get("/api/platform/advanced/projects/{project_id}/tree")
    def advanced_project_tree(
        project_id: str,
        max_files: int = 500,
    ) -> dict[str, Any]:
        project = adv_store.load(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="高级项目不存在")
        workspace = Path(project.workspace)
        if not workspace.is_dir():
            raise HTTPException(status_code=404, detail="工作区目录不存在")

        skip = {"node_modules", ".git", "__pycache__", ".venv", "venv", ".mawp"}
        paths: list[str] = []
        for path in sorted(workspace.rglob("*")):
            if not path.is_file():
                continue
            rel_parts = path.relative_to(workspace).parts
            if skip.intersection(rel_parts):
                continue
            paths.append(path.relative_to(workspace).as_posix())
            if len(paths) >= max(50, min(max_files, 2000)):
                break
        return {
            "project_id": project_id,
            "workspace": str(workspace),
            "paths": paths,
            "truncated": len(paths) >= max_files,
        }

    @app.get("/api/platform/advanced/projects/{project_id}/file")
    def advanced_project_file(
        project_id: str,
        path: str,
        max_chars: int = 120_000,
    ) -> dict[str, Any]:
        """读取工作区内文本文件，供工程树预览 / diff。"""
        project = adv_store.load(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="高级项目不存在")
        workspace = Path(project.workspace).resolve()
        rel = (path or "").replace("\\", "/").lstrip("/")
        if not rel or ".." in rel.split("/"):
            raise HTTPException(status_code=400, detail="非法路径")
        target = (workspace / rel).resolve()
        try:
            target.relative_to(workspace)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="路径越界") from exc
        if not target.is_file():
            raise HTTPException(status_code=404, detail="文件不存在")
        if target.stat().st_size > 2_000_000:
            raise HTTPException(status_code=400, detail="文件过大，请本地打开")
        try:
            text = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=415, detail="暂不支持预览二进制文件") from None
        truncated = len(text) > max_chars
        if truncated:
            text = text[:max_chars]
        return {
            "project_id": project_id,
            "path": rel,
            "content": text,
            "truncated": truncated,
            "size": target.stat().st_size,
        }

    return app


def create_app(config: AgentConfig | None = None) -> FastAPI:
    """Uvicorn factory 入口。"""
    return create_platform_app(config or load_config())
