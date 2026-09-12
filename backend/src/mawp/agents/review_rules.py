from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mawp.agents.base import AgentResult
from mawp.config.loader import AgentConfig

CONTENT_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"AKIA[0-9A-Z]{16}"), "疑似 AWS Access Key"),
    (
        re.compile(
            r'(?i)(api[_-]?key|secret|password|token)\s*[=:]\s*["\'][^"\']{8,}["\']'
        ),
        "疑似硬编码密钥或凭证",
    ),
    (re.compile(r"-----BEGIN (?:RSA )?PRIVATE KEY-----"), "疑似私钥内容"),
    (re.compile(r"sk-[a-zA-Z0-9]{20,}"), "疑似 OpenAI/Stripe 风格密钥"),
]

PLACEHOLDER_OK = re.compile(
    r"(?i)(placeholder|your[_-]?key|xxx+|changeme|example|todo|jwt-token-placeholder)"
)


@dataclass
class ReviewContext:
    session_id: str
    workspace: Path
    requirement_spec: dict[str, Any] = field(default_factory=dict)
    coding_result: dict[str, Any] = field(default_factory=dict)
    test_report: dict[str, Any] = field(default_factory=dict)


def scan_file_for_secrets(path: Path) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if not path.is_file():
        return issues
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return issues

    for line_no, line in enumerate(content.splitlines(), start=1):
        for pattern, message in CONTENT_SECRET_PATTERNS:
            if not pattern.search(line):
                continue
            if PLACEHOLDER_OK.search(line):
                continue
            issues.append(
                {
                    "level": "blocking",
                    "file": str(path),
                    "line": line_no,
                    "message": message,
                    "category": "secret",
                }
            )
    return issues


def check_change_magnitude(
    workspace: Path,
    files_changed: list[str],
    *,
    max_files: int,
    max_lines_per_file: int,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if len(files_changed) > max_files:
        issues.append(
            {
                "level": "suggestion",
                "file": "*",
                "line": 0,
                "message": (
                    f"变更文件数 {len(files_changed)} 超过建议阈值 {max_files}"
                ),
                "category": "magnitude",
            }
        )

    for rel in files_changed:
        path = workspace / rel
        if not path.is_file():
            continue
        line_count = len(path.read_text(encoding="utf-8", errors="ignore").splitlines())
        if line_count > max_lines_per_file:
            issues.append(
                {
                    "level": "nit",
                    "file": rel,
                    "line": 0,
                    "message": (
                        f"文件行数 {line_count} 较大，建议拆分（阈值 {max_lines_per_file}）"
                    ),
                    "category": "magnitude",
                }
            )
    return issues


class ReviewRulesAgent:
    agent_type = "review"

    def __init__(self, config: AgentConfig):
        self.config = config

    def run(self, ctx: ReviewContext) -> AgentResult:
        issues: list[dict[str, Any]] = []
        files_changed = list(ctx.coding_result.get("files_changed") or [])
        workspace = ctx.workspace

        for rel in files_changed:
            rel_posix = rel.replace("\\", "/")
            file_issues = scan_file_for_secrets(workspace / rel_posix)
            for item in file_issues:
                item["file"] = rel_posix
            issues.extend(file_issues)

        issues.extend(
            check_change_magnitude(
                workspace,
                files_changed,
                max_files=self.config.agents.review.max_files_changed,
                max_lines_per_file=self.config.agents.review.max_lines_per_file,
            )
        )

        if ctx.test_report and not ctx.test_report.get("skipped"):
            if not ctx.test_report.get("passed"):
                issues.append(
                    {
                        "level": "blocking",
                        "file": "*",
                        "line": 0,
                        "message": "测试未通过，不应进入提交阶段",
                        "category": "test",
                    }
                )

        blocking = [i for i in issues if i.get("level") == "blocking"]
        output = {
            "issues": issues,
            "blocking_count": len(blocking),
            "summary": self._build_summary(issues),
        }
        return AgentResult(
            success=True,
            output=output,
            agent_type=self.agent_type,
        )

    @staticmethod
    def _build_summary(issues: list[dict[str, Any]]) -> str:
        if not issues:
            return "规则审查通过，未发现 blocking 问题"
        blocking = sum(1 for i in issues if i.get("level") == "blocking")
        suggestion = sum(1 for i in issues if i.get("level") == "suggestion")
        nit = sum(1 for i in issues if i.get("level") == "nit")
        return (
            f"审查完成：blocking={blocking}, suggestion={suggestion}, nit={nit}"
        )
