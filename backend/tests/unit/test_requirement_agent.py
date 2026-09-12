from __future__ import annotations

import json

import pytest

from mawp.agents.requirement import (
    RequirementAgent,
    extract_json_object,
    parse_requirement_spec,
)
from mawp.agents.base import AgentContext
from mawp.config.loader import AgentConfig
from mawp.llm.mock import MockLLMAdapter
from mawp.tools.registry import ToolRegistry


def test_extract_json_object_from_fence() -> None:
    text = """```json
{"summary": "测试", "tasks": []}
```"""
    data = extract_json_object(text)
    assert data["summary"] == "测试"


def test_parse_requirement_spec_minimal() -> None:
    payload = {
        "summary": "邮箱登录",
        "acceptance_criteria": ["验证码有效"],
        "related_files": ["src/auth.py"],
        "open_questions": [],
        "tasks": [{"id": "T1", "title": "实现登录", "depends_on": []}],
    }
    spec = parse_requirement_spec(json.dumps(payload))
    assert spec.summary == "邮箱登录"
    assert spec.tasks[0].id == "T1"


def test_requirement_agent_mock_direct_json(tmp_path) -> None:
    config = AgentConfig(workspace=str(tmp_path))
    tools = ToolRegistry(config)
    llm = MockLLMAdapter(
        [
            MockLLMAdapter.json_response(
                {
                    "summary": "用户登录 API",
                    "goals": ["提供登录接口"],
                    "non_goals": [],
                    "acceptance_criteria": ["返回 JWT"],
                    "inputs_outputs": {},
                    "affected_modules": ["auth"],
                    "dependencies": [],
                    "risks": [],
                    "related_files": ["src/main.py"],
                    "open_questions": [],
                    "tasks": [{"id": "T1", "title": "实现登录", "depends_on": []}],
                }
            )
        ]
    )
    agent = RequirementAgent(config, tools, llm=llm)
    ctx = AgentContext(
        session_id="s1",
        user_description="实现用户登录 API",
        workspace=tmp_path,
    )

    result = agent.run(ctx)
    assert result.success
    assert result.output["summary"] == "用户登录 API"
    assert result.output["related_files"] == ["src/main.py"]
    assert result.tokens_used > 0


def test_requirement_agent_tool_loop(tmp_path) -> None:
    config = AgentConfig(workspace=str(tmp_path))
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hi')\n", encoding="utf-8")

    tools = ToolRegistry(config)
    llm = MockLLMAdapter(
        [
            MockLLMAdapter.tool_call_response("call_1", "read_file", {"path": "src/app.py"}),
            MockLLMAdapter.json_response(
                {
                    "summary": "改进 app",
                    "goals": [],
                    "non_goals": [],
                    "acceptance_criteria": ["运行成功"],
                    "inputs_outputs": {},
                    "affected_modules": [],
                    "dependencies": [],
                    "risks": [],
                    "related_files": ["src/app.py"],
                    "open_questions": [],
                    "tasks": [{"id": "T1", "title": "改 app", "depends_on": []}],
                }
            ),
        ]
    )
    agent = RequirementAgent(config, tools, llm=llm)
    ctx = AgentContext(
        session_id="s2",
        user_description="改进 app 输出",
        workspace=tmp_path,
    )

    result = agent.run(ctx)
    assert result.success
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "read_file"
    assert result.tool_calls[0].success


def test_requirement_agent_heuristic_without_llm(tmp_path) -> None:
    config = AgentConfig(workspace=str(tmp_path))
    (tmp_path / "main.py").write_text("x = 1\n", encoding="utf-8")
    tools = ToolRegistry(config)
    agent = RequirementAgent(config, tools, llm=None)
    ctx = AgentContext(
        session_id="s3",
        user_description="添加功能",
        workspace=tmp_path,
    )

    result = agent.run(ctx)
    assert result.success
    assert result.output["summary"] == "添加功能"
    assert result.output["open_questions"]
    assert len(result.tool_calls) >= 1
