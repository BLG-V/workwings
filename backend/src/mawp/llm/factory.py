from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mawp.config.loader import AgentConfig
from mawp.llm.anthropic_adapter import AnthropicAdapter
from mawp.llm.base import LLMAdapter
from mawp.llm.exceptions import LLMConfigError
from mawp.llm.openai_adapter import OpenAIAdapter


def _load_dotenv_if_present() -> None:
    """轻量加载仓库根/.env（不覆盖已有环境变量；无 python-dotenv 依赖）。"""
    path = Path.cwd() / ".env"
    if not path.is_file():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().lstrip("\ufeff")
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def resolve_api_key(config: AgentConfig) -> str | None:
    _load_dotenv_if_present()
    env_name = config.llm.api_key_env
    for candidate in (env_name, "DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        value = os.environ.get(candidate)
        if value:
            return value
    return None


def create_llm_adapter(config: AgentConfig, *, required: bool = False) -> LLMAdapter | None:
    """根据配置创建 LLM 适配器；无 API Key 时返回 None（或 required=True 时抛错）。"""
    if config.llm.provider == "mock":
        from mawp.llm.mock import MockLLMAdapter

        return MockLLMAdapter()

    api_key = resolve_api_key(config)
    if not api_key:
        if required:
            raise LLMConfigError(
                f"未找到 LLM API Key，请设置环境变量 {config.llm.api_key_env}"
            )
        return None

    provider = config.llm.provider.lower()
    kwargs: dict[str, Any] = {
        "api_key": api_key,
        "model": config.llm.model,
        "base_url": config.llm.base_url,
    }

    if provider == "openai":
        return OpenAIAdapter(**kwargs)
    if provider == "anthropic":
        return AnthropicAdapter(**kwargs)

    raise LLMConfigError(f"不支持的 LLM provider: {config.llm.provider}")
