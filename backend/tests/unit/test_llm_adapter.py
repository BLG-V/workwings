from __future__ import annotations

import pytest

from mawp.config.loader import AgentConfig
from mawp.llm.exceptions import LLMConfigError
from mawp.llm.factory import create_llm_adapter
from mawp.llm.mock import MockLLMAdapter


def test_create_mock_adapter() -> None:
    config = AgentConfig()
    config.llm.provider = "mock"
    adapter = create_llm_adapter(config, required=True)
    assert isinstance(adapter, MockLLMAdapter)


def test_create_adapter_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # 清除所有 fallback 环境变量，避免本机已配置的 DEEPSEEK/OPENAI key 干扰
    for env_var in (
        "MISSING_KEY_FOR_TEST_XYZ",
        "DEEPSEEK_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
    ):
        monkeypatch.delenv(env_var, raising=False)

    config = AgentConfig()
    config.llm.provider = "openai"
    config.llm.api_key_env = "MISSING_KEY_FOR_TEST_XYZ"
    adapter = create_llm_adapter(config, required=False)
    assert adapter is None

    with pytest.raises(LLMConfigError):
        create_llm_adapter(config, required=True)


def test_mock_adapter_default_json() -> None:
    llm = MockLLMAdapter()
    response = llm.chat([{"role": "user", "content": "实现登录功能"}])
    assert response.content
    assert "实现登录功能" in response.content
    assert response.usage.total_tokens > 0
