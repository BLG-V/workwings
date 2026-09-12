from __future__ import annotations

from pathlib import Path

from mawp.agents.base import AgentContext
from mawp.agents.requirement import RequirementAgent, build_requirement_user_message
from mawp.config.loader import AgentConfig
from mawp.llm.mock import MockLLMAdapter
from mawp.rag.service import RAGService
from mawp.tools.registry import ToolRegistry


def test_rag_build_and_retrieve(tmp_path: Path) -> None:
    (tmp_path / "src" / "auth").mkdir(parents=True)
    (tmp_path / "src" / "auth" / "login.py").write_text(
        "def email_login(email: str, code: str) -> str:\n"
        "    return 'jwt-token'\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "main.py").write_text("from auth.login import email_login\n", encoding="utf-8")

    config = AgentConfig(workspace=str(tmp_path))
    rag = RAGService(config)
    stats = rag.build_index(force=True)

    assert stats.rebuilt
    assert stats.chunks_indexed >= 1
    assert rag.is_indexed()

    result = rag.retrieve("邮箱验证码登录 JWT")
    assert result.index_hit
    assert len(result.chunks) >= 1
    paths = {chunk.path for chunk in result.chunks}
    assert any("login.py" in p for p in paths)


def test_rag_retrieve_without_index(tmp_path: Path) -> None:
    config = AgentConfig(workspace=str(tmp_path))
    rag = RAGService(config)
    result = rag.retrieve("anything")
    assert not result.index_hit
    assert result.chunks == []


def test_rag_index_idempotent(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("print('hi')\n", encoding="utf-8")
    config = AgentConfig(workspace=str(tmp_path))
    rag = RAGService(config)

    first = rag.build_index(force=True)
    second = rag.build_index(force=False)

    assert first.rebuilt
    assert not second.rebuilt
    assert second.chunks_indexed == first.chunks_indexed


def test_requirement_user_message_includes_rag_context() -> None:
    ctx = AgentContext(
        session_id="s1",
        user_description="实现邮箱登录",
        workspace=Path("."),
        rag_chunks=[
            {
                "path": "src/auth/login.py",
                "content": "def login(): ...",
                "start_line": 1,
                "end_line": 10,
                "score": 0.9,
            }
        ],
    )
    message = build_requirement_user_message(ctx)
    assert "src/auth/login.py" in message
    assert "实现邮箱登录" in message


def test_requirement_agent_injects_rag_chunks(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "users.py").write_text(
        "class User:\n    email: str\n",
        encoding="utf-8",
    )
    config = AgentConfig(workspace=str(tmp_path))
    rag = RAGService(config)
    rag.build_index(force=True)
    chunks = [chunk.to_dict() for chunk in rag.retrieve_chunks("用户邮箱")]

    tools = ToolRegistry(config)
    llm = MockLLMAdapter(
        [
            MockLLMAdapter.json_response(
                {
                    "summary": "用户模块",
                    "goals": [],
                    "non_goals": [],
                    "acceptance_criteria": [],
                    "inputs_outputs": {},
                    "affected_modules": [],
                    "dependencies": [],
                    "risks": [],
                    "related_files": ["src/users.py"],
                    "open_questions": [],
                    "tasks": [],
                }
            )
        ]
    )
    agent = RequirementAgent(config, tools, llm=llm)
    ctx = AgentContext(
        session_id="s1",
        user_description="为用户模块增加邮箱验证码登录",
        workspace=tmp_path,
        rag_chunks=chunks,
    )
    result = agent.run(ctx)
    assert result.success
    assert llm.calls
    user_message = llm.calls[0]["messages"][0]["content"]
    assert "users.py" in user_message or "email" in user_message.lower()
