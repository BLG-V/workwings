"""上下文管理与任务拆分：确定性拆分子任务、截断 SRS，不新增 Agent。

大模块（商城 / 团购 / 佣金等）禁止一次性塞进单次 LLM 调用，
避免 prompt 过长导致超时后整期 fallback 模板。
"""

from __future__ import annotations

import json
import re
from typing import Any

SRS_TASK_BUDGET = 2800
SRS_PHASE_BUDGET = 6000
CODING_PAYLOAD_BUDGET = 12_000

_TIMEOUT_HINTS = (
    "timed out",
    "timeout",
    "超时",
    "read operation",
    "deadline exceeded",
)


def split_phase_into_subtasks(phase: dict[str, Any]) -> list[dict[str, Any]]:
    """把大里程碑拆成可独立编码的子任务。"""
    pid = str(phase.get("id") or "").lower()
    title = str(phase.get("title") or "")
    goal = str(phase.get("goal") or "")
    text = f"{title} {goal} " + " ".join(str(x) for x in (phase.get("deliverables") or []))

    if pid == "p4" or any(k in text for k in ("商城", "团购", "商品")):
        tasks = [
            {
                "id": "T1",
                "title": "商品列表 API",
                "depends_on": [],
                "detail": "GET/POST /api/products，字段含 name/price/stock",
            },
            {
                "id": "T2",
                "title": "下单占位",
                "depends_on": ["T1"],
                "detail": "POST /api/orders 创建订单占位，关联商品与数量",
            },
            {
                "id": "T3",
                "title": "团长端入口页",
                "depends_on": ["T1"],
                "detail": "apps/web 商品列表 + 下单 + 团长入口页面",
            },
        ]
        if any(k in text for k in ("佣金", "commission", "分成")):
            tasks.append(
                {
                    "id": "T4",
                    "title": "佣金结算",
                    "depends_on": ["T2"],
                    "detail": "团长佣金计算与查询接口，关联订单",
                }
            )
        return tasks

    if pid == "p3" or any(k in text for k in ("后台", "运营")):
        return [
            {"id": "T1", "title": "运营概览 API", "depends_on": [], "detail": "后台概览统计接口"},
            {"id": "T2", "title": "工单列表与权限占位", "depends_on": ["T1"], "detail": "工单列表 + 角色权限占位"},
            {"id": "T3", "title": "后台页面", "depends_on": ["T2"], "detail": "apps/web 运营后台页面"},
        ]

    deliverables = [str(x).strip() for x in (phase.get("deliverables") or []) if str(x).strip()]
    if len(deliverables) >= 2:
        return [
            {
                "id": f"T{i + 1}",
                "title": d[:80],
                "depends_on": [f"T{i}"] if i else [],
                "detail": d,
            }
            for i, d in enumerate(deliverables[:12])
        ]

    clauses = _split_goal_clauses(goal or title)
    if len(clauses) >= 2:
        return [
            {
                "id": f"T{i + 1}",
                "title": c[:80],
                "depends_on": [f"T{i}"] if i else [],
                "detail": c,
            }
            for i, c in enumerate(clauses[:12])
        ]

    return [
        {
            "id": "T1",
            "title": title or pid or "本期增量",
            "depends_on": [],
            "detail": goal or title,
        }
    ]


def _split_goal_clauses(text: str) -> list[str]:
    raw = (text or "").strip()
    if len(raw) < 48:
        return [raw] if raw else []
    parts = re.split(r"[\n；;。]+|、(?=[^、]{6,})", raw)
    out = [p.strip(" -•\t") for p in parts if len(p.strip(" -•\t")) >= 6]
    return out if len(out) >= 2 else ([raw] if raw else [])


