from __future__ import annotations

from mawp.autoresearch.models import ProgramConfig


def render_program(program: ProgramConfig) -> str:
    scope = "\n".join(f"- {path}" for path in program.scope_files) or "- （实现时确定）"
    deny = "\n".join(f"- {path}" for path in program.deny_files) or "- （无）"
    return f"""# Autoresearch Program

## Goal
{program.goal}

## Metric（二元验证）
```bash
{program.metric_command}
```
通过条件: exit code == 0

## Scope（允许修改的文件）
{scope}

## Constraints
- max_iterations: {program.max_iterations}
- token_budget: {program.token_budget}
- 禁止修改:
{deny}

## Issue
- ID: {program.issue_id}
"""
