# -*- coding: utf-8 -*-
"""默认前端脚手架：深蓝侧栏后台壳 + Civic Trust 内容区（门户卡片 / 业务页）。

生成链路（Studio / 高级项目 / frontend stub / debug repair）统一走这里，
避免再产出灰底白卡 + 底部裸链接。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

THEME_FILENAME = "theme.css"
SHELL_CSS_FILENAME = "shell.css"
SHELL_JS_FILENAME = "shell.js"
PORTAL_START = "<!-- MAWP_PORTAL_CARDS -->"
PORTAL_END = "<!-- /MAWP_PORTAL_CARDS -->"
NAV_START = "/* MAWP_NAV_START */"
NAV_END = "/* MAWP_NAV_END */"

THEME_CSS = """\
/* Civic Trust · MAWP 内容区皮肤。Frontend Agent 必须复用本文件，禁止另起紫白脚手架。 */
:root {
  --navy: #1b4f9c;
  --navy-deep: #143a74;
  --teal: #0d9488;
  --ink: #1a2332;
  --muted: #5b6b7c;
  --line: #dce3ee;
  --card: #ffffff;
  --bg0: #eef3f9;
  --bg1: #f7f9fc;
  --danger: #b91c1c;
  --ok: #047857;
  --shadow: 0 12px 32px rgba(20, 58, 116, 0.08);
  --radius: 16px;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  color: var(--ink);
  font-family: "PingFang SC", "Microsoft YaHei", "Segoe UI", system-ui, sans-serif;
  background:
    radial-gradient(ellipse 80% 50% at 10% -10%, rgba(13, 148, 136, 0.12), transparent 50%),
    radial-gradient(ellipse 70% 40% at 90% 0%, rgba(27, 79, 156, 0.14), transparent 45%),
    linear-gradient(180deg, var(--bg0) 0%, var(--bg1) 55%, #eef2f7 100%);
}
.page { position: relative; max-width: 1080px; margin: 0 auto; padding: 28px 20px 48px; }
.topbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }
.brand { display: flex; align-items: center; gap: 12px; text-decoration: none; color: inherit; }
.logo {
  width: 42px; height: 42px; border-radius: 12px; flex-shrink: 0;
  background: linear-gradient(145deg, var(--navy) 0%, var(--teal) 100%);
  display: grid; place-items: center;
  box-shadow: 0 8px 20px rgba(27, 79, 156, 0.28);
  color: #fff; font-weight: 700; font-size: 16px;
}
.brand-text .name { font-size: 18px; font-weight: 700; line-height: 1.2; }
.brand-text .hint { font-size: 12px; color: var(--muted); margin-top: 2px; }
.badge {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 12px; border-radius: 999px;
  background: rgba(255,255,255,0.85); border: 1px solid var(--line);
  font-size: 12px; color: var(--navy); font-weight: 600;
}
.badge::before {
  content: ""; width: 7px; height: 7px; border-radius: 50%;
  background: var(--teal); box-shadow: 0 0 0 3px rgba(13, 148, 136, 0.25);
}
#mawp-nav { display: flex; flex-wrap: wrap; gap: 6px; }
.nav-link {
  text-decoration: none; color: var(--navy-deep); font-size: 13px; font-weight: 600;
  padding: 6px 10px; border-radius: 8px; border: 1px solid transparent;
}
.nav-link:hover { background: #fff; border-color: var(--line); }
.hero, .panel, .card {
  background: var(--card); border: 1px solid var(--line); border-radius: 20px;
  box-shadow: var(--shadow);
}
.hero { padding: 28px 28px 24px; margin-bottom: 24px; }
.hero h1, .app-main h1 { margin: 0 0 10px; font-size: clamp(22px, 3vw, 30px); letter-spacing: -0.02em; }
.lead, .muted { color: var(--muted); font-size: 14px; line-height: 1.7; }
.section { margin-bottom: 22px; }
.section-head { display: flex; align-items: baseline; gap: 12px; margin-bottom: 12px; }
.section-head h2 { margin: 0; font-size: 14px; font-weight: 700; color: var(--navy-deep); }
.section-head .line { flex: 1; height: 1px; background: linear-gradient(90deg, var(--line), transparent); }
.grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
@media (max-width: 720px) { .grid { grid-template-columns: 1fr; } .hero { padding: 22px 18px; } }
a.card {
  --accent: var(--navy);
  display: flex; gap: 14px; align-items: flex-start;
  padding: 16px 14px 16px 0; text-decoration: none; color: inherit;
  border-radius: var(--radius); transition: transform .18s ease, box-shadow .18s ease;
  position: relative; overflow: hidden;
}
a.card::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px; background: var(--accent); }
a.card:hover { transform: translateY(-3px); box-shadow: 0 14px 28px rgba(20, 58, 116, 0.1); }
a.card.tone-ops { --accent: #1b4f9c; }
a.card.tone-life { --accent: #0d9488; }
a.card.tone-ai { --accent: #1d4ed8; }
a.card.tone-dev { --accent: #475569; }
.icon {
  width: 44px; height: 44px; margin-left: 16px; border-radius: 12px; flex-shrink: 0;
  display: grid; place-items: center;
  background: color-mix(in srgb, var(--accent) 12%, white); color: var(--accent); font-weight: 700;
}
.body { flex: 1; min-width: 0; }
.title-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 6px; }
.title-row .t { font-size: 15px; font-weight: 700; }
.tag {
  font-size: 11px; font-weight: 650; padding: 2px 8px; border-radius: 999px;
  background: color-mix(in srgb, var(--accent) 12%, white); color: var(--accent);
}
.d { margin: 0; font-size: 13px; line-height: 1.65; color: var(--muted); }
.arrow { align-self: center; margin-right: 14px; color: #a8b4c4; }
a.card:hover .arrow { color: var(--accent); }
.app-main { display: grid; gap: 16px; }
.panel { padding: 20px 22px; }
label { display: block; font-size: 12px; color: var(--muted); }
input, textarea, select, button {
  font-family: inherit; font-size: 14px;
}
input, textarea, select {
  width: 100%; margin: 6px 0 12px; padding: 10px 12px;
  border: 1px solid #d0d5dd; border-radius: 10px; background: #fff;
}
.btn, button {
  background: var(--navy); color: #fff; border: 0; border-radius: 10px;
  padding: 10px 16px; cursor: pointer; font-weight: 600;
}
button.secondary { background: #eef3f9; color: var(--navy-deep); }
.row { display: flex; gap: 8px; flex-wrap: wrap; }
.log, pre#out {
  background: #0f172a; color: #e2e8f0; border-radius: 12px; padding: 14px;
  font-size: 12px; overflow: auto; white-space: pre-wrap;
}
.order { border-top: 1px solid #eef2f6; padding: 10px 0; font-size: 13px; }
.foot {
  margin-top: 20px; padding: 14px 18px; border-radius: 12px;
  background: rgba(255,255,255,0.72); border: 1px solid var(--line);
  font-size: 12px; color: #8a97a8;
  display: flex; flex-wrap: wrap; gap: 8px 20px; justify-content: space-between;
}
.mawp-extra-link {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  margin: 12px 0; padding: 14px 16px; border-radius: 14px;
  background: #fff; border: 1px solid var(--line); text-decoration: none; color: var(--ink);
  box-shadow: 0 4px 14px rgba(26, 35, 50, 0.04);
}
.mawp-extra-link strong { color: var(--navy); }
@media (prefers-reduced-motion: reduce) {
  a.card, a.card:hover { transition: none; transform: none; }
}
"""

SHELL_CSS = """\
/* MAWP Admin Shell · 深蓝侧栏 + 白顶栏。内容区继续复用 theme.css。 */
:root {
  --side: #0f2744;
  --side-2: #143454;
  --accent: #2f6fed;
  --ink: #1f2329;
  --muted: #667085;
  --line: #ebeef2;
  --bg: #f4f6f8;
  --card: #fff;
}

html, body {
  margin: 0;
  height: 100%;
  color: var(--ink);
  font-family: "PingFang SC", "Microsoft YaHei", "Segoe UI", system-ui, sans-serif;
  background: var(--bg);
}

.mawp-app {
  min-height: 100%;
  display: grid;
  grid-template-columns: 220px 1fr;
}

.mawp-side {
  background: linear-gradient(180deg, #0c223c 0%, var(--side) 55%, #0b1c33 100%);
  color: #d7e3f4;
  padding: 18px 12px 28px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.mawp-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px 14px;
  color: #fff;
  text-decoration: none;
  border-bottom: 1px solid rgba(255,255,255,.08);
}

.mawp-logo {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: linear-gradient(145deg, #2f6fed, #0d9488);
  display: grid;
  place-items: center;
  font-weight: 700;
  font-size: 14px;
}

.mawp-brand b { display: block; font-size: 14px; line-height: 1.2; }
.mawp-brand small { display: block; font-size: 11px; color: #8aa0bc; margin-top: 2px; font-weight: 400; }

.mawp-nav { display: flex; flex-direction: column; gap: 4px; }

.mawp-nav a {
  color: #c5d4e8;
  text-decoration: none;
  font-size: 14px;
  padding: 10px 12px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.mawp-nav a:hover { background: rgba(255,255,255,.06); color: #fff; }

.mawp-nav a.active {
  background: var(--accent);
  color: #fff;
  font-weight: 600;
}

.mawp-stage { min-width: 0; display: flex; flex-direction: column; min-height: 100vh; }

.mawp-top {
  height: 48px;
  background: #fff;
  border-bottom: 1px solid var(--line);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  font-size: 14px;
  color: #344054;
}

.mawp-top .muted { color: var(--muted); font-size: 12px; }

.mawp-main {
  padding: 28px 32px 40px;
  max-width: 1080px;
}

.mawp-main > h1 {
  margin: 0 0 22px;
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.mawp-main .hero { margin-top: 0; }

@media (max-width: 840px) {
  .mawp-app { grid-template-columns: 1fr; }
  .mawp-side { flex-direction: row; flex-wrap: wrap; padding: 10px; }
  .mawp-brand { border: 0; padding: 6px 8px; }
  .mawp-nav { flex-direction: row; flex-wrap: wrap; }
  .mawp-main { padding: 20px 16px 32px; }
}
"""

SHELL_JS_BOOT = """\
(function () {
  function mount() {
    if (document.querySelector(".mawp-app")) return;
    var brand = document.body.getAttribute("data-brand") || "业务后台";
    var hint = document.body.getAttribute("data-brand-hint") || "运营后台";
    var logo = document.body.getAttribute("data-logo") || (brand.charAt(0) || "业");
    var page = document.body.getAttribute("data-page") || "overview";
    var NAV = window.MAWP_NAV || [];
    var app = document.createElement("div");
    app.className = "mawp-app";
    var navHtml = NAV.map(function (item) {
      var cls = item.id === page ? "active" : "";
      var extra = item.ext ? ' target="_blank" rel="noreferrer"' : "";
      return '<a class="' + cls + '" href="' + item.href + '"' + extra + ">" + item.label + "</a>";
    }).join("");
    var side = document.createElement("aside");
    side.className = "mawp-side";
    side.innerHTML =
      '<a class="mawp-brand" href="./index.html">' +
      '<span class="mawp-logo">' + logo + "</span>" +
      "<div><b>" + brand + "</b><small>" + hint + "</small></div></a>" +
      '<nav class="mawp-nav">' + navHtml + "</nav>";
    var stage = document.createElement("div");
    stage.className = "mawp-stage";
    var top = document.createElement("header");
    top.className = "mawp-top";
    top.innerHTML =
      "<span>" + brand + " · " + hint + "</span>" +
      '<span class="muted">本地演示 · API :8001</span>';
    var main = document.createElement("div");
    main.className = "mawp-main";
    var nodes = Array.prototype.slice.call(document.body.childNodes);
    nodes.forEach(function (node) {
      if (node === app) return;
      if (node.nodeType === 1 && (node.tagName === "SCRIPT" || node.classList.contains("mawp-app"))) return;
      main.appendChild(node);
    });
    stage.appendChild(top);
    stage.appendChild(main);
    app.appendChild(side);
    app.appendChild(stage);
    document.body.insertBefore(app, document.body.firstChild);
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
"""

HEALTH_PROBE_JS = """\
const API = localStorage.getItem('ADV_API') || 'http://127.0.0.1:8001';
document.getElementById('btn').onclick = async () => {
  const out = document.getElementById('out');
  try {
    const r = await fetch(API + '/health');
    out.textContent = JSON.stringify(await r.json(), null, 2);
  } catch (e) {
    out.textContent = 'API 未启动: ' + e;
  }
};
"""


@dataclass(frozen=True)
class PortalCard:
    title: str
    href: str
    desc: str = ""
    tag: str = ""
    tone: str = "ops"


def brand_mark(title: str) -> str:
    text = (title or "业").strip()
    return text[0] if text else "业"


def default_nav_items() -> list[dict[str, Any]]:
    return [
        {"id": "overview", "href": "./index.html", "label": "总览"},
        {
            "id": "docs",
            "href": "http://127.0.0.1:8001/docs",
            "label": "API 文档",
            "ext": True,
        },
    ]


def page_id_from_href(href: str) -> str:
    name = href.replace("\\", "/").rsplit("/", 1)[-1]
    stem = name.replace(".html", "").strip() or "page"
    if stem in {"index", ""}:
        return "overview"
    return stem


def parse_nav_items(js: str) -> list[dict[str, Any]] | None:
    start = js.find(NAV_START)
    end = js.find(NAV_END)
    if start == -1 or end == -1 or end <= start:
        return None
    block = js[start + len(NAV_START) : end]
    match = re.search(r"window\.MAWP_NAV\s*=\s*(\[.*\])\s*;", block, re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list):
        return None
    return [item for item in data if isinstance(item, dict)]


def render_shell_js(items: list[dict[str, Any]] | None = None) -> str:
    nav = items if items is not None else default_nav_items()
    payload = json.dumps(nav, ensure_ascii=False, indent=2)
    return (
        "/* MAWP 后台壳：按 data-page / data-brand 注入侧栏 */\n"
        f"{NAV_START}\n"
        f"window.MAWP_NAV = {payload};\n"
        f"{NAV_END}\n"
        f"{SHELL_JS_BOOT}"
    )


def append_shell_nav(
    js: str,
    href: str,
    label: str,
    page_id: str | None = None,
) -> str:
    items = parse_nav_items(js)
    if items is None:
        items = default_nav_items()
        js = render_shell_js(items)
    if any(str(item.get("href") or "") == href for item in items):
        return js if parse_nav_items(js) is not None else render_shell_js(items)
    entry = {
        "id": page_id or page_id_from_href(href),
        "href": href,
        "label": label,
    }
    docs_idx = next(
        (
            i
            for i, item in enumerate(items)
            if item.get("ext") or item.get("id") == "docs"
        ),
        None,
    )
    if docs_idx is None:
        items.append(entry)
    else:
        items.insert(docs_idx, entry)
    return render_shell_js(items)


def write_theme_css(web_dir: Path) -> Path:
    """写入 theme.css，并确保侧栏壳 shell.css / shell.js 存在。"""
    web_dir.mkdir(parents=True, exist_ok=True)
    path = web_dir / THEME_FILENAME
    path.write_text(THEME_CSS, encoding="utf-8")
    (web_dir / SHELL_CSS_FILENAME).write_text(SHELL_CSS, encoding="utf-8")
    js_path = web_dir / SHELL_JS_FILENAME
    if js_path.is_file():
        existing = parse_nav_items(js_path.read_text(encoding="utf-8"))
        js_path.write_text(render_shell_js(existing or default_nav_items()), encoding="utf-8")
    else:
        js_path.write_text(render_shell_js(), encoding="utf-8")
    return path


def web_asset_files(frontend_dir: str) -> list[dict[str, str]]:
    root = frontend_dir.replace("\\", "/").rstrip("/")
    return [
        {"path": f"{root}/{THEME_FILENAME}", "content": THEME_CSS},
        {"path": f"{root}/{SHELL_CSS_FILENAME}", "content": SHELL_CSS},
        {"path": f"{root}/{SHELL_JS_FILENAME}", "content": render_shell_js()},
    ]


def render_card(card: PortalCard) -> str:
    tag = (
        f'<span class="tag">{escape(card.tag)}</span>' if card.tag else ""
    )
    mark = escape((card.title[:1] or "·"))
    ext = "↗" if card.href.startswith("http") else "→"
    return (
        f'<a class="card tone-{escape(card.tone)}" href="{escape(card.href, quote=True)}">'
        f'<div class="icon" aria-hidden="true">{mark}</div>'
        f'<div class="body"><div class="title-row">'
        f'<span class="t">{escape(card.title)}</span>{tag}</div>'
        f'<p class="d">{escape(card.desc)}</p></div>'
        f'<span class="arrow" aria-hidden="true">{ext}</span></a>'
    )


def _shell(
    *,
    title: str,
    hint: str,
    badge: str,
    inner: str,
    nav_html: str = "",
    script_src: str | None = "./app.js",
    extra_head: str = "",
    page_id: str = "overview",
    brand: str = "",
    brand_hint: str = "",
) -> str:
    title_e = escape(title)
    brand_text = brand or title
    hint_text = brand_hint or hint
    brand_e = escape(brand_text)
    hint_e = escape(hint_text)
    badge_e = escape(badge)
    logo_e = escape(brand_mark(brand_text))
    page_e = escape(page_id or "overview")
    nav = (
        f'<nav id="mawp-nav" aria-label="模块">{nav_html}</nav>'
        if nav_html
        else '<nav id="mawp-nav" aria-label="模块" hidden></nav>'
    )
    script = (
        f'<script src="{escape(script_src, quote=True)}"></script>' if script_src else ""
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title_e}</title>
  <link rel="stylesheet" href="./{THEME_FILENAME}" />
  <link rel="stylesheet" href="./{SHELL_CSS_FILENAME}" />
  {extra_head}
</head>
<body data-page="{page_e}" data-brand="{brand_e}" data-brand-hint="{hint_e}" data-logo="{logo_e}">
  {nav}
  {inner}
  <footer class="foot">
    <span>{title_e} · 本地演示</span>
    <span>后端 127.0.0.1:8001 · 前端 :5175</span>
    <span class="badge">{badge_e}</span>
  </footer>
  <script src="./{SHELL_JS_FILENAME}"></script>
  {script}
</body>
</html>
"""


def portal_html(
    *,
    title: str,
    subtitle: str = "业务演示入口",
    lead: str = "",
    badge: str = "演示版",
    hint: str = "智慧社区 · 物业运营 · 居民服务",
    cards: list[PortalCard] | None = None,
    extra_html: str = "",
    script_src: str | None = "./app.js",
) -> str:
    card_html = "".join(render_card(c) for c in (cards or []))
    lead_html = f'<p class="lead">{escape(lead)}</p>' if lead else ""
    inner = f"""
    <section class="hero">
      <h1>{escape(subtitle)}</h1>
      {lead_html}
    </section>
    <section class="section">
      <div class="section-head"><h2>功能入口</h2><div class="line"></div></div>
      <div class="grid" id="portal-grid">
        {PORTAL_START}
        {card_html}
        {PORTAL_END}
      </div>
    </section>
    {extra_html}
    """
    return _shell(
        title=title,
        hint=hint,
        badge=badge,
        inner=inner,
        script_src=script_src,
        page_id="overview",
        brand=title,
        brand_hint=hint,
    )


def app_page_html(
    *,
    title: str,
    heading: str,
    body_html: str,
    badge: str = "演示版",
    hint: str = "运营后台",
    nav_links: list[tuple[str, str]] | None = None,
    script_src: str | None = None,
    page_id: str = "",
    brand: str = "",
    brand_hint: str = "",
) -> str:
    nav = "".join(
        f'<a class="nav-link" href="{escape(href, quote=True)}">{escape(label)}</a>'
        for href, label in (nav_links or [("./index.html", "首页")])
    )
    inner = f"""
    <main class="app-main">
      <section class="hero"><h1>{escape(heading)}</h1></section>
      {body_html}
    </main>
    """
    brand_text = brand or title.split("·")[0].strip() or title
    return _shell(
        title=title,
        hint=hint,
        badge=badge,
        inner=inner,
        nav_html=nav,
        script_src=script_src,
        page_id=page_id or "page",
        brand=brand_text,
        brand_hint=brand_hint or hint,
    )


def placeholder_portal_html(title: str, message: str, badge: str = "待生成") -> str:
    return portal_html(
        title=title,
        subtitle="一站式业务演示入口",
        lead=message,
        badge=badge,
        extra_html=f'<section class="panel" id="root"><p class="muted">{escape(message)}</p></section>',
        script_src="./app.js",
    )


def health_probe_html(title: str) -> str:
    extra = """
    <section class="panel">
      <h2>联调探测</h2>
      <p class="muted">调用后端 GET /health，确认 API 已启动。</p>
      <p><button type="button" class="btn" id="btn">探测 API</button></p>
      <pre id="out">…</pre>
    </section>
    """
    return portal_html(
        title=title,
        subtitle="本地联调入口",
        lead="侧栏后台壳已接入，内容区可在此探测后端健康状态。",
        badge="联调",
        extra_html=extra,
        script_src="./app.js",
    )


def repair_note_html(title: str, note: str) -> str:
    body = (
        f'<section class="panel" id="app">'
        f"<h2>{escape(title)}</h2>"
        f'<p class="muted">{escape(note)}</p>'
        f"</section>"
    )
    return app_page_html(
        title=title,
        heading=title,
        body_html=body,
        badge="已修复",
        script_src="./app.js",
        page_id="overview",
        brand=title,
    )


def append_nav_link(
    html: str,
    href: str,
    label: str,
    desc: str = "",
    *,
    tag: str = "",
    tone: str = "life",
) -> str:
    """把增量入口加进门户卡片或顶栏，避免底部裸 <a>。"""
    if href in html and label in html:
        return html
    card = PortalCard(title=label, href=href, desc=desc or label, tag=tag, tone=tone)
    snippet = render_card(card)
    if PORTAL_END in html:
        return html.replace(PORTAL_END, snippet + "\n        " + PORTAL_END, 1)
    nav_mark = 'id="mawp-nav"'
    idx = html.find(nav_mark)
    if idx != -1:
        close = html.find("</nav>", idx)
        if close != -1:
            link = (
                f'<a class="nav-link" href="{escape(href, quote=True)}">'
                f"{escape(label)}</a>"
            )
            return html[:close] + link + html[close:]
    extra = (
        f'<a class="mawp-extra-link" href="{escape(href, quote=True)}">'
        f"<span><strong>{escape(label)}</strong>"
        f'<span class="muted"> · {escape(desc or "打开模块")}</span></span>'
        f"<span>→</span></a>\n"
    )
    if "</body>" in html:
        return html.replace("</body>", extra + "</body>", 1)
    return html + extra


def link_web_module(
    web_dir: Path,
    href: str,
    label: str,
    desc: str = "",
    *,
    tag: str = "",
    tone: str = "life",
    page_id: str | None = None,
) -> bool:
    """首页功能卡片 + 侧栏 NAV 同步增加入口。"""
    web_dir.mkdir(parents=True, exist_ok=True)
    write_theme_css(web_dir)
    changed = False
    index = web_dir / "index.html"
    if index.is_file():
        html = index.read_text(encoding="utf-8")
        updated = append_nav_link(
            html, href, label, desc, tag=tag, tone=tone
        )
        if updated != html:
            index.write_text(updated, encoding="utf-8")
            changed = True
    js_path = web_dir / SHELL_JS_FILENAME
    js = js_path.read_text(encoding="utf-8") if js_path.is_file() else render_shell_js()
    new_js = append_shell_nav(js, href, label, page_id=page_id)
    if new_js != js:
        js_path.write_text(new_js, encoding="utf-8")
        changed = True
    return changed
