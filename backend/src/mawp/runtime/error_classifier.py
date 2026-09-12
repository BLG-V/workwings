# -*- coding: utf-8 -*-
"""错误分类器：根据测试失败日志自动分类错误类型，并给出修复策略建议。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class ErrorClassification:
    """一个测试失败的分类结果。"""

    category: str  # syntax_error / import_error / route_error / build_error / runtime_error / unknown
    severity: str  # critical / high / medium / low
    file_hint: str | None  # 可能为 None
    line_hint: int | None  # 可能为 None
    module_hint: str | None  # 可能为 None
    raw_message: str
    suggested_fix: str
    fix_strategy: str  # rewrite_file / fix_import / fix_route / fix_build / generic


def classify_error(failure_text: str, log_summary: str = "") -> ErrorClassification:
    """把失败信息分类为具体的错误类型 + 修复策略。"""
    combined = f"{failure_text}\n{log_summary}".strip()
    lower = combined.lower()

    # 语法错误
    syntax_patterns = [
        r"SyntaxError:\s*(.+)",
        r"IndentationError:\s*(.+)",
        r"py_compile.*error",
        r"syntax\s+error",
        r"unexpected\s+(?:indent|token|EOF)",
        r"unterminated\s+(?:string|triple)",
    ]
    for pat in syntax_patterns:
        m = re.search(pat, combined, re.IGNORECASE)
        if m:
            file_hint = _extract_file_path(combined)
            line_hint = _extract_line_number(combined)
            return ErrorClassification(
                category="syntax_error",
                severity="critical",
                file_hint=file_hint,
                line_hint=line_hint,
                module_hint=None,
                raw_message=m.group(0)[:500],
                suggested_fix=f"修复语法错误：{m.group(1) if m.lastindex else m.group(0)}。检查文件 {file_hint or '未知'} 第 {line_hint or '?'} 行。",
                fix_strategy="rewrite_file",
            )

    # import 错误
    import_patterns = [
        r"ModuleNotFoundError:\s*No module named '([^']+)'",
        r"ImportError:\s*(.+)",
        r"cannot import name\s+(\S+)\s+from",
        r"No module named\s+([^\s']+)",
    ]
    for pat in import_patterns:
        m = re.search(pat, combined, re.IGNORECASE)
        if m:
            module = m.group(1) if m.lastindex else None
            return ErrorClassification(
                category="import_error",
                severity="critical",
                file_hint=_extract_file_path(combined),
                line_hint=_extract_line_number(combined),
                module_hint=module,
                raw_message=m.group(0)[:500],
                suggested_fix=f"修复导入：模块 '{module}' 未找到。检查路径或安装依赖。",
                fix_strategy="fix_import",
            )

    # 路由错误
    route_patterns = [
        r"live probe.*missing",
        r"404.*not found",
        r"status_code.*404",
        r"route.*not.*registered",
        r"MissingAPIRoute",
        r"api/repairs.*missing",
        r"unmounted router",
        r"missing include_router",
        r"unlinked page",
        r"placeholder endpoint",
        r"ACCEPTANCE fail",
        r"tenant isolation",
        r"missing tenant fields",
        r"memory-only store",
    ]
    for pat in route_patterns:
        m = re.search(pat, combined, re.IGNORECASE)
        if m:
            return ErrorClassification(
                category="route_error",
                severity="high",
                file_hint=_extract_file_path(combined),
                line_hint=None,
                module_hint=None,
                raw_message=m.group(0)[:500],
                suggested_fix="路由未注册、入口未接入，或接口只是空壳。检查 include_router，并实现业务字段（不要只返回「新增条目」/items 占位）。",
                fix_strategy="fix_route",
            )

    # 构建错误
    build_patterns = [
        r"web build failed",
        r"web install failed",
        r"npm.*ERR",
        r"pnpm.*ERR",
        r"yarn.*ERR",
        r"ERROR in.*\.tsx?",
        r"ERROR in.*\.jsx?",
        r"Failed to compile",
        r"TypeError:.*is not a function",
    ]
    for pat in build_patterns:
        m = re.search(pat, combined, re.IGNORECASE)
        if m:
            return ErrorClassification(
                category="build_error",
                severity="high",
                file_hint=_extract_file_path(combined),
                line_hint=_extract_line_number(combined),
                module_hint=None,
                raw_message=m.group(0)[:500],
                suggested_fix="前端构建失败。检查 package.json 依赖和入口文件。",
                fix_strategy="fix_build",
            )

    # 运行时错误
    runtime_patterns = [
        r"RuntimeError:\s*(.+)",
        r"TypeError:\s*(.+)",
        r"ValueError:\s*(.+)",
        r"KeyError:\s*(.+)",
        r"AttributeError:\s*(.+)",
        r"Exception:\s*(.+)",
        r"HTTPException",
        r"status_code.*500",
        r"Internal Server Error",
    ]
    for pat in runtime_patterns:
        m = re.search(pat, combined, re.IGNORECASE)
        if m:
            return ErrorClassification(
                category="runtime_error",
                severity="medium",
                file_hint=_extract_file_path(combined),
                line_hint=_extract_line_number(combined),
                module_hint=None,
                raw_message=m.group(0)[:500],
                suggested_fix=f"运行时异常：{m.group(1) if m.lastindex else m.group(0)}。检查对应代码逻辑。",
                fix_strategy="generic",
            )

    # 缺失文件
    missing_patterns = [
        r"missing apps/api",
        r"missing apps/web",
        r"FileNotFoundError",
        r"No such file or directory:\s*(.+)",
    ]
    for pat in missing_patterns:
        m = re.search(pat, combined, re.IGNORECASE)
        if m:
            return ErrorClassification(
                category="missing_file",
                severity="critical",
                file_hint=_extract_file_path(combined),
                line_hint=None,
                module_hint=None,
                raw_message=m.group(0)[:500],
                suggested_fix="关键文件或目录缺失。检查项目骨架是否完整。",
                fix_strategy="rewrite_file",
            )

    # 余额 / 鉴权：改代码也过不了
    if re.search(
        r"\b402\b|insufficient(?:\s+\w+)?\s+balance|insufficient_quota|quota exceeded|"
        r"余额不足|欠费|credit|billing",
        combined,
        re.IGNORECASE,
    ):
        return ErrorClassification(
            category="quota",
            severity="critical",
            file_hint=None,
            line_hint=None,
            module_hint=None,
            raw_message=combined[:500],
            suggested_fix="模型余额不足或欠费。充值或换 Key 后再跑，不要进 Debug 改代码。",
            fix_strategy="generic",
        )
    if re.search(
        r"\b401\b|invalid api key|incorrect api key|unauthorized|authentication.?fail",
        combined,
        re.IGNORECASE,
    ):
        return ErrorClassification(
            category="auth_error",
            severity="critical",
            file_hint=None,
            line_hint=None,
            module_hint=None,
            raw_message=combined[:500],
            suggested_fix="API Key 无效或未配置。检查 backend/.env 后重试。",
            fix_strategy="generic",
        )

    # LLM / 网络超时
    if re.search(
        r"timed?\s*out|timeout|超时|deadline exceeded|read operation",
        combined,
        re.IGNORECASE,
    ):
        return ErrorClassification(
            category="timeout",
            severity="high",
            file_hint=None,
            line_hint=None,
            module_hint=None,
            raw_message=combined[:500],
            suggested_fix="请求超时。可重试、缩短任务或换 Flash 模型。",
            fix_strategy="generic",
        )

    # 瞬时网络
    if re.search(
        r"connection reset|强迫关闭|远程主机|temporarily unavailable|"
        r"503|502|econnreset|disconnected without sending",
        combined,
        re.IGNORECASE,
    ):
        return ErrorClassification(
            category="transient",
            severity="medium",
            file_hint=None,
            line_hint=None,
            module_hint=None,
            raw_message=combined[:500],
            suggested_fix="瞬时网络或网关故障，适合自动重试。",
            fix_strategy="generic",
        )

    if re.search(r"max_steps|超过 max_steps", combined, re.IGNORECASE):
        return ErrorClassification(
            category="max_steps",
            severity="medium",
            file_hint=None,
            line_hint=None,
            module_hint=None,
            raw_message=combined[:500],
            suggested_fix="Agent 步数用尽。拆小任务或提高 max_steps。",
            fix_strategy="generic",
        )

    # 冒烟 / 测试失败（日志常被截成 [FAIL] attempt=…，没有 SyntaxError 原文）
    if re.search(
        r"\[FAIL\]|SMOKE\s*FAIL|test_failed|pytest.*failed|"
        r"exit=\s*[1-9]|metric.*fail|验收失败",
        combined,
        re.IGNORECASE,
    ):
        return ErrorClassification(
            category="test_failed",
            severity="high",
            file_hint=_extract_file_path(combined),
            line_hint=_extract_line_number(combined),
            module_hint=None,
            raw_message=combined[:500],
            suggested_fix="验收/冒烟未通过。展开节点看完整日志，再按语法/路由等细类修复。",
            fix_strategy="generic",
        )

    # 未分类
    return ErrorClassification(
        category="unknown",
        severity="low",
        file_hint=_extract_file_path(combined),
        line_hint=_extract_line_number(combined),
        module_hint=None,
        raw_message=combined[:500],
        suggested_fix="未分类错误。建议查看完整日志，手动定位问题。",
        fix_strategy="generic",
    )


def _extract_file_path(text: str) -> str | None:
    """从错误文本中提取文件路径。"""
    patterns = [
        r"File\s+\"([^\"]+\.py)\"",
        r"File\s+\"([^\"]+\.tsx?)\"",
        r"File\s+\"([^\"]+\.jsx?)\"",
        r"apps/api/(\S+\.py)",
        r"apps/web/(\S+\.\w+)",
        r"([a-zA-Z0-9_./-]+\.(?:py|tsx?|jsx?|vue))",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1) if m.lastindex else m.group(0)
    return None


def _extract_line_number(text: str) -> int | None:
    """从错误文本中提取行号。"""
    patterns = [
        r"line\s+(\d+)",
        r":(\d+):",
        r"at line (\d+)",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            try:
                return int(m.group(1))
            except (ValueError, IndexError):
                pass
    return None


def build_repair_instruction(classification: ErrorClassification) -> str:
    """根据错误分类生成修复指令。"""
    base = f"【{classification.category}】{classification.suggested_fix}\n"
    if classification.file_hint:
        base += f"目标文件：{classification.file_hint}"
        if classification.line_hint:
            base += f" 第 {classification.line_hint} 行"
        base += "\n"
    if classification.module_hint:
        base += f"缺失模块：{classification.module_hint}\n"
    base += f"原始错误：{classification.raw_message[:300]}\n"

    strategy_hints = {
        "rewrite_file": "请用 write_files 重写该文件，确保语法正确、结构完整。",
        "fix_import": "请检查导入路径，确保模块存在或有 __init__.py，或安装缺失的依赖。",
        "fix_route": "请检查 main.py 是否正确 import 并 include 了路由，确保 API 路径已注册。",
        "fix_build": "请检查 package.json 的依赖版本和入口文件，确保 build 脚本可执行。",
        "generic": "请根据错误信息定位并修复问题。",
    }
    base += f"修复策略：{strategy_hints.get(classification.fix_strategy, 'generic')}\n"
    return base


def classify_failures(
    failures: list[str],
    log_summary: str = "",
) -> list[dict[str, Any]]:
    """批量分类失败项。"""
    results: list[dict[str, Any]] = []
    for f in failures:
        cls = classify_error(f, log_summary)
        results.append({
            "category": cls.category,
            "severity": cls.severity,
            "file_hint": cls.file_hint,
            "line_hint": cls.line_hint,
            "module_hint": cls.module_hint,
            "raw_message": cls.raw_message,
            "suggested_fix": cls.suggested_fix,
            "fix_strategy": cls.fix_strategy,
            "repair_instruction": build_repair_instruction(cls),
        })
    return results


UNFIXABLE_DEBUG_HINTS = (
    "402",
    "insufficient balance",
    "invalid api key",
    "incorrect api key",
    "401",
    "quota",
    "deliver 超时",
)

_LLM_TIMEOUT_HINTS = (
    "openai",
    "deepseek",
    "llm",
    "read operation",
    "the read operation timed out",
)


def is_unfixable_debug_failure(text: str | None) -> bool:
    """余额不足 / 密钥错误 / LLM 超时：改代码也过不了，不要进 Debug。"""
    blob = (text or "").lower()
    if any(h in blob for h in UNFIXABLE_DEBUG_HINTS):
        return True
    if "connection reset" in blob or "强迫关闭" in blob or "远程主机" in blob:
        return True
    if ("timed out" in blob or "timeout" in blob) and any(
        h in blob for h in _LLM_TIMEOUT_HINTS
    ):
        return True
    return False
