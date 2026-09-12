from __future__ import annotations

import time
from typing import Any

from mawp.config.loader import AgentConfig
from mawp.security.audit import AuditLogger, AuditResult
from mawp.security.policy import PolicyDenied, PolicyEngine
from mawp.tools import echo_tools, file_tools, lint_tools, terminal_tools, test_tools
from mawp.tools.types import ToolCallContext, ToolDefinition, ToolResult

AGENT_TOOL_WHITELIST: dict[str, set[str]] = {
    "workflow": {"echo"},
    "planner": {"read_file", "list_dir", "glob_search", "grep", "echo"},
    "requirement": {"read_file", "list_dir", "glob_search", "grep", "echo"},
    "coding": {
        "read_file",
        "write_file",
        "write_files",
        "edit_file",
        "list_dir",
        "glob_search",
        "grep",
        "echo",
    },
    "frontend": {
        "read_file",
        "write_file",
        "write_files",
        "edit_file",
        "list_dir",
        "glob_search",
        "grep",
        "echo",
    },
    "testing": {
        "read_file",
        "run_tests",
        "run_linter",
        "run_typecheck",
        "run_terminal_cmd",
        "echo",
    },
    "debug": {
        "read_file",
        "write_file",
        "write_files",
        "edit_file",
        "list_dir",
        "glob_search",
        "grep",
        "run_terminal_cmd",
        "echo",
    },
    "review": {"read_file", "grep", "echo"},
    "ship": {"read_file", "list_dir", "grep", "echo"},
}


