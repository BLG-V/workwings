"""产物差距比对：SRS 能力表 vs 仓库证据 → 三态 + GAP 报告 + NEXT_TASKS。"""

from __future__ import annotations

import json
from pathlib import Path

from mawp.runtime.gap_report import (
    CapabilityStatus,
    build_gap_report,
    format_gap_markdown,
    scan_workspace_capabilities,
    write_gap_artifacts,
)


SRS_SAMPLE = """
# 邻智云 SRS
- 业主报修与接单
- 物业缴费与模拟支付
- 真实微信支付
- 商城团购
- 微信小程序端
- 运营数据大屏
- AI 客服问答与识图报修
"""


def _ws_with_repair(tmp_path: Path) -> Path:
    ws = tmp_path / "proj"
    api = ws / "apps" / "api"
    web = ws / "apps" / "web"
    api.mkdir(parents=True)
    web.mkdir(parents=True)
    (ws / "docs").mkdir(parents=True)
    (ws / "docs" / "SRS.md").write_text(SRS_SAMPLE, encoding="utf-8")
    (api / "main.py").write_text(
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.get('/api/repairs')\n"
        "def repairs():\n"
        "    return {'items': []}\n",
        encoding="utf-8",
    )
    (web / "repair.html").write_text("<html>报修</html>", encoding="utf-8")
    return ws


def test_scan_marks_missing_miniapp_and_bigscreen(tmp_path: Path) -> None:
    ws = _ws_with_repair(tmp_path)
    items = scan_workspace_capabilities(ws, srs_text=SRS_SAMPLE)
    by_id = {i.id: i for i in items}
    assert by_id["repair"].status == CapabilityStatus.DONE
    assert by_id["miniapp"].status == CapabilityStatus.MISSING
    assert by_id["bigscreen"].status == CapabilityStatus.MISSING
    assert by_id["pay_real"].status == CapabilityStatus.MISSING


def test_placeholder_mall_is_partial(tmp_path: Path) -> None:
    ws = _ws_with_repair(tmp_path)
    (ws / "apps" / "api" / "module_p4.py").write_text(
        '"""Auto increment for p4"""\n'
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n"
        '@router.get("/items")\n'
        "def list_items():\n"
        "    return {'items': []}\n"
        "新增条目\n",
        encoding="utf-8",
    )
    items = scan_workspace_capabilities(ws, srs_text=SRS_SAMPLE)
    by_id = {i.id: i for i in items}
    assert by_id["mall"].status == CapabilityStatus.PARTIAL


def test_real_mall_routes_are_done(tmp_path: Path) -> None:
    ws = _ws_with_repair(tmp_path)
    (ws / "apps" / "api" / "routers").mkdir()
    (ws / "apps" / "api" / "routers" / "mall.py").write_text(
        "@router.get('/api/products')\n"
        "def list_products(): ...\n"
        "@router.get('/api/orders')\n"
        "def list_orders(): ...\n"
        "@router.get('/api/captains')\n"
        "def list_captains(): ...\n"
        "tenant_id = 'demo-tenant'\n",
        encoding="utf-8",
    )
    items = scan_workspace_capabilities(ws, srs_text=SRS_SAMPLE)
    assert {i.id: i.status for i in items}["mall"] == CapabilityStatus.DONE


def test_write_gap_artifacts(tmp_path: Path) -> None:
    ws = _ws_with_repair(tmp_path)
    report = build_gap_report(ws)
    paths = write_gap_artifacts(ws, report)
    assert (ws / "docs" / "GAP_WITH_SRS.md").is_file()
    assert (ws / "docs" / "NEXT_TASKS.json").is_file()
    md = (ws / "docs" / "GAP_WITH_SRS.md").read_text(encoding="utf-8")
    assert "完全未实现" in md
    assert "小程序" in md or "miniapp" in md.lower() or "微信小程序" in md
    tasks = json.loads((ws / "docs" / "NEXT_TASKS.json").read_text(encoding="utf-8"))
    assert isinstance(tasks, list)
    assert any("小程序" in t.get("title", "") or t.get("capability_id") == "miniapp" for t in tasks)
    assert "GAP_WITH_SRS.md" in " ".join(paths)


def test_format_gap_markdown_has_three_sections() -> None:
    from mawp.runtime.gap_report import GapItem, GapReport

    r = GapReport(
        items=[
            GapItem("repair", "报修", CapabilityStatus.DONE, "ok"),
            GapItem("mall", "商城", CapabilityStatus.PARTIAL, "items shell"),
            GapItem("miniapp", "小程序", CapabilityStatus.MISSING, "no evidence"),
        ]
    )
    md = format_gap_markdown(r)
    assert "## 已完成" in md
    assert "## 部分占位" in md
    assert "## 完全未实现" in md
