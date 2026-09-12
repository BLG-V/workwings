"""Admin Shell + Civic Trust 前端脚手架：门户、侧栏导航、生成提示词。"""

from __future__ import annotations

from pathlib import Path

from mawp.advanced import (
    AdvancedProject,
    generate_phase_billing,
    generate_phase_mvp_repair,
)
from mawp.runtime.deliver_specs import build_deliver_specs
from mawp.runtime.web_scaffold import (
    PORTAL_END,
    PortalCard,
    append_nav_link,
    health_probe_html,
    link_web_module,
    placeholder_portal_html,
    portal_html,
    write_theme_css,
)


def test_portal_html_has_civic_markers() -> None:
    html = portal_html(
        title="邻智云",
        subtitle="社区治理入口",
        lead="按业务域进入模块",
        cards=[PortalCard("缴费中心", "./bills.html", "模拟支付", tag="P2", tone="life")],
    )
    assert 'href="./theme.css"' in html
    assert 'href="./shell.css"' in html
    assert 'src="./shell.js"' in html
    assert 'data-page="overview"' in html
    assert 'data-brand="邻智云"' in html
    assert PORTAL_END in html
    assert "缴费中心" in html
    assert "bills.html" in html
    assert "功能入口" in html
    assert "#1b4f9c" not in html  # tokens live in theme.css


def test_append_nav_link_inserts_portal_card() -> None:
    html = portal_html(title="Demo", cards=[])
    updated = append_nav_link(html, "./billing.html", "缴费", desc="账单与支付", tag="P2")
    assert updated.count("./billing.html") == 1
    assert '<p><a href="./billing.html">' not in updated
    assert PORTAL_END in updated
    assert "缴费" in updated.split(PORTAL_END)[0]


def test_append_nav_link_fallback_is_not_naked_anchor() -> None:
    html = "<html><body><h1>old</h1></body></html>"
    updated = append_nav_link(html, "./admin.html", "运营后台")
    assert "admin.html" in updated
    assert '<p><a href="./admin.html">' not in updated
    assert "mawp-extra-link" in updated


def test_placeholder_and_probe_are_not_scaffold_cards() -> None:
    placeholder = placeholder_portal_html("Studio 项目", "点击生成以写入业务")
    probe = health_probe_html("报修MVP")
    for html in (placeholder, probe):
        assert "theme.css" in html
        assert "shell.css" in html
        assert "max-width:720px" not in html.replace(" ", "")
        assert 'id="btn"' in probe or html is placeholder
    assert 'id="btn"' in probe
    assert 'id="out"' in probe


def test_write_theme_css(tmp_path: Path) -> None:
    web = tmp_path / "web"
    path = write_theme_css(web)
    css = path.read_text(encoding="utf-8")
    assert "--navy: #1b4f9c" in css
    assert "--teal: #0d9488" in css
    assert "PingFang SC" in css
    shell_css = (web / "shell.css").read_text(encoding="utf-8")
    shell_js = (web / "shell.js").read_text(encoding="utf-8")
    assert ".mawp-side" in shell_css
    assert "window.MAWP_NAV" in shell_js
    assert "./index.html" in shell_js


def test_link_web_module_updates_portal_and_shell_nav(tmp_path: Path) -> None:
    web = tmp_path / "web"
    web.mkdir()
    write_theme_css(web)
    (web / "index.html").write_text(portal_html(title="Demo", cards=[]), encoding="utf-8")
    changed = link_web_module(
        web, "./billing.html", "缴费中心", "账单", tag="P2", page_id="billing"
    )
    assert changed is True
    index = (web / "index.html").read_text(encoding="utf-8")
    js = (web / "shell.js").read_text(encoding="utf-8")
    assert "billing.html" in index
    assert '"id": "billing"' in js
    assert "./billing.html" in js
    # docs 仍在末尾
    assert js.rfind("billing.html") < js.rfind("API 文档")


def test_frontend_and_requirement_prompts_require_civic() -> None:
    specs = {s.name: s for s in build_deliver_specs()}
    fe = specs["frontend"].system_prompt
    req = specs["requirement"].system_prompt
    assert "theme.css" in fe
    assert "shell.css" in fe
    assert "shell.js" in fe
    assert "Civic Trust" in fe or "深蓝" in fe
    assert "裸" in fe
    assert "浅色卡片" in req
    assert "禁止" in req
    assert "侧栏" in req


def test_phase_increment_uses_theme_and_nav(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    project = AdvancedProject(
        id="t1",
        title="邻智云测",
        source_filename="s.md",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        workspace=str(ws),
    )
    generate_phase_mvp_repair(ws, project)
    generate_phase_billing(ws, project)
    web = ws / "apps" / "web"
    theme = web / "theme.css"
    index = (web / "index.html").read_text(encoding="utf-8")
    billing = (web / "billing.html").read_text(encoding="utf-8")
    shell_js = (web / "shell.js").read_text(encoding="utf-8")
    assert theme.is_file()
    assert (web / "shell.css").is_file()
    assert (web / "repair.html").is_file()
    assert "billing.html" in index
    assert "repair.html" in index
    assert "功能入口" in index
    assert '<p><a href="./billing.html">' not in index
    assert "theme.css" in billing
    assert "shell.css" in billing
    assert 'data-page="billing"' in billing
    assert "./billing.html" in shell_js
    assert "./repair.html" in shell_js
    assert "--navy: #1b4f9c" in theme.read_text(encoding="utf-8")
