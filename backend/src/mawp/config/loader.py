from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMConfig(BaseModel):
    # DeepSeek OpenAI 兼容端点（方案 C）；无 Key 时 Hybrid 自动回退 Mock/stub
    provider: str = "openai"
    base_url: str | None = "https://api.deepseek.com"
    model: str = "deepseek-v4-pro"
    api_key_env: str = "DEEPSEEK_API_KEY"
    max_tokens_per_run: int = 100_000


class AgentCodingConfig(BaseModel):
    max_retries: int = 3
    max_tool_iterations: int = 15


class AgentTestingConfig(BaseModel):
    timeout_seconds: int = 120
    run_linter: bool = True
    run_typecheck: bool = True
    block_on_lint_errors: bool = True
    block_on_type_errors: bool = True


class AgentReviewConfig(BaseModel):
    mode: str = "hybrid"  # rules | hybrid | llm
    max_files_changed: int = 20
    max_lines_per_file: int = 500
    max_fix_retries: int = 3
    max_iterations: int = 3
    max_file_chars: int = 4000


class AgentRequirementConfig(BaseModel):
    max_tool_iterations: int = 10


# 八 Agent 推荐分档（核心生成用 Pro，编排/需求/收尾用 Flash）
DEFAULT_AGENT_MODELS: dict[str, str] = {
    "planner": "deepseek-v4-flash",
    "requirement": "deepseek-v4-flash",
    "coding": "deepseek-v4-pro",
    "frontend": "deepseek-v4-pro",
    "testing": "deepseek-v4-flash",
    "debug": "deepseek-v4-pro",
    "review": "deepseek-v4-flash",
    "ship": "deepseek-v4-flash",
}


class AgentsConfig(BaseModel):
    requirement: AgentRequirementConfig = Field(default_factory=AgentRequirementConfig)
    coding: AgentCodingConfig = Field(default_factory=AgentCodingConfig)
    testing: AgentTestingConfig = Field(default_factory=AgentTestingConfig)
    review: AgentReviewConfig = Field(default_factory=AgentReviewConfig)
    # 按 Agent 覆盖全局 llm.model；未列出的 Agent 回退全局模型
    models: dict[str, str] = Field(default_factory=lambda: dict(DEFAULT_AGENT_MODELS))


class TerminalToolsConfig(BaseModel):
    timeout_seconds: int = 120
    blocked_commands: list[str] = Field(
        default_factory=lambda: ["rm -rf", "git push --force"]
    )


class ToolsConfig(BaseModel):
    terminal: TerminalToolsConfig = Field(default_factory=TerminalToolsConfig)


class RAGEmbeddingConfig(BaseModel):
    provider: str = "local"  # local | openai
    model: str = "text-embedding-3-small"
    api_key_env: str = "OPENAI_API_KEY"
    base_url: str | None = None


class RAGConfig(BaseModel):
    index_path: str = ".mawp/index"
    exclude: list[str] = Field(
        default_factory=lambda: ["node_modules", "dist", ".git", ".mawp"]
    )
    chunk_size_chars: int = 3200
    chunk_overlap_chars: int = 400
    top_k: int = 10
    max_context_chars: int = 12000
    use_ast_chunking: bool = True
    hybrid_search: bool = True
    bm25_weight: float = 0.35
    embedding: RAGEmbeddingConfig = Field(default_factory=RAGEmbeddingConfig)


class SecurityConfig(BaseModel):
    secret_patterns: list[str] = Field(
        default_factory=lambda: ["*.env", "**/secrets/**"]
    )
    path_denylist: list[str] = Field(default_factory=lambda: ["/etc"])


class AuditConfig(BaseModel):
    retention_days: int = 90


class GoalWorkflowConfig(BaseModel):
    base_path: str = ".goal"
    quick_track_max_files: int = 3


class GstackConfig(BaseModel):
    enabled: bool = True
    auto_fix_blocking: bool = True


class AutoresearchConfig(BaseModel):
    max_iterations: int = 25
    token_budget: int = 500_000
    results_path: str = ".autoresearch/results.jsonl"
    auto_commit_on_keep: bool = True


class HealModelsConfig(BaseModel):
    """自愈回合按错误类型 / 轮次 / Agent 选型（不全程升 Pro）。"""

    # keep = 沿用 agents.models[agent]；也可写死模型名作全局默认
    default: str = "keep"
    by_category: dict[str, str] = Field(
        default_factory=lambda: {
            "syntax_error": "deepseek-v4-flash",
            "import_error": "deepseek-v4-flash",
            "missing_file": "deepseek-v4-flash",
            "route_error": "deepseek-v4-pro",
            "build_error": "deepseek-v4-pro",
            "runtime_error": "deepseek-v4-pro",
            "review_blocking": "deepseek-v4-pro",
            "max_steps": "deepseek-v4-pro",
            "unknown": "keep",
        }
    )
    # 自愈轮次（1-based）达到该值后升档；第 1 轮不升
    escalate_after_round: int = 2
    escalate_to: str = "deepseek-v4-pro"
    # 断线 / 限流时按 attempt 轮换
    failover: list[str] = Field(
        default_factory=lambda: ["deepseek-v4-flash", "deepseek-v4-pro"]
    )


class AgentConfig(BaseModel):
    workspace: str = "."
    llm: LLMConfig = Field(default_factory=LLMConfig)
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    audit: AuditConfig = Field(default_factory=AuditConfig)
    goal_workflow: GoalWorkflowConfig = Field(default_factory=GoalWorkflowConfig)
    gstack: GstackConfig = Field(default_factory=GstackConfig)
    autoresearch: AutoresearchConfig = Field(default_factory=AutoresearchConfig)
    heal_models: HealModelsConfig = Field(default_factory=HealModelsConfig)

    def workspace_path(self) -> Path:
        return Path(self.workspace).resolve()

    def rag_index_path(self) -> Path:
        return self.workspace_path() / self.rag.index_path


class EnvOverrides(BaseSettings):
    """环境变量覆盖 LLM 配置（优先级高于 YAML）。"""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    llm_provider: str | None = Field(default=None, alias="LLM_PROVIDER")
    llm_base_url: str | None = Field(default=None, alias="LLM_BASE_URL")
    llm_model: str | None = Field(default=None, alias="LLM_MODEL")


def _find_config_file(explicit: Path | None) -> Path | None:
    if explicit is not None:
        path = explicit.expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"配置文件不存在: {path}")
        return path

    for candidate in (Path("mawp.config.yaml"), Path("mawp.config.yml")):
        if candidate.is_file():
            return candidate.resolve()
    return None


def _apply_env_overrides(config: AgentConfig) -> AgentConfig:
    env = EnvOverrides()
    updates: dict[str, Any] = {}
    if env.llm_provider is not None:
        updates["provider"] = env.llm_provider
    if env.llm_base_url is not None:
        updates["base_url"] = env.llm_base_url
    if env.llm_model is not None:
        updates["model"] = env.llm_model
    if updates:
        config.llm = config.llm.model_copy(update=updates)
    return config


def load_config(config_path: Path | str | None = None) -> AgentConfig:
    explicit = Path(config_path) if config_path is not None else None
    file_path = _find_config_file(explicit)

    if file_path is None:
        config = AgentConfig()
    else:
        with file_path.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        config = AgentConfig.model_validate(raw)

    return _apply_env_overrides(config)
