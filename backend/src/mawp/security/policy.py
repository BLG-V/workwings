from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path

from mawp.config.loader import AgentConfig
from mawp.autoresearch.utils import path_in_write_scope

# B · W4：Coding / Debug / Frontend 可写；其余 Agent 只读
WRITE_AGENTS = frozenset({"coding", "debug", "frontend"})

# Frontend 仅允许写入前端约定目录（相对工作区）
FRONTEND_WRITE_PREFIXES = (
    "frontend/",
    "apps/demo-code-agent/frontend/",
    "workspaces/",  # 大项目隔离区：workspaces/<id>/apps/web/...
)


class PolicyDenied(Exception):
    """策略引擎拒绝操作。"""

    def __init__(self, message: str, *, code: str = "DENIED"):
        super().__init__(message)
        self.code = code


class PolicyEngine:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.workspace = config.workspace_path()
        self._blocked_cmd_patterns = [
            re.compile(re.escape(cmd), re.IGNORECASE)
            for cmd in config.tools.terminal.blocked_commands
        ]
        self._extra_blocked = [
            re.compile(r"rm\s+-rf\s+[/\\]", re.IGNORECASE),
            re.compile(r"git\s+push\s+.*--force", re.IGNORECASE),
            re.compile(r"\bmkfs\b", re.IGNORECASE),
            re.compile(r"\bdd\s+if=", re.IGNORECASE),
        ]

    def resolve_path(self, user_path: str) -> Path:
        raw = Path(os.path.expanduser(user_path))
        if raw.is_absolute():
            resolved = raw.resolve()
        else:
            resolved = (self.workspace / raw).resolve()

        try:
            resolved.relative_to(self.workspace)
        except ValueError as exc:
            raise PolicyDenied(
                f"路径超出工作区范围: {resolved}", code="PATH_OUTSIDE_WORKSPACE"
            ) from exc

        if self._is_denied_path(resolved):
            raise PolicyDenied(f"禁止访问敏感路径: {resolved}", code="PATH_DENIED")

        return resolved

    def check_read(self, user_path: str) -> Path:
        return self.resolve_path(user_path)

    def check_write(self, user_path: str, agent_name: str) -> Path:
        if agent_name not in WRITE_AGENTS:
            raise PolicyDenied(
                f"Agent '{agent_name}' 无写权限", code="AGENT_NO_WRITE"
            )
        resolved = self.resolve_path(user_path)
        if agent_name == "frontend":
            rel = resolved.relative_to(self.workspace).as_posix()
            if not any(
                rel == p.rstrip("/") or rel.startswith(p) for p in FRONTEND_WRITE_PREFIXES
            ):
                raise PolicyDenied(
                    f"Frontend Agent 仅可写入前端目录（允许: {', '.join(FRONTEND_WRITE_PREFIXES)}），"
                    f"拒绝: {rel}",
                    code="FRONTEND_PATH_DENIED",
                )
        return resolved

    def check_write_in_scope(
        self,
        user_path: str,
        agent_name: str,
        *,
        scope_files: list[str] | None,
        deny_files: list[str] | None = None,
    ) -> Path:
        resolved = self.check_write(user_path, agent_name)
        if scope_files is None:
            return resolved

        rel = resolved.relative_to(self.workspace).as_posix()
        if not path_in_write_scope(
            rel,
            scope_files,
            deny_files=deny_files,
            allow_tests=True,
        ):
            allowed = ", ".join(scope_files) if scope_files else "tests/**"
            raise PolicyDenied(
                f"路径 {rel} 超出 autoresearch scope（允许: {allowed}）",
                code="PATH_OUT_OF_SCOPE",
            )
        return resolved

    def check_agent_tool(self, agent_name: str, tool_name: str, allowed: set[str]) -> None:
        if agent_name not in allowed:
            raise PolicyDenied(
                f"Agent '{agent_name}' 不可调用工具 '{tool_name}'",
                code="AGENT_TOOL_DENIED",
            )

    def check_command(self, command: str) -> None:
        normalized = command.strip()
        if not normalized:
            raise PolicyDenied("空命令", code="COMMAND_EMPTY")

        for pattern in self._blocked_cmd_patterns:
            if pattern.search(normalized):
                raise PolicyDenied(
                    f"危险命令被拦截: {normalized}", code="COMMAND_BLOCKED"
                )

        for pattern in self._extra_blocked:
            if pattern.search(normalized):
                raise PolicyDenied(
                    f"危险命令被拦截: {normalized}", code="COMMAND_BLOCKED"
                )

    def _is_denied_path(self, path: Path) -> bool:
        posix = path.as_posix()
        home_ssh = Path.home() / ".ssh"

        try:
            path.relative_to(home_ssh)
            return True
        except ValueError:
            pass

        for pattern in self.config.security.path_denylist:
            expanded = os.path.expanduser(pattern)
            if expanded.startswith("/") or (len(expanded) > 1 and expanded[1] == ":"):
                if posix.startswith(Path(expanded).as_posix()):
                    return True
            elif fnmatch.fnmatch(posix, expanded) or fnmatch.fnmatch(path.name, expanded):
                return True

        for pattern in self.config.security.secret_patterns:
            if self._path_matches_pattern(path, pattern):
                return True

        return False

    @staticmethod
    def _path_matches_pattern(path: Path, pattern: str) -> bool:
        if pattern.startswith("~/"):
            return fnmatch.fnmatch(str(path), os.path.expanduser(pattern))

        normalized = pattern.replace("\\", "/")
        if normalized.startswith("**/"):
            suffix = normalized[3:]
            if fnmatch.fnmatch(path.name, suffix):
                return True
            if suffix.endswith("/**"):
                dir_name = suffix[:-3]
                return dir_name in path.parts
            return fnmatch.fnmatch(path.as_posix(), f"*/{suffix}")

        if fnmatch.fnmatch(path.name, normalized):
            return True
        return fnmatch.fnmatch(path.as_posix(), normalized)
