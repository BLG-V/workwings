from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from mawp.config.loader import AgentConfig
from mawp.web.progress import WorkflowProgressService

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(config: AgentConfig) -> FastAPI:
    app = FastAPI(
        title="AI Code Agent",
        description="Goal Workflow 进度 Web UI",
        version="0.1.0",
    )
    service = WorkflowProgressService(config)

    @app.get("/api/health")
    def health() -> dict:
        return {
            "status": "ok",
            "workspace": str(config.workspace_path()),
        }

    @app.get("/api/workflows")
    def list_workflows() -> dict:
        items = service.list_workflows()
        return {"workflows": [w.model_dump() for w in items]}

    @app.get("/api/workflows/{slug}")
    def get_workflow(slug: str) -> dict:
        try:
            detail = service.get_workflow(slug)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return detail.model_dump()

    @app.get("/api/issues")
    def list_issues() -> dict:
        items = service.list_all_issues()
        return {"issues": [i.model_dump() for i in items]}

    @app.get("/api/issues/{issue_id}")
    def get_issue(issue_id: str) -> dict:
        try:
            return service.get_issue(issue_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    return app
