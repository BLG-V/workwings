"""产物差距比对（对标 SRS）：确定性扫描，不新增 Agent。

从 docs/SRS.md + 能力表抽出能力项，对照仓库证据分为：
已完成 / 部分占位 / 完全未实现，并写出 GAP_WITH_SRS.md 与 NEXT_TASKS.json。
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class CapabilityStatus(str, Enum):
    DONE = "done"
    PARTIAL = "partial"
    MISSING = "missing"


@dataclass(frozen=True)
class CapabilityDef:
    id: str
    title: str
    srs_hints: tuple[str, ...]
    evidence: tuple[str, ...]  # regex against workspace blob
    placeholder_hints: tuple[str, ...] = ()
    priority: int = 2  # 1 high


# 邻智云 / 社区类 SRS 默认能力表（可后续扩展）
DEFAULT_CAPABILITIES: tuple[CapabilityDef, ...] = (
    CapabilityDef(
        "repair",
        "报修闭环",
        ("报修", "报事", "工单报修"),
        (r"/api/repairs", r"repair\.html", r"def\s+\w*repair"),
        priority=1,
    ),
    CapabilityDef(
        "billing",
        "物业缴费",
        ("缴费", "账单", "物业费"),
        (r"/api/bills", r"billing\.html", r"bills\.html", r"def\s+list_bills"),
        priority=1,
    ),
    CapabilityDef(
        "pay_mock",
        "模拟支付",
        ("模拟支付", "支付占位", "mock.?pay"),
        (r"/api/.*/pay", r"def\s+pay_", r"模拟支付"),
        priority=2,
    ),
    CapabilityDef(
        "pay_real",
        "真实支付",
        ("微信支付", "真实支付", "支付宝", "wechat.?pay", "alipay"),
        (r"wechat.?pay|微信支付|alipay|支付宝.?sdk|wxpay",),
        placeholder_hints=(r"模拟支付", r"mock.?pay", r"fake.?pay"),
        priority=1,
    ),
    CapabilityDef(
        "mall",
        "商城团购",
        ("商城", "团购", "商品"),
        (r"/api/products", r"/api/orders", r"/api/captains", r"p4\.html", r"mall\.py"),
        placeholder_hints=(
            r'Auto increment for',
            r'新增条目',
            r'@router\.get\("/items"\)',
            r"def list_items\(",
        ),
        priority=1,
    ),
    CapabilityDef(
        "admin",
        "运营后台",
        ("运营后台", "管理后台", "权限"),
        (r"/api/admin", r"admin\.html", r"rbac"),
        priority=2,
    ),
    CapabilityDef(
        "ai",
        "AI 问答/识图",
        ("AI", "识图", "问答", "客服"),
        (r"ai_gateway", r"/api/p5", r"ai\.html", r"/api/.*/ai"),
        priority=2,
    ),
    CapabilityDef(
        "miniapp",
        "微信小程序",
        ("小程序", "微信小程序", "miniprogram"),
        (r"miniprogram/", r"app\.json", r"project\.config\.json", r"\bwx\."),
        priority=1,
    ),
    CapabilityDef(
        "bigscreen",
        "运营数据大屏",
        ("大屏", "数据大屏", "可视化看板"),
        (r"big.?screen", r"dashboard", r"大屏", r"echarts"),
        priority=1,
    ),
)


@dataclass
class GapItem:
    id: str
    title: str
    status: CapabilityStatus
    detail: str
    priority: int = 2

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status.value,
            "detail": self.detail,
            "priority": self.priority,
        }


@dataclass
class GapReport:
    items: list[GapItem] = field(default_factory=list)
    srs_path: str = "docs/SRS.md"

    def by_status(self, status: CapabilityStatus) -> list[GapItem]:
        return [i for i in self.items if i.status == status]

    def to_dict(self) -> dict[str, Any]:
        return {
            "srs_path": self.srs_path,
            "completed": [i.to_dict() for i in self.by_status(CapabilityStatus.DONE)],
            "partial": [i.to_dict() for i in self.by_status(CapabilityStatus.PARTIAL)],
            "missing": [i.to_dict() for i in self.by_status(CapabilityStatus.MISSING)],
            "items": [i.to_dict() for i in self.items],
        }


def _read_workspace_blob(workspace: Path) -> str:
    """只扫实现目录，避免 docs/SRS.md 自身关键词造成假阳性。"""
    parts: list[str] = []
    roots = [
        workspace / "apps",
        workspace / "miniprogram",
        workspace / "frontend",
        workspace / "scripts",
    ]
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {
                ".py",
                ".html",
                ".js",
                ".ts",
                ".tsx",
                ".json",
                ".css",
                ".vue",
                ".wxml",
                ".wxss",
            }:
                continue
            if path.stat().st_size > 400_000:
                continue
            try:
                parts.append(path.read_text(encoding="utf-8", errors="ignore"))
                parts.append(path.relative_to(workspace).as_posix())
            except OSError:
                continue
    # 目录名证据（如 miniprogram/）
    for name in ("miniprogram", "miniapp", "dashboard", "bigscreen"):
        if (workspace / name).exists():
            parts.append(name + "/")
    return "\n".join(parts)


def _srs_mentions(srs_text: str, hints: tuple[str, ...]) -> bool:
    if not srs_text.strip():
        return True  # 无 SRS 时仍扫默认表，便于演示
    low = srs_text.lower()
    return any(h.lower() in low or h in srs_text for h in hints)


def _any_evidence(blob: str, patterns: tuple[str, ...]) -> bool:
    for pat in patterns:
        if re.search(pat, blob, re.IGNORECASE):
            return True
    return False


def scan_workspace_capabilities(
    workspace: Path,
    *,
    srs_text: str | None = None,
    capabilities: tuple[CapabilityDef, ...] | None = None,
) -> list[GapItem]:
    srs = srs_text
    if srs is None:
        srs_path = workspace / "docs" / "SRS.md"
        srs = srs_path.read_text(encoding="utf-8", errors="ignore") if srs_path.is_file() else ""
    blob = _read_workspace_blob(workspace)
    caps = capabilities or DEFAULT_CAPABILITIES
    items: list[GapItem] = []
    for cap in caps:
        if not _srs_mentions(srs or "", cap.srs_hints):
            continue
        has = _any_evidence(blob, cap.evidence)
        hollow = bool(cap.placeholder_hints) and _any_evidence(blob, cap.placeholder_hints)
        if not has:
            # 对 mall：仅有 /items 壳也算 partial（有痕迹但非真业务）
            if hollow and cap.id == "mall":
                items.append(
                    GapItem(
                        cap.id,
                        cap.title,
                        CapabilityStatus.PARTIAL,
                        "检出通用 /items 占位，缺少商品/订单等真实接口",
                        cap.priority,
                    )
                )
            else:
                items.append(
                    GapItem(
                        cap.id,
                        cap.title,
                        CapabilityStatus.MISSING,
                        "SRS 提及但仓库无实现证据",
                        cap.priority,
                    )
                )
            continue
        if hollow and cap.id != "pay_real":
            items.append(
                GapItem(
                    cap.id,
                    cap.title,
                    CapabilityStatus.PARTIAL,
                    "有文件/路由痕迹，但命中占位特征",
                    cap.priority,
                )
            )
            continue
        if cap.id == "pay_real" and hollow and not _any_evidence(
            blob, (r"wechat.?pay|wxpay|alipay.?sdk",)
        ):
            items.append(
                GapItem(
                    cap.id,
                    cap.title,
                    CapabilityStatus.PARTIAL,
                    "仅有模拟/占位支付，未见真实支付 SDK",
                    cap.priority,
                )
            )
            continue
        items.append(
            GapItem(cap.id, cap.title, CapabilityStatus.DONE, "证据命中", cap.priority)
        )
    return items


def build_gap_report(workspace: Path, *, srs_text: str | None = None) -> GapReport:
    return GapReport(
        items=scan_workspace_capabilities(workspace, srs_text=srs_text),
        srs_path="docs/SRS.md",
    )


def format_gap_markdown(report: GapReport) -> str:
    lines = [
        "# 产物差距比对（对标 SRS）",
        "",
        f"对照：`{report.srs_path}`",
        "",
        "## 已完成",
    ]
    done = report.by_status(CapabilityStatus.DONE)
    lines.extend([f"- **{i.title}**（`{i.id}`）：{i.detail}" for i in done] or ["- （无）"])
    lines.extend(["", "## 部分占位"])
    partial = report.by_status(CapabilityStatus.PARTIAL)
    lines.extend([f"- **{i.title}**（`{i.id}`）：{i.detail}" for i in partial] or ["- （无）"])
    lines.extend(["", "## 完全未实现"])
    missing = report.by_status(CapabilityStatus.MISSING)
    lines.extend([f"- **{i.title}**（`{i.id}`）：{i.detail}" for i in missing] or ["- （无）"])
    lines.extend(["", "## 建议下一步", ""])
    tasks = next_tasks_from_report(report)
    if not tasks:
        lines.append("- 暂无强制补齐项")
    else:
        for t in tasks:
            lines.append(f"- [{t['priority']}] {t['title']} — {t['reason']}")
    lines.append("")
    return "\n".join(lines)


def next_tasks_from_report(report: GapReport) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for item in report.items:
        if item.status == CapabilityStatus.DONE:
            continue
        action = "补齐实现" if item.status == CapabilityStatus.MISSING else "替换占位为真实实现"
        tasks.append(
            {
                "capability_id": item.id,
                "title": f"{action}：{item.title}",
                "reason": item.detail,
                "status": item.status.value,
                "priority": "P0" if item.priority <= 1 else "P1",
                "suggested_phase": {
                    "repair": "p1",
                    "billing": "p2",
                    "pay_mock": "p2",
                    "pay_real": "p2+",
                    "admin": "p3",
                    "mall": "p4",
                    "ai": "p5",
                    "miniapp": "p6",
                    "bigscreen": "p6",
                }.get(item.id, "backlog"),
            }
        )
    # 未实现优先、高优先级优先
    tasks.sort(
        key=lambda t: (
            0 if t["status"] == "missing" else 1,
            0 if t["priority"] == "P0" else 1,
            t["capability_id"],
        )
    )
    return tasks


def write_gap_artifacts(workspace: Path, report: GapReport | None = None) -> list[str]:
    report = report or build_gap_report(workspace)
    docs = workspace / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    gap_md = docs / "GAP_WITH_SRS.md"
    tasks_json = docs / "NEXT_TASKS.json"
    gap_md.write_text(format_gap_markdown(report), encoding="utf-8")
    tasks_json.write_text(
        json.dumps(next_tasks_from_report(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # 机器可读汇总
    (docs / "gap_report.json").write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return [
        "docs/GAP_WITH_SRS.md",
        "docs/NEXT_TASKS.json",
        "docs/gap_report.json",
    ]
