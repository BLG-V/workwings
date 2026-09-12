from __future__ import annotations

from pathlib import Path

import pytest

from mawp.config.loader import AgentConfig
from mawp.llm.base import LLMAdapter
from mawp.llm.mock import MockLLMAdapter


@pytest.fixture
def e2e_config(tmp_path, monkeypatch) -> AgentConfig:
    """E2E 测试用配置：无 LLM API Key，启用启发式编码 Agent。"""
    for key in (
        "DEEPSEEK_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "NONEXISTENT_E2E_KEY",
    ):
        monkeypatch.delenv(key, raising=False)

    return AgentConfig(
        workspace=str(tmp_path),
        llm={"provider": "openai", "api_key_env": "NONEXISTENT_E2E_KEY"},
        gstack={"auto_fix_blocking": False},
        autoresearch={"max_iterations": 3, "auto_commit_on_keep": False},
    )


def setup_verify_workspace(workspace: Path) -> str:
    """创建 demo 文件与二元验证脚本，供 autoresearch 启发式实现通过。"""
    (workspace / "src").mkdir(exist_ok=True)
    (workspace / "src" / "demo.py").write_text("# demo\n", encoding="utf-8")
    verify = workspace / "verify.py"
    verify.write_text(
        "from pathlib import Path\n"
        "text = Path('src/demo.py').read_text(encoding='utf-8')\n"
        "raise SystemExit(0 if 'agent-generated' in text else 1)\n",
        encoding="utf-8",
    )
    return "python verify.py"


def setup_secrets_workspace(workspace: Path) -> None:
    """创建 secrets 目录与 .env，用于 E2E-05 越权访问测试。"""
    (workspace / "secrets").mkdir(exist_ok=True)
    (workspace / "secrets" / "key.txt").write_text("SUPER_SECRET\n", encoding="utf-8")
    (workspace / ".env").write_text("API_KEY=must-not-leak\n", encoding="utf-8")


def patch_mock_llm(monkeypatch: pytest.MonkeyPatch, llm: LLMAdapter) -> None:
    """将 autoresearch 循环使用的 LLM 替换为预设 Mock 适配器。"""

    def _factory(_config: AgentConfig) -> LLMAdapter:
        return llm

    monkeypatch.setattr("mawp.autoresearch.loop.create_llm_adapter", _factory)


def demo_marker_content() -> str:
    return "# demo\n\n# --- agent-generated ---\n"


def build_fail_then_pass_llm() -> MockLLMAdapter:
    """第一轮无文件变更（verify 失败），第二轮写入 marker 后通过。"""
    return MockLLMAdapter(
        [
            MockLLMAdapter.json_response(
                {
                    "change_plan": [],
                    "files_changed": [],
                    "changelog": "第一次尝试未修改文件",
                }
            ),
            MockLLMAdapter.tool_call_response(
                "c1",
                "write_file",
                {"path": "src/demo.py", "content": demo_marker_content()},
            ),
            MockLLMAdapter.json_response(
                {
                    "change_plan": [
                        {
                            "path": "src/demo.py",
                            "action": "modify",
                            "summary": "添加 agent-generated 标记",
                        }
                    ],
                    "files_changed": ["src/demo.py"],
                    "changelog": "第二次尝试写入 marker",
                }
            ),
        ]
    )


def build_secrets_probe_then_fix_llm() -> MockLLMAdapter:
    """先尝试访问 secrets，再在 scope 内修复 demo.py。"""
    return MockLLMAdapter(
        [
            MockLLMAdapter.tool_call_response(
                "c1",
                "read_file",
                {"path": "secrets/key.txt"},
            ),
            MockLLMAdapter.tool_call_response(
                "c2",
                "write_file",
                {"path": "secrets/evil.py", "content": "stolen = True\n"},
            ),
            MockLLMAdapter.tool_call_response(
                "c3",
                "write_file",
                {"path": "src/demo.py", "content": demo_marker_content()},
            ),
            MockLLMAdapter.json_response(
                {
                    "change_plan": [
                        {
                            "path": "src/demo.py",
                            "action": "modify",
                            "summary": "在 scope 内完成修复",
                        }
                    ],
                    "files_changed": ["src/demo.py"],
                    "changelog": "secrets 访问被拦截后改走 scope 内修复",
                }
            ),
        ]
    )
