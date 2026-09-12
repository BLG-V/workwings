"""coding 后确定性装配门禁：扫描 routers/ 补挂 main.py，缺挂载冒烟失败。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from mawp.config.loader import load_config
from mawp.runtime.agents import AgentRunContext
from mawp.runtime.assembly_gate import (
    assemble_project,
    detect_router_symbol,
    find_unmounted_routers,
    is_router_mounted,
)
from mawp.runtime.deliver_specs import DELIVER_AGENTS
from mawp.runtime.error_classifier import classify_error
from mawp.runtime.hybrid import HybridAgentRunner
from mawp.runtime.project_deliver import write_smoke_script


ROUTER_SRC = '''\
"""example router."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/ai", tags=["ai"])

@router.get("/ping")
def ping():
    return {"ok": True}
'''

MAIN_SRC = '''\
from fastapi import FastAPI

app = FastAPI(title="Demo")

@app.get("/health")
def health():
    return {"ok": True}
'''


def _api_tree(tmp_path: Path, *, router: bool = True, mounted: bool = False) -> Path:
    api = tmp_path / "workspaces" / "demo" / "apps" / "api"
    (api / "routers").mkdir(parents=True)
    (api / "routers" / "__init__.py").write_text('"""routers."""\n', encoding="utf-8")
    (api / "main.py").write_text(MAIN_SRC, encoding="utf-8")
    (api / "requirements.txt").write_text("fastapi>=0.110\n", encoding="utf-8")
    if router:
        (api / "routers" / "ai_gateway.py").write_text(ROUTER_SRC, encoding="utf-8")
        if mounted:
            main = api / "main.py"
            main.write_text(
                MAIN_SRC
                + "\nfrom routers.ai_gateway import router as ai_gateway_router\n"
                + "app.include_router(ai_gateway_router)\n",
                encoding="utf-8",
            )
    web = tmp_path / "workspaces" / "demo" / "apps" / "web"
    web.mkdir(parents=True, exist_ok=True)
    (web / "index.html").write_text("<html></html>", encoding="utf-8")
    return api


def test_detect_router_symbol() -> None:
    assert detect_router_symbol(ROUTER_SRC) == "router"
    assert detect_router_symbol("x = 1\n") is None
    assert (
        detect_router_symbol("bills_router = APIRouter(prefix='/api/bills')\n")
        == "bills_router"
    )


def test_find_unmounted_routers(tmp_path: Path) -> None:
    api = _api_tree(tmp_path, router=True, mounted=False)
    found = find_unmounted_routers(api)
    assert [f.rel_path for f in found] == ["routers/ai_gateway.py"]
    assert found[0].module == "routers.ai_gateway"
    assert found[0].symbol == "router"


def test_find_unmounted_skips_helpers_and_init(tmp_path: Path) -> None:
    api = _api_tree(tmp_path, router=True, mounted=False)
    (api / "routers" / "helpers.py").write_text("VALUE = 1\n", encoding="utf-8")
    found = find_unmounted_routers(api)
    assert [f.rel_path for f in found] == ["routers/ai_gateway.py"]


def test_already_mounted_is_not_reported(tmp_path: Path) -> None:
    api = _api_tree(tmp_path, router=True, mounted=True)
    assert find_unmounted_routers(api) == []
    assert is_router_mounted(
        (api / "main.py").read_text(encoding="utf-8"),
        module="routers.ai_gateway",
        stem="ai_gateway",
    )


def test_assemble_project_mounts_missing_router(tmp_path: Path) -> None:
    _api_tree(tmp_path, router=True, mounted=False)
    report = assemble_project(tmp_path, "workspaces/demo")
    assert report.mounted == ["routers/ai_gateway.py"]
    main = (tmp_path / "workspaces/demo/apps/api/main.py").read_text(encoding="utf-8")
    assert "from routers.ai_gateway import router as ai_gateway_router" in main
    assert "app.include_router(ai_gateway_router)" in main
    assert find_unmounted_routers(tmp_path / "workspaces/demo/apps/api") == []


def test_assemble_project_is_idempotent(tmp_path: Path) -> None:
    _api_tree(tmp_path, router=True, mounted=False)
    first = assemble_project(tmp_path, "workspaces/demo")
    second = assemble_project(tmp_path, "workspaces/demo")
    assert first.mounted
    assert second.mounted == []
    main = (tmp_path / "workspaces/demo/apps/api/main.py").read_text(encoding="utf-8")
    assert main.count("include_router(ai_gateway_router)") == 1


def _run_smoke(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    root = "workspaces/demo"
    write_smoke_script(tmp_path, root)
    script = tmp_path / root / "scripts" / "smoke_check.py"
    env = os.environ.copy()
    env["MAWP_SMOKE_API_INSTALL"] = "0"
    env["MAWP_SMOKE_WEB_BUILD"] = "0"
    env["MAWP_SMOKE_LIVE"] = "0"
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
        check=False,
    )


def test_smoke_fails_when_router_unmounted(tmp_path: Path) -> None:
    _api_tree(tmp_path, router=True, mounted=False)
    proc = _run_smoke(tmp_path)
    assert proc.returncode != 0
    combined = (proc.stdout or "") + (proc.stderr or "")
    assert "unmounted router" in combined
    assert "ai_gateway.py" in combined


def test_smoke_passes_after_assemble(tmp_path: Path) -> None:
    _api_tree(tmp_path, router=True, mounted=False)
    assemble_project(tmp_path, "workspaces/demo")
    proc = _run_smoke(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SMOKE PASS" in (proc.stdout or "")


def test_coding_project_loop_auto_mounts_existing_router(monkeypatch, tmp_path: Path) -> None:
    for env_var in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(env_var, raising=False)
    _api_tree(tmp_path, router=True, mounted=False)
    base = load_config()
    config = base.model_copy(
        update={
            "workspace": str(tmp_path),
            "llm": base.llm.model_copy(update={"provider": "mock", "api_key": None}),
        }
    )
    runner = HybridAgentRunner(config)
    ctx = AgentRunContext(
        run_id="r-asm",
        params={
            "project_mode": True,
            "project_root": "workspaces/demo",
            "project_title": "Demo",
            "goal": "scaffold",
        },
        nodes_outputs={"planner": {"tasks": [{"id": "T1", "title": "api"}]}},
        node_id="coding",
    )
    result = runner.run("coding", {}, ctx)
    assert result.success
    assembly = (result.output or {}).get("assembly") or {}
    assert assembly.get("mounted")
    main = (tmp_path / "workspaces/demo/apps/api/main.py").read_text(encoding="utf-8")
    assert "include_router(ai_gateway_router)" in main
    assert "apps/api/main.py" in " ".join(result.output.get("changed_files") or [])


def test_unmounted_router_classifies_as_route_error() -> None:
    cls = classify_error(
        "unmounted router: routers/ai_gateway.py (missing include_router in apps/api/main.py)"
    )
    assert cls.category == "route_error"
    assert cls.fix_strategy == "fix_route"
    page = classify_error("unlinked page: ai.html (missing from index.html)")
    assert page.category == "route_error"


def test_deliver_chain_still_has_eight_agents() -> None:
    assert DELIVER_AGENTS == (
        "planner",
        "requirement",
        "coding",
        "frontend",
        "testing",
        "debug",
        "review",
        "ship",
    )


ROOT_ROUTER_SRC = '''\
"""root-level phase module."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/p5", tags=["p5"])

@router.get("/ping")
def ping():
    return {"ok": True}
'''


def test_find_unmounted_includes_root_module_router(tmp_path: Path) -> None:
    api = _api_tree(tmp_path, router=False, mounted=False)
    (api / "module_p5.py").write_text(ROOT_ROUTER_SRC, encoding="utf-8")
    found = find_unmounted_routers(api)
    assert [f.rel_path for f in found] == ["module_p5.py"]
    assert found[0].module == "module_p5"


def test_assemble_mounts_root_module_and_prefers_package_import(tmp_path: Path) -> None:
    api = _api_tree(tmp_path, router=True, mounted=False)
    (api / "module_p5.py").write_text(ROOT_ROUTER_SRC, encoding="utf-8")
    # 已有 package 风格 import 时，新增 routers 模块应并入，而不是另起一行 from routers.x
    (api / "main.py").write_text(
        MAIN_SRC
        + "\nfrom routers import repairs\n"
        + "app.include_router(repairs.router)\n",
        encoding="utf-8",
    )
    (api / "routers" / "repairs.py").write_text(ROUTER_SRC.replace("ai", "repairs"), encoding="utf-8")

    report = assemble_project(tmp_path, "workspaces/demo")
    assert "routers/ai_gateway.py" in report.mounted
    assert "module_p5.py" in report.mounted
    main = (api / "main.py").read_text(encoding="utf-8")
    assert "from routers import" in main and "ai_gateway" in main
    assert "from routers.ai_gateway import" not in main
    assert "app.include_router(ai_gateway.router)" in main
    assert "from module_p5 import router as module_p5_router" in main
    assert "app.include_router(module_p5_router)" in main


def test_assemble_links_orphan_html_into_index(tmp_path: Path) -> None:
    from mawp.runtime.web_scaffold import PORTAL_END, portal_html

    _api_tree(tmp_path, router=False, mounted=False)
    web = tmp_path / "workspaces" / "demo" / "apps" / "web"
    (web / "index.html").write_text(portal_html(title="Demo", cards=[]), encoding="utf-8")
    (web / "ai.html").write_text("<html><body>AI</body></html>", encoding="utf-8")

    report = assemble_project(tmp_path, "workspaces/demo")
    assert "ai.html" in (report.linked_pages or [])
    index = (web / "index.html").read_text(encoding="utf-8")
    assert "ai.html" in index
    assert PORTAL_END in index
    # 再次装配幂等
    again = assemble_project(tmp_path, "workspaces/demo")
    assert again.linked_pages == []


def test_smoke_fails_when_root_router_or_html_unlinked(tmp_path: Path) -> None:
    from mawp.runtime.web_scaffold import portal_html

    api = _api_tree(tmp_path, router=False, mounted=False)
    (api / "module_p5.py").write_text(ROOT_ROUTER_SRC, encoding="utf-8")
    web = tmp_path / "workspaces" / "demo" / "apps" / "web"
    (web / "index.html").write_text(portal_html(title="Demo", cards=[]), encoding="utf-8")
    (web / "ai.html").write_text("<html><body>AI</body></html>", encoding="utf-8")

    proc = _run_smoke(tmp_path)
    assert proc.returncode != 0
    combined = (proc.stdout or "") + (proc.stderr or "")
    assert "unmounted router" in combined and "module_p5.py" in combined
    assert "unlinked page" in combined and "ai.html" in combined
