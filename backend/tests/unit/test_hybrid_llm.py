"""Hybrid DeepSeek / JSON util 最小路径。"""

from __future__ import annotations

import json
from pathlib import Path

from mawp.config.loader import AgentConfig, load_config
from mawp.llm.mock import MockLLMAdapter
from mawp.llm.types import LLMResponse, TokenUsage
from mawp.runtime.agents import AgentRunContext
from mawp.runtime.agent_runtime import AgentRuntime, RuntimeContext
from mawp.runtime.deliver_specs import build_deliver_specs
from mawp.runtime.hybrid import HybridAgentRunner
from mawp.runtime.json_util import extract_json_object
from mawp.runtime.spec import AgentSpec


def test_extract_json_object_from_fence() -> None:
    text = '说明如下：\n```json\n{"status":"ok","count":1}\n```\n'
    assert extract_json_object(text) == {"status": "ok", "count": 1}


def test_hybrid_offline_without_key(monkeypatch, tmp_path: Path) -> None:
    for env_var in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(env_var, raising=False)
    base = load_config()
    config = base.model_copy(
        update={
            "workspace": str(tmp_path),
            "llm": base.llm.model_copy(update={"provider": "mock", "api_key": None}),
        }
    )
    (tmp_path / "src").mkdir()
    runner = HybridAgentRunner(config)
    assert runner.llm_enabled is False
    ctx = AgentRunContext(
        run_id="r",
        params={"goal": "g"},
        nodes_outputs={"planner": {"tasks": [{"id": "T1", "title": "t", "depends_on": []}]}},
        node_id="coding",
    )
    result = runner.run("coding", {}, ctx)
    assert result.success
    assert result.output["status"] == "ok"


def test_hybrid_llm_mode_eight_agents(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    config = AgentConfig(
        workspace=str(tmp_path),
        llm={"provider": "openai", "model": "deepseek-v4-pro", "api_key_env": "DEEPSEEK_API_KEY"},
    )
    llm = MockLLMAdapter()
    runner = HybridAgentRunner(config, llm=llm, force_llm=True)
    assert runner.llm_enabled is True

    ctx = AgentRunContext(run_id="r", params={"goal": "demo", "pass_on_attempt": 1}, nodes_outputs={}, node_id="planner")
    planner = runner.run("planner", {"tasks": [{"id": "T1", "title": "x", "depends_on": []}]}, ctx)
    assert planner.success
    assert "tasks" in planner.output

    ctx.nodes_outputs["planner"] = planner.output
    ctx.node_id = "requirement"
    req = runner.run("requirement", {"summary": "demo"}, ctx)
    assert req.success
    assert req.output.get("status") == "ok"

    ctx.nodes_outputs["requirement"] = req.output
    ctx.node_id = "coding"
    coding = runner.run("coding", {}, ctx)
    assert coding.success
    assert "changed_files" in coding.output

    ctx.node_id = "testing"
    testing = runner.run("testing", {}, ctx)
    assert testing.success
    assert testing.output["passed"] is True
    assert testing.output["attempt"] == 1

    ctx.params["review_status"] = "blocking"
    ctx.node_id = "review"
    review = runner.run("review", {}, ctx)
    assert review.output["status"] == "blocking"
    assert review.output["blocking_count"] >= 1

    ctx.node_id = "ship"
    ship = runner.run("ship", {"delivery_notes": "n"}, ctx)
    assert ship.output["auto_push"] is False
    assert ship.output["auto_merge"] is False


def test_agent_runtime_parses_json_output() -> None:
    llm = MockLLMAdapter(
        [
            LLMResponse(
                content=json.dumps({"status": "ok", "n": 1}),
                usage=TokenUsage(1, 1, 2),
            )
        ]
    )
    config = AgentConfig()
    runtime = AgentRuntime(config, llm=llm)
    runtime.register(
        AgentSpec(name="planner", system_prompt="你是任务规划 Agent。", tools=[], max_steps=2)
    )
    result = runtime.run("planner", {"text": "{}"}, RuntimeContext(session_id="s"))
    assert result.success
    assert result.output == {"status": "ok", "n": 1}


def test_build_deliver_specs_covers_eight() -> None:
    specs = build_deliver_specs()
    assert {s.name for s in specs} == {
        "planner",
        "requirement",
        "coding",
        "frontend",
        "testing",
        "debug",
        "review",
        "ship",
    }


def test_default_agent_models_use_flash_for_light_agents() -> None:
    from mawp.config.loader import DEFAULT_AGENT_MODELS

    for name in ("planner", "requirement", "testing", "review", "ship"):
        assert "flash" in DEFAULT_AGENT_MODELS[name]
    for name in ("coding", "frontend", "debug"):
        assert "pro" in DEFAULT_AGENT_MODELS[name]


def test_build_deliver_specs_respects_model_overrides() -> None:
    specs = {s.name: s for s in build_deliver_specs(models={"planner": "deepseek-v4-flash", "coding": "deepseek-v4-pro"})}
    assert specs["planner"].model == "deepseek-v4-flash"
    assert specs["coding"].model == "deepseek-v4-pro"
