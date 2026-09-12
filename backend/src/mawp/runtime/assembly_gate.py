"""coding 后的确定性装配门禁：扫描 router / 前端页，补入口，不新增节点。

挂路由、补导航是规则活：缺 include_router 或入口链接就补上；
冒烟再扫一遍，漏挂 / 漏链则直接 fail。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_ROUTER_ASSIGN = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*APIRouter\s*\(",
    re.MULTILINE,
)
_PKG_IMPORT = re.compile(r"^(from\s+routers\s+import\s+)(.+)$", re.MULTILINE)

_SKIP_ROOT_STEMS = ("seed", "model", "test")
_SKIP_ROOT_FILES = {"main.py", "conftest.py"}


@dataclass(frozen=True)
class UnmountedRouter:
    rel_path: str
    module: str
    stem: str
    symbol: str


@dataclass
class AssemblyReport:
    scanned: int = 0
    mounted: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    linked_pages: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scanned": self.scanned,
            "mounted": list(self.mounted),
            "skipped": list(self.skipped),
            "linked_pages": list(self.linked_pages),
            "errors": list(self.errors),
        }


def detect_router_symbol(text: str) -> str | None:
    """文件里第一个 `name = APIRouter(` 赋值；没有则看是否出现 APIRouter(。"""
    m = _ROUTER_ASSIGN.search(text or "")
    if m:
        return m.group(1)
    if "APIRouter(" in (text or ""):
        return "router"
    return None


def is_router_mounted(main_text: str, *, module: str, stem: str) -> bool:
    """main.py 是否已经 import / include 了该 router 模块。"""
    text = main_text or ""
    if re.search(
        rf"include_router\s*\([^)]*\b{re.escape(stem)}\b",
        text,
    ):
        return True
    if re.search(rf"from\s+{re.escape(module)}\s+import\b", text):
        return True
    if re.search(
        rf"from\s+routers\s+import\s+[^\n]*\b{re.escape(stem)}\b",
        text,
    ):
        return True
    return False


def prefers_package_import(main_text: str) -> bool:
    return bool(_PKG_IMPORT.search(main_text or ""))


def merge_package_import(text: str, stem: str) -> str:
    """把 stem 并入已有的 `from routers import a, b` 行。"""
    m = _PKG_IMPORT.search(text or "")
    if not m:
        return text
    names = [
        n.strip()
        for n in m.group(2).replace("(", "").replace(")", "").split(",")
        if n.strip()
    ]
    if stem in names:
        return text
    names.append(stem)
    return text[: m.start(2)] + ", ".join(names) + text[m.end(2) :]


def _skip_root_py(name: str) -> bool:
    if name.startswith("_") or name in _SKIP_ROOT_FILES:
        return True
    stem = name[:-3] if name.endswith(".py") else name
    return any(stem.startswith(p) for p in _SKIP_ROOT_STEMS)


def iter_router_files(api_dir: Path) -> list[Path]:
    """routers/ 下的模块 + API 根目录含 APIRouter 的 module_*.py 等。"""
    found: list[Path] = []
    routers_dir = api_dir / "routers"
    if routers_dir.is_dir():
        for path in routers_dir.rglob("*.py"):
            if not path.name.startswith("_"):
                found.append(path)
    for path in api_dir.glob("*.py"):
        if _skip_root_py(path.name):
            continue
        found.append(path)
    uniq: dict[str, Path] = {}
    for path in found:
        uniq[path.resolve().as_posix()] = path
    return sorted(uniq.values(), key=lambda p: p.as_posix())


def find_unmounted_routers(api_dir: Path) -> list[UnmountedRouter]:
    """扫描含 APIRouter 的模块，返回 main.py 尚未挂载的。"""
    main_py = api_dir / "main.py"
    if not main_py.is_file():
        return []
    main_text = main_py.read_text(encoding="utf-8", errors="ignore")
    found: list[UnmountedRouter] = []
    for path in iter_router_files(api_dir):
        body = path.read_text(encoding="utf-8", errors="ignore")
        symbol = detect_router_symbol(body)
        if not symbol:
            continue
        rel = path.relative_to(api_dir).as_posix()
        module = rel[:-3].replace("/", ".")
        stem = path.stem
        if is_router_mounted(main_text, module=module, stem=stem):
            continue
        found.append(
            UnmountedRouter(
                rel_path=rel,
                module=module,
                stem=stem,
                symbol=symbol,
            )
        )
    return found


def assemble_api_routers(api_dir: Path) -> AssemblyReport:
    """把未挂载的 router 写入 main.py。已存在则跳过。"""
    report = AssemblyReport()
    main_py = api_dir / "main.py"
    if not main_py.is_file():
        report.errors.append("apps/api/main.py missing")
        return report
    missing = find_unmounted_routers(api_dir)
    report.scanned = _count_router_modules(api_dir)
    if not missing:
        return report
    txt = main_py.read_text(encoding="utf-8")
    if "FastAPI" not in txt or not re.search(r"\bapp\s*=", txt):
        report.errors.append("apps/api/main.py has no FastAPI app to mount onto")
        return report
    prefer_pkg = prefers_package_import(txt)
    if not txt.endswith("\n"):
        txt += "\n"
    for item in missing:
        nxt, did = _append_mount(txt, item, prefer_pkg=prefer_pkg)
        if not did:
            report.skipped.append(item.rel_path)
            continue
        txt = nxt
        report.mounted.append(item.rel_path)
    if report.mounted:
        main_py.write_text(txt, encoding="utf-8")
    return report


def _append_mount(
    txt: str,
    item: UnmountedRouter,
    *,
    prefer_pkg: bool,
) -> tuple[str, bool]:
    is_pkg_mod = item.module.startswith("routers.") and item.module.count(".") == 1
    if prefer_pkg and is_pkg_mod and item.symbol == "router":
        include_stmt = f"app.include_router({item.stem}.router)"
        if include_stmt in txt:
            return txt, False
        txt = merge_package_import(txt, item.stem)
        if not txt.endswith("\n"):
            txt += "\n"
        txt += f"{include_stmt}\n"
        return txt, True

    alias = f"{item.stem}_router"
    import_stmt = f"from {item.module} import {item.symbol} as {alias}"
    include_stmt = f"app.include_router({alias})"
    if include_stmt in txt:
        return txt, False
    if import_stmt not in txt:
        txt += f"\n{import_stmt}\n"
    else:
        txt += "\n"
    txt += f"{include_stmt}\n"
    return txt, True


def page_label(stem: str) -> str:
    known = {
        "ai": "AI 助手",
        "admin": "运营后台",
        "billing": "缴费中心",
        "bills": "账单",
        "repair": "在线报修",
        "repairs": "在线报修",
    }
    return known.get(stem.lower(), stem.replace("_", " ").replace("-", " "))


def find_unlinked_pages(web_dir: Path) -> list[Path]:
    index = web_dir / "index.html"
    if not index.is_file():
        return []
    html = index.read_text(encoding="utf-8", errors="ignore")
    orphans: list[Path] = []
    for path in sorted(web_dir.glob("*.html")):
        if path.name.lower() == "index.html":
            continue
        if path.name in html or f"./{path.name}" in html:
            continue
        orphans.append(path)
    return orphans


def assemble_web_pages(web_dir: Path, report: AssemblyReport) -> None:
    """把未出现在 index.html 的业务页补进门户卡片 / 导航。"""
    if not web_dir.is_dir():
        return
    orphans = find_unlinked_pages(web_dir)
    if not orphans:
        return
    from mawp.runtime.web_scaffold import link_web_module

    for path in orphans:
        href = f"./{path.name}"
        link_web_module(
            web_dir,
            href,
            page_label(path.stem),
            desc=f"打开 {path.stem}",
        )
        report.linked_pages.append(path.name)


def assemble_project(workspace: Path, project_root: str) -> AssemblyReport:
    """对 {project_root}/apps/api 与 apps/web 执行装配。"""
    root = str(project_root or "").replace("\\", "/").rstrip("/")
    if not root:
        report = AssemblyReport()
        report.errors.append("project_root empty")
        return report
    api_dir = workspace / root / "apps" / "api"
    web_dir = workspace / root / "apps" / "web"
    if api_dir.is_dir():
        report = assemble_api_routers(api_dir)
    else:
        report = AssemblyReport()
        report.errors.append(f"{root}/apps/api missing")
    assemble_web_pages(web_dir, report)
    return report


def _count_router_modules(api_dir: Path) -> int:
    n = 0
    for path in iter_router_files(api_dir):
        body = path.read_text(encoding="utf-8", errors="ignore")
        if detect_router_symbol(body):
            n += 1
    return n