class ToolRegistry:
    def __init__(
        self,
        config: AgentConfig,
        policy: PolicyEngine | None = None,
        audit: AuditLogger | None = None,
    ):
        self.config = config
        self.policy = policy or PolicyEngine(config)
        self.audit = audit or AuditLogger.from_config(config)
        self._tools: dict[str, ToolDefinition] = {}
        self._register_builtin_tools()

    def _register_builtin_tools(self) -> None:
        self.register(
            ToolDefinition(
                name="echo",
                description="安全回显文本（无副作用）",
                parameters={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
                handler=echo_tools.echo,
                allowed_agents={
                    "workflow",
                    "planner",
                    "requirement",
                    "coding",
                    "frontend",
                    "testing",
                    "debug",
                    "review",
                    "ship",
                },
            )
        )
        self.register(
            ToolDefinition(
                name="read_file",
                description="读取工作区内文件内容",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "start_line": {"type": "integer"},
                        "end_line": {"type": "integer"},
                    },
                    "required": ["path"],
                },
                handler=file_tools.read_file,
                allowed_agents={
                    "planner",
                    "requirement",
                    "coding",
                    "frontend",
                    "testing",
                    "debug",
                    "review",
                    "ship",
                },
            )
        )
        self.register(
            ToolDefinition(
                name="write_file",
                description="写入或创建文件",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                        "dry_run": {"type": "boolean"},
                    },
                    "required": ["path", "content"],
                },
                handler=file_tools.write_file,
                allowed_agents={"coding", "debug", "frontend"},
                requires_write=True,
            )
        )
        self.register(
            ToolDefinition(
                name="write_files",
                description="批量写入多个文件（大项目优先用此工具，减少往返）",
                parameters={
                    "type": "object",
                    "properties": {
                        "files": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "path": {"type": "string"},
                                    "content": {"type": "string"},
                                },
                                "required": ["path", "content"],
                            },
                        },
                        "dry_run": {"type": "boolean"},
                    },
                    "required": ["files"],
                },
                handler=file_tools.write_files,
                allowed_agents={"coding", "debug", "frontend"},
                requires_write=True,
            )
        )
        self.register(
            ToolDefinition(
                name="edit_file",
                description="基于 search/replace 编辑文件",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "old_string": {"type": "string"},
                        "new_string": {"type": "string"},
                    },
                    "required": ["path", "old_string", "new_string"],
                },
                handler=file_tools.edit_file,
                allowed_agents={"coding", "debug", "frontend"},
                requires_write=True,
            )
        )
        self.register(
            ToolDefinition(
                name="list_dir",
                description="列出目录内容",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "recursive": {"type": "boolean"},
                    },
                },
                handler=file_tools.list_dir,
                allowed_agents={
                    "planner",
                    "requirement",
                    "coding",
                    "frontend",
                    "debug",
                    "ship",
                },
            )
        )
        self.register(
            ToolDefinition(
                name="glob_search",
                description="按 glob 模式搜索文件",
                parameters={
                    "type": "object",
                    "properties": {"pattern": {"type": "string"}},
                    "required": ["pattern"],
                },
                handler=file_tools.glob_search,
                allowed_agents={
                    "planner",
                    "requirement",
                    "coding",
                    "frontend",
                    "debug",
                },
            )
        )
        self.register(
            ToolDefinition(
                name="grep",
                description="正则搜索文件内容",
                parameters={
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string"},
                        "path": {"type": "string"},
                        "glob_pattern": {"type": "string"},
                    },
                    "required": ["pattern"],
                },
                handler=file_tools.grep,
                allowed_agents={
                    "planner",
                    "requirement",
                    "coding",
                    "frontend",
                    "debug",
                    "review",
                    "ship",
                },
            )
        )
        self.register(
            ToolDefinition(
                name="run_terminal_cmd",
                description="在工作区内执行 shell 命令",
                parameters={
                    "type": "object",
                    "properties": {
                        "command": {"type": "string"},
                        "cwd": {"type": "string"},
                    },
                    "required": ["command"],
                },
                handler=terminal_tools.run_terminal_cmd,
                allowed_agents={"testing", "debug"},
            )
        )
        self.register(
            ToolDefinition(
                name="run_tests",
                description="自动检测并运行项目测试",
                parameters={
                    "type": "object",
                    "properties": {
                        "scope": {
                            "type": "string",
                            "enum": ["all", "changed"],
                        }
                    },
                },
                handler=test_tools.run_tests,
                allowed_agents={"testing"},
            )
        )
        self.register(
            ToolDefinition(
                name="run_linter",
                description="自动检测并运行 Linter（ruff / flake8 / eslint）",
                parameters={
                    "type": "object",
                    "properties": {
                        "scope": {
                            "type": "string",
                            "enum": ["all", "changed"],
                        },
                        "changed_files": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "timeout_seconds": {"type": "integer"},
                    },
                },
                handler=lint_tools.run_linter,
                allowed_agents={"testing"},
            )
        )
        self.register(
            ToolDefinition(
                name="run_typecheck",
                description="自动检测并运行类型检查（mypy / tsc）",
                parameters={
                    "type": "object",
                    "properties": {
                        "scope": {
                            "type": "string",
                            "enum": ["all", "changed"],
                        },
                        "changed_files": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "timeout_seconds": {"type": "integer"},
                    },
                },
                handler=lint_tools.run_typecheck,
                allowed_agents={"testing"},
            )
        )

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list_tools(self, agent_name: str | None = None) -> list[ToolDefinition]:
        if agent_name is None:
            return list(self._tools.values())
        return [t for t in self._tools.values() if agent_name in t.allowed_agents]

    def schemas_for_agent(self, agent_name: str) -> list[dict[str, Any]]:
        return [t.to_openai_schema() for t in self.list_tools(agent_name)]

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        ctx: ToolCallContext,
    ) -> ToolResult:
        start = time.perf_counter()
        tool = self._tools.get(tool_name)
        if tool is None:
            self.audit.log(
                actor_id=ctx.actor_id,
                action=f"tool.{tool_name}",
                resource_type="tool",
                resource_id=tool_name,
                result=AuditResult.FAILED,
                metadata={"reason": "unknown tool"},
            )
            return ToolResult(
                success=False,
                error=f"未知工具: {tool_name}",
                duration_ms=self._elapsed(start),
            )

        try:
            self.policy.check_agent_tool(
                ctx.agent_name, tool_name, tool.allowed_agents
            )
        except PolicyDenied as exc:
            self._audit_denied(tool_name, arguments, ctx, exc)
            return ToolResult(
                success=False,
                error=str(exc),
                duration_ms=self._elapsed(start),
            )

        call_args = dict(arguments)
        if tool.requires_write:
            call_args.setdefault("agent_name", ctx.agent_name)

        rel_path = str(arguments.get("path") or "")
        if (
            tool.requires_write
            and ctx.scope_files is not None
            and rel_path
            and not call_args.get("dry_run")
        ):
            try:
                self.policy.check_write_in_scope(
                    rel_path,
                    ctx.agent_name,
                    scope_files=ctx.scope_files,
                    deny_files=ctx.deny_files,
                )
            except PolicyDenied as exc:
                self._audit_denied(tool_name, arguments, ctx, exc)
                return ToolResult(
                    success=False,
                    error=str(exc),
                    duration_ms=self._elapsed(start),
                )

        if tool_name == "run_terminal_cmd":
            call_args.setdefault(
                "timeout_seconds", self.config.tools.terminal.timeout_seconds
            )

        if tool_name in {"run_linter", "run_typecheck"}:
            call_args.setdefault(
                "timeout_seconds", self.config.agents.testing.timeout_seconds
            )

        try:
            data = tool.handler(self.policy, **call_args)
            self.audit.log(
                actor_id=ctx.actor_id,
                action=f"tool.{tool_name}",
                resource_type="tool",
                resource_id=str(arguments.get("path", tool_name)),
                result=AuditResult.SUCCESS,
                metadata={"agent": ctx.agent_name, "session_id": ctx.session_id},
            )
            return ToolResult(
                success=True, data=data, duration_ms=self._elapsed(start)
            )
        except PolicyDenied as exc:
            self._audit_denied(tool_name, arguments, ctx, exc)
            return ToolResult(
                success=False,
                error=str(exc),
                duration_ms=self._elapsed(start),
            )
        except Exception as exc:
            self.audit.log(
                actor_id=ctx.actor_id,
                action=f"tool.{tool_name}",
                resource_type="tool",
                resource_id=str(arguments.get("path", tool_name)),
                result=AuditResult.FAILED,
                metadata={"reason": str(exc), "agent": ctx.agent_name},
            )
            return ToolResult(
                success=False,
                error=str(exc),
                duration_ms=self._elapsed(start),
            )

    def _audit_denied(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        ctx: ToolCallContext,
        exc: PolicyDenied,
    ) -> None:
        self.audit.log(
            actor_id=ctx.actor_id,
            action=f"tool.{tool_name}",
            resource_type="tool",
            resource_id=str(arguments.get("path", tool_name)),
            result=AuditResult.DENIED,
            metadata={"reason": str(exc), "agent": ctx.agent_name},
        )

    @staticmethod
    def _elapsed(start: float) -> int:
        return int((time.perf_counter() - start) * 1000)