def srs_slice_for_task(
    srs_text: str,
    task: dict[str, Any] | None = None,
    *,
    max_chars: int = SRS_TASK_BUDGET,
) -> str:
    """按子任务关键词抽取 SRS 段落，而不是整本塞进 prompt。"""
    text = (srs_text or "").strip()
    if not text:
        return ""
    budget = max(400, int(max_chars))
    if len(text) <= budget:
        return text

    query = " ".join(
        [
            str((task or {}).get("title") or ""),
            str((task or {}).get("detail") or (task or {}).get("description") or ""),
        ]
    )
    keywords = [w for w in re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9_]{2,}", query) if w]
    blocks = re.split(r"\n{2,}|^#{1,3}\s+", text, flags=re.M)
    if keywords:
        scored: list[tuple[int, str]] = []
        for block in blocks:
            b = block.strip()
            if len(b) < 8:
                continue
            score = sum(1 for k in keywords if k.lower() in b.lower())
            if score:
                scored.append((score, b))
        scored.sort(key=lambda x: -x[0])
        picked: list[str] = []
        total = 0
        for _s, b in scored:
            if total >= budget:
                break
            piece = b[: budget - total]
            picked.append(piece)
            total += len(piece)
        if picked:
            return "\n\n".join(picked)[:budget]
    return text[:budget]


def srs_slice_for_phase(
    srs_text: str,
    phase: dict[str, Any] | None = None,
    *,
    max_chars: int = SRS_PHASE_BUDGET,
) -> str:
    blob = " ".join(
        [
            str((phase or {}).get("title") or ""),
            str((phase or {}).get("goal") or ""),
            " ".join(str(x) for x in ((phase or {}).get("deliverables") or [])),
        ]
    )
    return srs_slice_for_task(
        srs_text,
        {"title": blob, "detail": blob},
        max_chars=max_chars,
    )


