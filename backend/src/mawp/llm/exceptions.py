from __future__ import annotations


class LLMError(Exception):
    """LLM 调用基础异常。"""


class LLMConfigError(LLMError):
    """配置或 API Key 缺失。"""


class LLMRequestError(LLMError):
    """HTTP 请求失败或 API 返回错误。"""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code
