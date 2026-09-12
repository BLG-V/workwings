"""验收闭环门禁：ACCEPTANCE 驱动 HTTP 探测，区分空壳与真业务。"""

from __future__ import annotations

import json
from pathlib import Path

from mawp.runtime.acceptance_gate import (
    ACCEPTANCE_CASES_REL,
    classify_response,
    default_cases_for_phase,
    format_acceptance_report,
    run_acceptance_cases,
    write_acceptance_cases,
)
from mawp.runtime.project_deliver import write_phase_acceptance_note, write_smoke_script


def test_p4_cases_require_products_not_just_health() -> None:
    cases = default_cases_for_phase(
        "p4", title="商城/团购", goal="商品列表、下单占位、团长端入口"
    )
    paths = {c["path"] for c in cases}
    assert "/health" in paths
    assert "/api/products" in paths
    assert "/api/orders" in paths


def test_classify_404_is_fail() -> None:
    assert classify_response(404, "{}", {"expect_status": [200]}) == "fail"


def test_classify_empty_products_list_is_pass() -> None:
    body = json.dumps({"items": []})
    case = {
        "expect_status": [200],
        "required_any_keys": ["items", "products"],
        "item_required_keys": ["name", "price"],
    }
    assert classify_response(200, body, case) == "pass"


def test_classify_generic_items_shell_is_placeholder() -> None:
    body = json.dumps(
        {
            "items": [
                {
                    "id": "I-1",
                    "title": "新增条目",
                    "note": "",
                    "created_at": "2026-01-01",
                }
            ]
        }
    )
    case = {
        "expect_status": [200],
        "required_any_keys": ["items", "products"],
        "item_required_keys": ["name", "price"],
        "reject_if_generic_items": True,
        "reject_body_substrings": ["新增条目", "Auto increment"],
    }
    assert classify_response(200, body, case) == "placeholder"


def test_classify_real_product_payload_is_pass() -> None:
    body = json.dumps(
        {"items": [{"id": "p1", "name": "大米", "price": 12.5, "stock": 10}]}
    )
    case = {
        "expect_status": [200],
        "required_any_keys": ["items", "products"],
        "item_required_keys": ["name", "price"],
    }
    assert classify_response(200, body, case) == "pass"


def test_run_acceptance_cases_reports_fail_placeholder_pass() -> None:
    def request(method: str, path: str, **_kw):
        if path == "/health":
            return 200, json.dumps({"ok": True})
        if path == "/api/products":
            return 200, json.dumps({"items": [{"id": "1", "title": "新增条目"}]})
        if path == "/api/orders":
            return 404, ""
        return 404, ""

    cases = default_cases_for_phase("p4", title="商城", goal="商品")
    report = run_acceptance_cases(request, cases)
    by_id = {r.id: r for r in report.results}
    assert by_id["health"].verdict == "pass"
    assert by_id["products-list"].verdict == "placeholder"
    assert by_id["orders-list"].verdict == "fail"
    assert report.passed is False
    md = format_acceptance_report(report)
    assert "完成" in md and "空壳" in md and "失败" in md


def test_write_acceptance_note_emits_json_cases(tmp_path: Path) -> None:
    root = "workspaces/demo"
    (tmp_path / root / "docs").mkdir(parents=True)
    write_phase_acceptance_note(
        tmp_path,
        root,
        phase_id="p4",
        metric_command='python "workspaces/demo/scripts/smoke_check.py"',
        title="商城/团购",
        goal="商品列表、下单",
    )
    cases_path = tmp_path / root / ACCEPTANCE_CASES_REL
    assert cases_path.is_file()
    data = json.loads(cases_path.read_text(encoding="utf-8"))
    assert data["phase_id"] == "p4"
    assert any(c["path"] == "/api/products" for c in data["cases"])
    md = (tmp_path / root / "docs" / "ACCEPTANCE_P4.md").read_text(encoding="utf-8")
    assert "/api/products" in md


def test_smoke_fails_when_acceptance_path_missing(tmp_path: Path) -> None:
    import os
    import subprocess
    import sys

    root = "workspaces/demo"
    api = tmp_path / root / "apps" / "api"
    web = tmp_path / root / "apps" / "web"
    api.mkdir(parents=True)
    web.mkdir(parents=True)
    (api / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n"
        "@app.get('/health')\ndef health():\n    return {'ok': True}\n",
        encoding="utf-8",
    )
    (api / "requirements.txt").write_text("fastapi>=0.110\n", encoding="utf-8")
    (web / "index.html").write_text("<html></html>", encoding="utf-8")
    write_acceptance_cases(
        tmp_path,
        root,
        phase_id="p4",
        title="商城",
        goal="商品",
    )
    write_smoke_script(tmp_path, root)
    env = os.environ.copy()
    env["MAWP_SMOKE_API_INSTALL"] = "0"
    env["MAWP_SMOKE_WEB_BUILD"] = "0"
    env["MAWP_SMOKE_LIVE"] = "1"
    proc = subprocess.run(
        [sys.executable, str(tmp_path / root / "scripts" / "smoke_check.py")],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
        check=False,
    )
    combined = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode != 0
    assert "ACCEPTANCE" in combined
    assert "/api/products" in combined