def prefer_split_tasks(
    planner_tasks: list[dict[str, Any]] | None,
    injected_tasks: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Planner 若把大模块合成 1 条，改用确定性拆分，避免一次生成超时。"""
    planner = [t for t in (planner_tasks or []) if isinstance(t, dict)]
    injected = [t for t in (injected_tasks or []) if isinstance(t, dict)]
    if not injected:
        return planner
    if not planner:
        return injected
    if len(injected) >= 2 and len(planner) <= 1:
        return injected
    if len(injected) > len(planner) + 1:
        return injected
    return planner


def should_retry_coding_task(error: str | None, attempt: int, *, max_attempts: int = 2) -> bool:
    if attempt >= max_attempts:
        return False
    text = (error or "").lower()
    return any(h in text for h in _TIMEOUT_HINTS)


def successful_task_ids(
    *,
    task_runs: list[dict[str, Any]] | None = None,
    tasks_done: list[Any] | None = None,
) -> set[str]:
    """从上次 coding 输出里抽出已成功子任务 id。"""
    done: set[str] = set()
    for tid in tasks_done or []:
        text = str(tid or "").strip()
        if text:
            done.add(text)
    for row in task_runs or []:
        if not isinstance(row, dict):
            continue
        tid = str(row.get("task_id") or row.get("id") or "").strip()
        if not tid:
            continue
        status = str(row.get("status") or "").lower()
        if row.get("success") is True or status in {"ok", "done", "stub_batch"}:
            done.add(tid)
    return done


def plan_coding_resume(
    tasks: list[dict[str, Any]],
    prior: dict[str, Any] | None = None,
    *,
    rerun_all: bool = False,
) -> dict[str, Any]:
    """续跑计划：跳过已成功子任务，只重跑失败/未完成项。

    默认只要 prior 里有成功记录就跳过；rerun_all=True 时强制全量。
    """
    rows = [t for t in tasks if isinstance(t, dict)]
    prior = prior if isinstance(prior, dict) else {}
    if rerun_all or not prior:
        return {
            "pending": rows,
            "skipped": [],
            "carried_task_runs": [],
            "carried_changed_files": [],
            "carried_done": [],
            "resumed": False,
        }

    prior_runs = [r for r in (prior.get("task_runs") or []) if isinstance(r, dict)]
    prior_done = list(prior.get("tasks_done") or [])
    done_ids = successful_task_ids(task_runs=prior_runs, tasks_done=prior_done)
    prior_by_id = {
        str(r.get("task_id") or r.get("id") or ""): r
        for r in prior_runs
        if str(r.get("task_id") or r.get("id") or "")
    }

    pending: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    carried_runs: list[dict[str, Any]] = []
    carried_done: list[str] = []
    carried_files: list[str] = []

    for f in prior.get("changed_files") or []:
        text = str(f or "").strip()
        if text and text not in carried_files:
            carried_files.append(text)

    for i, task in enumerate(rows):
        tid = str(task.get("id") or f"T{i + 1}").strip()
        if tid in done_ids:
            prev = dict(prior_by_id.get(tid) or {})
            meta = {
                "task_id": tid,
                "title": task.get("title") or prev.get("title"),
                "success": True,
                "changed_files": list(prev.get("changed_files") or []),
                "error": None,
                "attempts": int(prev.get("attempts") or 1),
                "skipped": True,
                "status": "skipped_ok",
            }
            skipped.append(meta)
            carried_runs.append(meta)
            carried_done.append(tid)
            for f in meta["changed_files"]:
                text = str(f or "").strip()
                if text and text not in carried_files:
                    carried_files.append(text)
        else:
            pending.append(task)

    return {
        "pending": pending,
        "skipped": skipped,
        "carried_task_runs": carried_runs,
        "carried_changed_files": carried_files,
        "carried_done": carried_done,
        "resumed": bool(skipped),
    }


def prior_coding_output(
    input_data: dict[str, Any] | None,
    nodes_outputs: dict[str, Any] | None,
) -> dict[str, Any]:
    """合并 input / 上游 coding 节点里的续跑线索。"""
    merged: dict[str, Any] = {}
    coding = (nodes_outputs or {}).get("coding")
    if isinstance(coding, dict):
        merged.update(coding)
    raw = input_data or {}
    for key in ("task_runs", "tasks_done", "changed_files"):
        if key in raw and raw[key] is not None:
            merged[key] = raw[key]
    prior_block = raw.get("prior_coding")
    if isinstance(prior_block, dict):
        merged.update(prior_block)
    return merged


def compact_prior_outputs(nodes_outputs: dict[str, Any] | None) -> dict[str, Any]:
    slim: dict[str, Any] = {}
    for key, val in (nodes_outputs or {}).items():
        if not isinstance(val, dict):
            slim[key] = val
            continue
        keep: dict[str, Any] = {}
        for field in ("status", "tasks", "count", "changed_files", "api_contract", "pages"):
            if field in val:
                keep[field] = val[field]
        if val.get("summary"):
            keep["summary"] = str(val["summary"])[:400]
        slim[key] = keep
    return slim


def compact_coding_payload(
    *,
    input_data: dict[str, Any],
    params: dict[str, Any],
    prior_outputs: dict[str, Any] | None,
    task: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Coding 子运行只带当前任务 + 切片 SRS，丢掉整本规格与上游长文本。"""
    srs = str(params.get("srs_excerpt") or input_data.get("srs_excerpt") or "")
    sliced = srs_slice_for_task(srs, task)
    lean_params = {
        "project_mode": params.get("project_mode"),
        "project_root": params.get("project_root"),
        "frontend_dir": params.get("frontend_dir"),
        "phase_id": params.get("phase_id"),
        "current_task_id": (task or {}).get("id") or params.get("current_task_id"),
        "current_task_title": (task or {}).get("title") or params.get("current_task_title"),
        "srs_excerpt": sliced,
        "metric_command": params.get("metric_command"),
    }
    lean_input = {
        "current_task": task or input_data.get("current_task"),
        "task_index": input_data.get("task_index"),
        "tasks_total": input_data.get("tasks_total"),
        "already_changed_files": list(input_data.get("already_changed_files") or [])[:40],
        "instruction": str(input_data.get("instruction") or "")[:1200],
        "api_contract": input_data.get("api_contract")
        or ((prior_outputs or {}).get("coding") or {}).get("api_contract"),
        "goal": str((task or {}).get("title") or input_data.get("goal") or "")[:200],
    }
    payload = {
        "input": lean_input,
        "params": lean_params,
        "prior_outputs": compact_prior_outputs(prior_outputs),
        "project_constraints": {
            "project_root": params.get("project_root"),
            "frontend_dir": params.get("frontend_dir"),
            "phase_id": params.get("phase_id"),
            "srs_excerpt_chars": len(sliced),
            "rule": "只实现当前子任务；只在 project_root 下写代码；禁止修改平台源码",
        },
    }
    dumped = json.dumps(payload, ensure_ascii=False, default=str)
    if len(dumped) > CODING_PAYLOAD_BUDGET:
        payload["params"]["srs_excerpt"] = sliced[: max(400, SRS_TASK_BUDGET // 2)]
    return payload


def payload_char_count(payload: dict[str, Any]) -> int:
    return len(json.dumps(payload, ensure_ascii=False, default=str))
