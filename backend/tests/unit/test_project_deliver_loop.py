"""project_mode：Coding 任务循环 + 真实 metric 验收。"""

from __future__ import annotations

from pathlib import Path

from mawp.config.loader import load_config
from mawp.runtime.agents import AgentRunContext
from mawp.runtime.hybrid import HybridAgentRunner
from mawp.runtime.project_deliver import (
    default_metric_command,
    ensure_project_metric,
    extract_tasks_from_ctx,
    write_smoke_script,
)


def test_extract_tasks_fallback() -> None:
    tasks = extract_tasks_from_ctx({}, {}, goal="做报修 API")
    assert len(tasks) == 1
    assert tasks[0]["id"] == "T1"


def test_ensure_project_metric_writes_smoke(tmp_path: Path) -> None:
    root = "workspaces/demo"
    (tmp_path / root / "apps" / "api").mkdir(parents=True)
    (tmp_path / root / "apps" / "web").mkdir(parents=True)
    (tmp_path / root / "apps" / "api" / "main.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / root / "apps" / "web" / "index.html").write_text("<html></html>", encoding="utf-8")
    params = {
        "project_mode": True,
        "project_root": root,
        "phase_id": "p1",
    }
    metric = ensure_project_metric(tmp_path, params)
    assert metric == default_metric_command(root)
    assert (tmp_path / root / "scripts" / "smoke_check.py").is_file()
    assert (tmp_path / root / "docs" / "ACCEPTANCE_P1.md").is_file()


def test_hybrid_project_coding_stub_loop(monkeypatch, tmp_path: Path) -> None:
    for env_var in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(env_var, raising=False)
    base = load_config()
    config = base.model_copy(
        update={
            "workspace": str(tmp_path),
            "llm": base.llm.model_copy(update={"provider": "mock", "api_key": None}),
        }
    )
    root = "workspaces/proj"
    (tmp_path / root).mkdir(parents=True)
    runner = HybridAgentRunner(config)
    assert runner.llm_enabled is False

    ctx = AgentRunContext(
        run_id="r1",
        params={
            "project_mode": True,
            "project_root": root,
            "project_title": "Demo",
            "goal": "scaffold",
            "phase_id": "p1",
        },
        nodes_outputs={
            "planner": {
                "tasks": [
                    {"id": "T1", "title": "api"},
                    {"id": "T2", "title": "docs"},
                ]
            }
        },
        node_id="coding",
    )
    result = runner.run("coding", {}, ctx)
    assert result.success
    assert result.output["mode"] == "project_stub_loop"
    assert len(result.output["task_runs"]) == 2
    assert result.output["changed_files"]
    for rel in result.output["changed_files"]:
        assert (tmp_path / rel).is_file()


def test_hybrid_coding_resume_skips_successful_tasks(monkeypatch, tmp_path: Path) -> None:
    """自愈/重跑 coding：已成功子任务跳过，只跑失败项。"""
    for env_var in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(env_var, raising=False)
    base = load_config()
    config = base.model_copy(
        update={
            "workspace": str(tmp_path),
            "llm": base.llm.model_copy(update={"provider": "mock", "api_key": None}),
        }
    )
    root = "workspaces/resume"
    (tmp_path / root).mkdir(parents=True)
    runner = HybridAgentRunner(config)

    called: list[str] = []
    real_stub = runner._run_coding_project_stub

    def wrap_stub(goal, tasks, input_data, ctx):  # type: ignore[no-untyped-def]
        for t in tasks:
            called.append(str(t.get("id")))
        return real_stub(goal, tasks, input_data, ctx)

    monkeypatch.setattr(runner, "_run_coding_project_stub", wrap_stub)

    ctx = AgentRunContext(
        run_id="r-resume",
        params={
            "project_mode": True,
            "project_root": root,
            "project_title": "Resume",
            "goal": "feature",
            "phase_id": "p1",
        },
        nodes_outputs={
            "planner": {
                "tasks": [
                    {"id": "T1", "title": "api"},
                    {"id": "T2", "title": "ui"},
                    {"id": "T3", "title": "docs"},
                ]
            },
            "coding": {
                "tasks_done": ["T1"],
                "changed_files": [f"{root}/apps/api/main.py"],
                "task_runs": [
                    {
                        "task_id": "T1",
                        "success": True,
                        "changed_files": [f"{root}/apps/api/main.py"],
                    },
                    {
                        "task_id": "T2",
                        "success": False,
                        "error": "timed out",
                        "changed_files": [],
                    },
                ],
            },
        },
        node_id="coding",
    )
    result = runner.run("coding", {}, ctx)
    assert result.success
    assert result.output.get("resumed") is True
    assert result.output.get("skipped_tasks") == 1
    assert called == ["T2", "T3"]
    assert "T1" in result.output["tasks_done"]
    assert any(r.get("task_id") == "T1" and r.get("skipped") for r in result.output["task_runs"])


def test_hybrid_coding_resume_all_done_noop(monkeypatch, tmp_path: Path) -> None:
    for env_var in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(env_var, raising=False)
    base = load_config()
    config = base.model_copy(
        update={
            "workspace": str(tmp_path),
            "llm": base.llm.model_copy(update={"provider": "mock", "api_key": None}),
        }
    )
    root = "workspaces/done"
    (tmp_path / root).mkdir(parents=True)
    runner = HybridAgentRunner(config)
    called = {"n": 0}

    def boom(*_a, **_k):
        called["n"] += 1
        raise AssertionError("should not stub when all tasks already done")

    monkeypatch.setattr(runner, "_run_coding_project_stub", boom)
    ctx = AgentRunContext(
        run_id="r-done",
        params={
            "project_mode": True,
            "project_root": root,
            "goal": "x",
            "phase_id": "p1",
        },
        nodes_outputs={
            "planner": {"tasks": [{"id": "T1", "title": "a"}, {"id": "T2", "title": "b"}]},
            "coding": {
                "tasks_done": ["T1", "T2"],
                "changed_files": [f"{root}/ok.py"],
                "task_runs": [
                    {"task_id": "T1", "success": True, "changed_files": [f"{root}/ok.py"]},
                    {"task_id": "T2", "success": True, "changed_files": []},
                ],
            },
        },
        node_id="coding",
    )
    result = runner.run("coding", {}, ctx)
    assert called["n"] == 0
    assert result.success
    assert result.output["resumed"] is True
    assert result.output["skipped_tasks"] == 2
    assert result.output["tasks_done"] == ["T1", "T2"]

def test_hybrid_project_real_testing(monkeypatch, tmp_path: Path) -> None:
    for env_var in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(env_var, raising=False)
    base = load_config()
    config = base.model_copy(
        update={
            "workspace": str(tmp_path),
            "llm": base.llm.model_copy(update={"provider": "mock", "api_key": None}),
        }
    )
    root = "workspaces/proj2"
    (tmp_path / root / "apps" / "api").mkdir(parents=True)
    (tmp_path / root / "apps" / "web").mkdir(parents=True)
    (tmp_path / root / "apps" / "api" / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n"
        "@app.get('/health')\ndef health():\n    return {'ok': True}\n"
        "@app.get('/api/repairs')\ndef repairs():\n    return {'items': [], 'total': 0}\n",
        encoding="utf-8",
    )
    (tmp_path / root / "apps" / "api" / "requirements.txt").write_text(
        "fastapi>=0.110\n", encoding="utf-8"
    )
    (tmp_path / root / "apps" / "web" / "index.html").write_text("<html></html>", encoding="utf-8")
    write_smoke_script(tmp_path, root)

    runner = HybridAgentRunner(config)
    ctx = AgentRunContext(
        run_id="r2",
        params={
            "project_mode": True,
            "project_root": root,
            "phase_id": "p1",
            "metric_command": default_metric_command(root),
        },
        nodes_outputs={},
        node_id="testing",
    )
    result = runner.run("testing", {}, ctx)
    assert result.success
    assert result.output["passed"] is True
    assert "SMOKE" in (result.output.get("log_summary") or "")
    assert result.output.get("metric_command")


def test_hybrid_project_debug_repair_from_failures(monkeypatch, tmp_path: Path) -> None:
    for env_var in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(env_var, raising=False)
    base = load_config()
    config = base.model_copy(
        update={
            "workspace": str(tmp_path),
            "llm": base.llm.model_copy(update={"provider": "mock", "api_key": None}),
        }
    )
    root = "workspaces/broken"
    (tmp_path / root / "apps" / "api").mkdir(parents=True)
    (tmp_path / root / "apps" / "api" / "main.py").write_text(
        "def broken(\n", encoding="utf-8"
    )
    (tmp_path / root / "apps" / "api" / "requirements.txt").write_text(
        "fastapi>=0.110\n", encoding="utf-8"
    )

    runner = HybridAgentRunner(config)
    ctx = AgentRunContext(
        run_id="r3",
        params={
            "project_mode": True,
            "project_root": root,
            "project_title": "FixMe",
            "frontend_dir": f"{root}/apps/web",
            "phase_id": "p1",
        },
        nodes_outputs={
            "testing": {
                "passed": False,
                "failures": ["syntax main.py", "missing apps/web"],
                "log_summary": "SMOKE FAIL: syntax + missing apps/web",
            }
        },
        node_id="debug",
    )
    result = runner.run("debug", {}, ctx)
    assert result.success
    assert result.output["mode"] == "project_debug_repair"
    assert result.output["fixed"] is True
    changed = result.output["changed_files"]
    assert any(p.endswith("main.py") for p in changed)
    assert any("index.html" in p for p in changed)

    ctx_test = AgentRunContext(
        run_id="r4",
        params=dict(ctx.params),
        nodes_outputs={},
        node_id="testing",
    )
    testing = runner.run("testing", {}, ctx_test)
    assert testing.success
    assert testing.output["passed"] is True


def test_testing_fail_does_not_inline_debug(monkeypatch, tmp_path: Path) -> None:
    """冒烟失败只汇报结果，不在 Testing 节点内再跑 Debug+重测。"""
    for env_var in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(env_var, raising=False)
    base = load_config()
    config = base.model_copy(
        update={
            "workspace": str(tmp_path),
            "llm": base.llm.model_copy(update={"provider": "mock", "api_key": None}),
        }
    )
    root = "workspaces/broken-test"
    (tmp_path / root / "apps" / "api").mkdir(parents=True)
    (tmp_path / root / "apps" / "api" / "main.py").write_text("def broken(\n", encoding="utf-8")
    write_smoke_script(tmp_path, root)

    runner = HybridAgentRunner(config)
    called = {"n": 0}

    def boom(*_a, **_k):
        called["n"] += 1
        raise AssertionError("testing must not inline debug repair")

    monkeypatch.setattr(runner, "_run_project_debug_repair", boom)
    ctx = AgentRunContext(
        run_id="r-test-only",
        params={
            "project_mode": True,
            "project_root": root,
            "phase_id": "p1",
            "metric_command": default_metric_command(root),
        },
        nodes_outputs={},
        node_id="testing",
    )
    result = runner.run("testing", {}, ctx)
    assert called["n"] == 0
    assert result.output["passed"] is False
    # 节点成功执行，YAML 才能把 passed=false 交给 debug
    assert result.success is True


def test_smoke_script_defaults_to_l0(tmp_path: Path) -> None:
    root = "workspaces/l0"
    path = write_smoke_script(tmp_path, root)
    text = path.read_text(encoding="utf-8")
    assert 'os.environ.get("MAWP_SMOKE_API_INSTALL", "0")' in text
    assert 'os.environ.get("MAWP_SMOKE_WEB_INSTALL", "0")' in text
    assert 'os.environ.get("MAWP_SMOKE_WEB_BUILD", "0")' in text
    assert 'os.environ.get("MAWP_SMOKE_LIVE", "0")' in text
