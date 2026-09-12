"""阶段生成结果判定：完成 / 部分完成 / 失败，占位检测与重试分类。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

PLACEHOLDER_MARKERS = (
    "Auto increment for",
    "新增条目",
    'prefix="/api/{slug}"',  # rendered templates keep real slug; keep as extra
    "通用占位",
)

# 通用增量壳：只有 /items CRUD，没有业务语义
GENERIC_ITEM_PATTERNS = (
    r'@router\.get\("/items"\)',
    r"def list_items\(",
    r"def create_item\(",
    r"新增条目",
    r"Auto increment for",
)

RETRYABLE_HINTS = (
    "timed out",
    "timeout",
    "超时",
    "connection reset",
    "connection aborted",
    "强迫关闭",
    "远程主机",
    "server disconnected",
    "temporarily unavailable",
    "429",
    "502",
    "503",
    "504",
    "winerror 10054",
    "read operation",
)

FATAL_HINTS = (
    "402",
    "insufficient balance",
    "invalid api key",
    "incorrect api key",
    "401",
    "quota",
)


def is_retryable_failure(exc: BaseException) -> bool:
    """瞬时网络/超时可重试；余额不足等不可重试。"""
    if isinstance(exc, (TimeoutError, ConnectionError, ConnectionResetError, ConnectionAbortedError)):
        text = str(exc).lower()
        if any(h in text for h in FATAL_HINTS):
            return False
        return True
    text = str(exc).lower()
    if any(h in text for h in FATAL_HINTS):
        return False
    return any(h in text for h in RETRYABLE_HINTS)


def run_deliver_with_retry(
    fn: Callable[[], Any],
    *,
    max_attempts: int = 3,
    sleep: Callable[[float], None] | None = None,
) -> tuple[Any | None, int, BaseException | None]:
    """对瞬时失败做指数退避重试。返回 (result, attempts, last_error)。"""
    import time

    sleeper = sleep if sleep is not None else time.sleep
    last_error: BaseException | None = None
    attempts = 0
    for i in range(max(1, max_attempts)):
        attempts = i + 1
        try:
            return fn(), attempts, None
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if not is_retryable_failure(exc) or i >= max_attempts - 1:
                break
            sleeper(min(8.0, 1.0 * (2**i)))
    return None, attempts, last_error


def _read_written_blob(workspace: Path, written: list[str]) -> str:
    parts: list[str] = []
    for rel in written:
        path = workspace / rel
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8", errors="ignore"))
        else:
            parts.append(rel)
    return "\n".join(parts)


def detect_placeholder_output(workspace: Path, written: list[str]) -> bool:
    """识别通用占位增量（/items + 新增条目），区别于真实业务代码。"""
    if not written:
        return False
    blob = _read_written_blob(workspace, written)
    hits = sum(1 for pat in GENERIC_ITEM_PATTERNS if re.search(pat, blob))
    return hits >= 2


def _phase_keywords(phase: dict[str, Any]) -> list[str]:
    text = " ".join(
        [
            str(phase.get("title") or ""),
            str(phase.get("goal") or ""),
            " ".join(str(x) for x in (phase.get("deliverables") or [])),
        ]
    )
    vocab = [
        ("商品", ("商品", "product", "mall", "sku", "团购", "下单", "订单", "团长")),
        ("缴费", ("账单", "缴费", "支付", "bill", "pay")),
        ("报修", ("报修", "repair", "工单")),
        ("后台", ("后台", "admin", "权限", "overview")),
        ("通知", ("通知", "notification")),
        ("AI", ("ai", "识图", "问答", "gateway")),
    ]
    keys: list[str] = []
    lower = text.lower()
    for _label, group in vocab:
        if any(k.lower() in lower or k in text for k in group):
            keys.extend(group)
    # 去重且只保留出现在目标文本里的词，避免过宽
    return [k for k in dict.fromkeys(keys) if k.lower() in lower or k in text]


def validate_phase_against_spec(
    workspace: Path,
    phase: dict[str, Any],
    written: list[str],
) -> list[str]:
    """对照本期 goal/deliverables，返回未覆盖的能力缺口。

    通用 /items 壳即使把 goal 抄进注释，也不算覆盖商品/下单等业务接口。
    """
    if not written:
        goal = str(phase.get("goal") or phase.get("title") or "本期目标")
        return [goal]
    if detect_placeholder_output(workspace, written):
        return [str(phase.get("goal") or phase.get("title") or "通用占位未覆盖需求")]

    blob = _read_written_blob(workspace, written)
    blob_l = blob.lower()
    keywords = _phase_keywords(phase)
    if not keywords:
        return []

    evidence_groups = [
        (["商品", "product", "mall", "sku", "团购"], [r"/api/products", r"def list_products", r"group_buy"]),
        (["下单", "订单", "order"], [r"/api/orders", r"def create_order"]),
        (["团长"], [r"/api/captains", r"captain", r"团长"]),
        (["账单", "缴费", "bill"], [r"/api/bills", r"def list_bills"]),
        (["支付", "pay"], [r"/pay", r"def pay_"]),
        (["报修", "repair"], [r"/api/repairs", r"def .*repair"]),
        (["工单"], [r"/api/workorders", r"/api/admin/tickets", r"tickets"]),
        (["后台", "admin"], [r"/api/admin", r"admin.html"]),
        (["权限"], [r"role", r"rbac", r"权限"]),
        (["通知", "notification"], [r"/api/notifications", r"notification"]),
        (["识图", "问答", "ai", "gateway"], [r"/api/p5", r"ai_gateway", r"/api/.*/ai"]),
    ]
    missing: list[str] = []
    for keys, patterns in evidence_groups:
        if not any(k in keywords for k in keys):
            continue
        if not any(re.search(pat, blob_l if pat.islower() or pat.startswith("/") else blob, re.I) for pat in patterns):
            missing.append("/".join(keys[:2]))
    return missing


def resolve_phase_outcome(
    *,
    via: str,
    written: list[str],
    testing: dict[str, Any] | None,
    placeholder: bool,
    spec_gaps: list[str],
) -> dict[str, Any]:
    """把生成路径与验收结果收成三档状态。"""
    via_l = (via or "").lower()
    degraded = (
        "template_fallback" in via_l
        or "deliver+template" in via_l
    )
    testing_failed = bool(testing) and testing.get("passed") is False

    if not written:
        status = "failed"
    elif degraded or placeholder or spec_gaps or testing_failed:
        status = "partial"
    else:
        status = "done"

    return {
        "status": status,
        "degraded": degraded or placeholder,
        "placeholder": placeholder,
        "spec_gaps": list(spec_gaps),
        "via": via,
    }


def phase_subtasks(phase: dict[str, Any]) -> list[dict[str, Any]]:
    """大模块拆成可独立编码的子任务，降低超时/超上下文概率。"""
    from mawp.runtime.task_split import split_phase_into_subtasks

    return split_phase_into_subtasks(phase)
