from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

from mawp.llm.exceptions import LLMError
from mawp.llm.types import LLMResponse


class LLMAdapter(ABC):
    """统一 chat + tool calling 接口（架构 §9.1）。"""

    max_retries: int = 3
    retry_base_delay: float = 1.0

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        system: str | None = None,
        response_format: dict[str, Any] | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        """发送对话请求。model 可覆盖适配器默认模型（按 Agent 分档）。"""

    def chat_with_retry(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> LLMResponse:
        last_error: LLMError | None = None
        for attempt in range(self.max_retries):
            try:
                return self.chat(messages, **kwargs)
            except LLMError as exc:
                last_error = exc
                if attempt >= self.max_retries - 1:
                    break
                time.sleep(self.retry_base_delay * (2**attempt))
        assert last_error is not None
        raise last_error
