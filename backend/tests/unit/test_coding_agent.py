from __future__ import annotations

import json
from pathlib import Path

from mawp.agents.coding import CodingAgent, CodingAgentContext, files_changed_from_tools
from mawp.agents.base import ToolCallRecord
from mawp.config.loader import AgentConfig
from mawp.llm.mock import MockLLMAdapter
from mawp.tools.registry import ToolRegistry


def test_coding_agent_mock_write_and_finish(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def hello():\n    pass\n", encoding="utf-8")

    config = AgentConfig(workspace=str(tmp_path))
    tools = ToolRegistry(config)
    llm = MockLLMAdapter(
        [
            MockLLMAdapter.tool_call_response(
                "c1",
                "write_file",
                {
                    "path": "src/app.py",
                    "content": "def hello():\n    return 'hi'\n",
                },
            ),
            MockLLMAdapter.json_response(
                {
                    "change_plan": [
                        {
                            "path": "src/app.py",
                            "action": "modify",
                            "summary": "return greeting",
                        }
                    ],
                    "files_changed": ["src/app.py"],
                    "changelog": "更新 hello 返回值",
                }
            ),
        ]
    )
    agent = CodingAgent(config, tools, llm=llm)
    ctx = CodingAgentContext(
        session_id="s1",
        user_description="让 hello 返回 hi",
        workspace=tmp_path,
        requirement_spec={"summary": "更新 hello", "related_files": ["src/app.py"]},
    )

    result = agent.run(ctx)
    assert result.success
    assert "src/app.py" in result.output["files_changed"]
    assert (tmp_path / "src" / "app.py").read_text(encoding="utf-8").strip().endswith(
        "return 'hi'"
    )


def test_coding_agent_heuristic_creates_file(tmp_path: Path) -> None:
    config = AgentConfig(workspace=str(tmp_path))
    tools = ToolRegistry(config)
    agent = CodingAgent(config, tools, llm=None)
    ctx = CodingAgentContext(
        session_id="s2",
        user_description="添加占位实现",
        workspace=tmp_path,
        requirement_spec={"summary": "添加占位实现", "related_files": []},
    )

    result = agent.run(ctx)
    assert result.success
    assert result.output["files_changed"]
    assert (tmp_path / "src" / "agent_generated.py").exists()


def test_files_changed_from_tools() -> None:
    records = [
        ToolCallRecord(
            name="write_file",
            arguments={"path": "a.py"},
            success=True,
            result={"path": "a.py"},
        ),
        ToolCallRecord(
            name="grep",
            arguments={"pattern": "x"},
            success=True,
            result={},
        ),
    ]
    assert files_changed_from_tools(records) == ["a.py"]
