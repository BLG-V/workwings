"""确定性验收门禁：按 ACCEPTANCE 用例打 HTTP，区分完成 / 空壳 / 失败。

不是新 Agent。Testing 冒烟读取 docs/acceptance_cases.json；
空壳或 404 记为失败，分期不能标 done。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

ACCEPTANCE_CASES_REL = "docs/acceptance_cases.json"
ACCEPTANCE_REPORT_REL = "docs/ACCEPTANCE_REPORT.md"

HOLLOW_SUBSTRINGS = (
    "新增条目",
    "auto increment",
    "notimplemented",
    "not implemented",
    "placeholder",
    "通用占位",
    "todo: implement",
)

GENERIC_ITEM_KEYS = {
    "id",
    "title",
    "note",
    "created_at",
    "updated_at",
}

RequestFn = Callable[..., tuple[int, str]]


def default_cases_for_phase(
    phase_id: str | None,
    *,
    title: str = "",
    goal: str = "",
) -> list[dict[str, Any]]:
    pid = (phase_id or "").strip().lower()
    text = f"{pid} {title} {goal}".lower()
    cases: list[dict[str, Any]] = [
        {
            "id": "health",
            "method": "GET",
            "path": "/health",
            "expect_status": [200],
        }
    ]
    hollow = list(HOLLOW_SUBSTRINGS)

    def add(
        cid: str,
        path: str,
        *,
        keys: list[str] | None = None,
        item_keys: list[str] | None = None,
        generic: bool = False,
    ) -> None:
        case: dict[str, Any] = {
            "id": cid,
            "method": "GET",
            "path": path,
            "expect_status": [200],
            "reject_body_substrings": hollow,
        }
        if keys:
            case["required_any_keys"] = keys
        if item_keys:
            case["item_required_keys"] = item_keys
        if generic:
            case["reject_if_generic_items"] = True
        cases.append(case)

    if pid == "p1" or any(k in text for k in ("报修", "repair")):
        add("repairs-list", "/api/repairs", keys=["items", "orders", "total"])
    if pid == "p2" or any(k in text for k in ("缴费", "账单", "bill")):
        add("bills-list", "/api/bills", keys=["items", "bills", "total"])
    if pid == "p3" or any(k in text for k in ("后台", "运营", "admin")):
        add("admin-overview", "/api/admin/overview", keys=["ok", "stats", "tickets", "total"])
    if pid == "p4" or any(k in text for k in ("商城", "团购", "商品", "mall", "product")):
        add(
            "products-list",
            "/api/products",
            keys=["items", "products"],
            item_keys=["name", "price"],
            generic=True,
        )
        add("orders-list", "/api/orders", keys=["items", "orders"])
        add("captains-list", "/api/captains", keys=["items", "captains"])
    if pid == "p5" or any(k in text for k in ("识图", "问答", "gateway")):
        add("ai-gateway", "/api/p5/ai/ping", keys=["ok", "status", "message"])
        cases.append(
            {
                "id": "ai-alt",
                "method": "GET",
                "path": "/api/p5/health",
                "expect_status": [200, 404],
                "optional": True,
            }
        )
    return cases


def _parse_json(body: str) -> Any:
    try:
        return json.loads(body or "")
    except json.JSONDecodeError:
        return None


def _is_generic_items(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    items = data.get("items")
    if not isinstance(items, list) or not items:
        return False
    for row in items:
        if not isinstance(row, dict):
            return False
        extra = set(row.keys()) - GENERIC_ITEM_KEYS
        if extra:
            return False
        if "title" not in row and "name" not in row:
            return False
        if "name" in row or "price" in row:
            return False
    return True


def classify_response(status: int, body: str, case: dict[str, Any]) -> str:
    """返回 pass / placeholder / fail。"""
    expect = [int(x) for x in (case.get("expect_status") or [200])]
    text = body or ""
    low = text.lower()
    if case.get("optional") and status == 404:
        return "pass"
    if status >= 500:
        return "fail"
    if status in (404, 405, 501) and status not in expect:
        return "fail"
    if status not in expect:
        return "fail"
    for needle in case.get("reject_body_substrings") or []:
        if str(needle).lower() in low:
            return "placeholder"
    data = _parse_json(text)
    keys = list(case.get("required_any_keys") or [])
    if keys:
        if not isinstance(data, dict) or not any(k in data for k in keys):
            return "placeholder"
    item_keys = list(case.get("item_required_keys") or [])
    if item_keys and isinstance(data, dict):
        rows = data.get("items") or data.get("products") or data.get("orders") or []
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                if not all(k in row for k in item_keys):
                    return "placeholder"
    if case.get("reject_if_generic_items") and _is_generic_items(data):
        return "placeholder"
    return "pass"


@dataclass
class CaseResult:
    id: str
    path: str
    method: str
    status_code: int
    verdict: str
    detail: str = ""


@dataclass
class AcceptanceReport:
    results: list[CaseResult] = field(default_factory=list)
    phase_id: str = ""

    @property
    def passed(self) -> bool:
        return bool(self.results) and all(r.verdict == "pass" for r in self.results)

    def grouped(self) -> dict[str, list[CaseResult]]:
        out = {"pass": [], "placeholder": [], "fail": []}
        for r in self.results:
            out.setdefault(r.verdict, []).append(r)
        return out

    def to_dict(self) -> dict[str, Any]:
        g = self.grouped()
        return {
            "phase_id": self.phase_id,
            "passed": self.passed,
            "completed": [r.id for r in g.get("pass") or []],
            "placeholder": [r.id for r in g.get("placeholder") or []],
            "failed": [r.id for r in g.get("fail") or []],
            "results": [
                {
                    "id": r.id,
                    "path": r.path,
                    "method": r.method,
                    "status_code": r.status_code,
                    "verdict": r.verdict,
                    "detail": r.detail,
                }
                for r in self.results
            ],
        }


def run_acceptance_cases(
    request: RequestFn,
    cases: list[dict[str, Any]],
    *,
    phase_id: str = "",
) -> AcceptanceReport:
    report = AcceptanceReport(phase_id=phase_id)
    for case in cases:
        method = str(case.get("method") or "GET").upper()
        path = str(case.get("path") or "/")
        cid = str(case.get("id") or path)
        try:
            status, body = request(method, path)
        except Exception as exc:  # noqa: BLE001
            report.results.append(
                CaseResult(
                    id=cid,
                    path=path,
                    method=method,
                    status_code=0,
                    verdict="fail",
                    detail=str(exc)[:200],
                )
            )
            continue
        verdict = classify_response(int(status), str(body or ""), case)
        detail = f"{method} {path} -> {status}"
        if verdict != "pass":
            detail += f" ({verdict})"
        report.results.append(
            CaseResult(
                id=cid,
                path=path,
                method=method,
                status_code=int(status),
                verdict=verdict,
                detail=detail,
            )
        )
    return report


def format_acceptance_report(report: AcceptanceReport) -> str:
    g = report.grouped()
    lines = [
        f"# 验收报告 · {(report.phase_id or 'phase').upper()}",
        "",
        f"- 通过：{len(g.get('pass') or [])}",
        f"- 空壳占位：{len(g.get('placeholder') or [])}",
        f"- 失败：{len(g.get('fail') or [])}",
        "",
        "## 完成",
    ]
    done = g.get("pass") or []
    lines.extend([f"- `{r.method} {r.path}` ({r.id})" for r in done] or ["- （无）"])
    lines.extend(["", "## 空壳"])
    hollow = g.get("placeholder") or []
    lines.extend([f"- `{r.method} {r.path}` — {r.detail}" for r in hollow] or ["- （无）"])
    lines.extend(["", "## 失败"])
    failed = g.get("fail") or []
    lines.extend([f"- `{r.method} {r.path}` — {r.detail}" for r in failed] or ["- （无）"])
    lines.append("")
    return "\n".join(lines)


def write_acceptance_cases(
    workspace: Path,
    project_root: str,
    *,
    phase_id: str | None,
    title: str = "",
    goal: str = "",
) -> Path:
    root = str(project_root or "").replace("\\", "/").rstrip("/")
    cases = default_cases_for_phase(phase_id, title=title, goal=goal)
    payload = {
        "phase_id": (phase_id or "").strip().lower(),
        "title": title,
        "goal": goal,
        "cases": cases,
    }
    path = workspace / root / ACCEPTANCE_CASES_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_acceptance_report_file(
    workspace: Path,
    project_root: str,
    report: AcceptanceReport,
) -> Path:
    root = str(project_root or "").replace("\\", "/").rstrip("/")
    path = workspace / root / ACCEPTANCE_REPORT_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(format_acceptance_report(report), encoding="utf-8")
    return path


_PATH_LINE = re.compile(r"`(/api/[a-zA-Z0-9_/{}.-]+)`")


def cases_from_acceptance_markdown(text: str, *, phase_id: str = "") -> list[dict[str, Any]]:
    """从 ACCEPTANCE_Px.md 抽路径，补进默认用例（文档优先）。"""
    base = default_cases_for_phase(phase_id)
    seen = {c["path"] for c in base}
    for raw in _PATH_LINE.findall(text or "") + re.findall(
        r"/api/[a-zA-Z0-9_/{}.-]+", text or ""
    ):
        path = raw.split("{")[0].rstrip("/") or raw
        if path in seen or path.endswith("/items"):
            continue
        seen.add(path)
        stem = path.rstrip("/").split("/")[-1] or "api"
        base.append(
            {
                "id": f"doc-{stem}",
                "method": "GET",
                "path": path if path.startswith("/") else "/" + path,
                "expect_status": [200],
                "reject_body_substrings": list(HOLLOW_SUBSTRINGS),
            }
        )
    return base
