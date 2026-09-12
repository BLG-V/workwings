"""高级项目：DOCX 解析、里程碑拆分、工程脚手架。"""

from __future__ import annotations

import json
import re
import time
import zipfile
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4
from xml.etree import ElementTree as ET

from mawp.advanced.phase_outcome import (
    detect_placeholder_output,
    is_retryable_failure,
    phase_subtasks,
    resolve_phase_outcome,
    run_deliver_with_retry,
    validate_phase_against_spec,
)
from mawp.runtime.web_scaffold import (
    PortalCard,
    app_page_html,
    link_web_module,
    placeholder_portal_html,
    portal_html,
    write_theme_css,
)

PHASE_RETRY_SLEEP = time.sleep
# 瞬时失败只试 1 次（不整期连跑 3 遍）；需要重跑请点「生成当前期」
PHASE_RETRY_ATTEMPTS = 1
# Deliver 轮询默认 12 分钟；可用 MAWP_DELIVER_POLL_SECONDS 覆盖
DEFAULT_DELIVER_POLL_SECONDS = 720
_TERMINAL_PHASE_STATUSES = frozenset({"done", "partial", "failed"})

W_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def extract_docx_text(data: bytes) -> str:
    """从 docx 二进制提取纯文本（不依赖 python-docx）。"""
    with zipfile.ZipFile(__import__("io").BytesIO(data)) as zf:
        xml = zf.read("word/document.xml")
    root = ET.fromstring(xml)
    parts: list[str] = []
    for node in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"):
        if node.text:
            parts.append(node.text)
        if node.tail:
            parts.append(node.tail)
    text = "".join(parts)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_plaintext(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".docx"):
        return extract_docx_text(data)
    if name.endswith((".md", ".txt", ".markdown")):
        return data.decode("utf-8", errors="ignore").strip()
    # 其它二进制先尝试 utf-8
    try:
        return data.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise ValueError(f"暂不支持的文件类型: {filename}") from exc


DEFAULT_PHASES_SMART_COMMUNITY = [
    {
        "id": "p1",
        "title": "MVP · 业主报修闭环",
        "goal": "登录占位 + 报修提交 + 物业接单列表；Web 前端 + FastAPI 骨架可本地启动",
        "deliverables": ["apps/web 报修页", "apps/api 报修接口", "README 启动说明"],
        "depends_on": [],
        "status": "pending",
    },
    {
        "id": "p2",
        "title": "缴费与消息通知",
        "goal": "账单列表、模拟支付、欠费提醒接口与页面",
        "deliverables": ["账单 API", "缴费页", "通知占位"],
        "depends_on": ["p1"],
        "status": "pending",
    },
    {
        "id": "p3",
        "title": "物业运营后台",
        "goal": "角色权限、小区档案、工单管理后台",
        "deliverables": ["后台布局", "工单管理", "租户字段预留"],
        "depends_on": ["p1"],
        "status": "pending",
    },
    {
        "id": "p4",
        "title": "商城/团购最小闭环",
        "goal": "商品列表、下单占位、团长端入口",
        "deliverables": ["商品 API", "下单页"],
        "depends_on": ["p2"],
        "status": "pending",
    },
    {
        "id": "p5",
        "title": "AI 能力接入位",
        "goal": "客服问答与识图报修的适配层（可接百炼/万相）",
        "deliverables": ["AI gateway", "报修识图占位", "配置说明"],
        "depends_on": ["p1"],
        "status": "pending",
    },
]


def plan_phases(srs_text: str, title: str = "") -> list[dict[str, Any]]:
    """根据 SRS 文本拆里程碑；识别到社区/物业特征时用邻智云默认分期。"""
    text = srs_text or ""
    lower = text.lower()
    community_hints = [
        "物业",
        "报修",
        "业主",
        "小区",
        "租户",
        "邻智",
        "社区",
        "团购",
        "维修",
    ]
    hits = sum(1 for h in community_hints if h in text)
    if hits >= 3 or "多租户" in text or "saas" in lower:
        phases = json.loads(json.dumps(DEFAULT_PHASES_SMART_COMMUNITY))
        if title:
            phases[0]["goal"] = f"围绕「{title}」：{phases[0]['goal']}"
        return phases

    # 通用启发式：按「第x章/模块」切，否则给 4 期标准研发分期
    chapters = re.findall(
        r"(?:第[一二三四五六七八九十\d]+[章节]|^\d+\.\d*\s*[^\n]{4,40})",
        text,
        flags=re.M,
    )
    if len(chapters) >= 4:
        phases = []
        for i, ch in enumerate(chapters[:6]):
            phases.append(
                {
                    "id": f"p{i + 1}",
                    "title": ch.strip()[:40],
                    "goal": f"依据规格章节「{ch.strip()[:40]}」实现可运行增量",
                    "deliverables": ["docs 对齐说明", "对应模块代码"],
                    "depends_on": [f"p{i}"] if i > 0 else [],
                    "status": "pending",
                }
            )
        return phases

    return [
        {
            "id": "p1",
            "title": "需求澄清与领域模型",
            "goal": "输出领域对象、用例与数据库草案",
            "deliverables": ["domain.md", "schema.sql"],
            "depends_on": [],
            "status": "pending",
        },
        {
            "id": "p2",
            "title": "API 与最小前端",
            "goal": "核心用例 API + 可操作页面",
            "deliverables": ["apps/api", "apps/web"],
            "depends_on": ["p1"],
            "status": "pending",
        },
        {
            "id": "p3",
            "title": "权限与多角色",
            "goal": "登录占位、角色路由、基础鉴权",
            "deliverables": ["auth 模块", "角色页"],
            "depends_on": ["p2"],
            "status": "pending",
        },
        {
            "id": "p4",
            "title": "联调、测试与交付说明",
            "goal": "测试用例、启动脚本、演示剧本",
            "deliverables": ["tests", "DEMO.md"],
            "depends_on": ["p3"],
            "status": "pending",
        },
    ]


@dataclass
class AdvancedProject:
    id: str
    title: str
    source_filename: str
    created_at: str
    updated_at: str
    workspace: str
    phases: list[dict[str, Any]] = field(default_factory=list)
    srs_chars: int = 0
    current_phase_id: str | None = None
    status: str = "draft"  # draft | generating | ready | failed
    gap_summary: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AdvancedProject:
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


class AdvancedProjectStore:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.projects_dir = self.root / "workspaces"
        self.meta_dir = self.root / ".mawp" / "advanced_projects"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.meta_dir.mkdir(parents=True, exist_ok=True)

    def _meta_path(self, project_id: str) -> Path:
        return self.meta_dir / f"{project_id}.json"

    def save(self, project: AdvancedProject) -> None:
        project.updated_at = utc_now()
        self._meta_path(project.id).write_text(
            json.dumps(project.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load(self, project_id: str) -> AdvancedProject | None:
        path = self._meta_path(project_id)
        if not path.is_file():
            return None
        return AdvancedProject.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list_projects(self, limit: int = 40) -> list[AdvancedProject]:
        files = sorted(self.meta_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        out: list[AdvancedProject] = []
        for f in files[:limit]:
            try:
                out.append(AdvancedProject.from_dict(json.loads(f.read_text(encoding="utf-8"))))
            except (OSError, json.JSONDecodeError, TypeError):
                continue
        return out


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def scaffold_project(
    store: AdvancedProjectStore,
    *,
    title: str,
    srs_text: str,
    source_filename: str,
    phases: list[dict[str, Any]] | None = None,
) -> AdvancedProject:
    project_id = f"ap-{uuid4().hex[:10]}"
    workspace = store.projects_dir / project_id
    workspace.mkdir(parents=True, exist_ok=True)

    phase_list = phases or plan_phases(srs_text, title=title)
    now = utc_now()
    project = AdvancedProject(
        id=project_id,
        title=title or "未命名高级项目",
        source_filename=source_filename,
        created_at=now,
        updated_at=now,
        workspace=str(workspace),
        phases=phase_list,
        srs_chars=len(srs_text),
        current_phase_id=phase_list[0]["id"] if phase_list else None,
        status="draft",
    )

    _write(workspace / "docs" / "SRS.md", f"# {project.title}\n\n{srs_text}\n")
    _write(
        workspace / "docs" / "phases.json",
        json.dumps(phase_list, ensure_ascii=False, indent=2),
    )
    _write(
        workspace / "README.md",
        f"""# {project.title}

> 由智流 MAWP「高级项目」模式生成 · 分期交付

## 启动（第 1 期骨架）

```bash
# API
cd apps/api
pip install -r requirements.txt
uvicorn main:app --reload --port 8001

# Web
cd apps/web
npm install
npm run dev
```

## 里程碑

见 `docs/phases.json`。请按期生成，不要期望一次生成整套多端系统。

源文件：`{source_filename}`
""",
    )

    # 最小 API / Web 占位，后续 generate_phase 会充实
    _write(
        workspace / "apps" / "api" / "requirements.txt",
        "fastapi>=0.115.0\nuvicorn[standard]>=0.30.0\npydantic>=2.0\n",
    )
    _write(
        workspace / "apps" / "api" / "main.py",
        '''"""高级项目 API 骨架 — 生成第 1 期后会写入业务路由。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Advanced Project API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok", "service": "advanced-project-api"}
''',
    )
    write_theme_css(workspace / "apps" / "web")
    _write(
        workspace / "apps" / "web" / "index.html",
        placeholder_portal_html(
            project.title,
            "点击平台「生成当前期」以写入报修闭环页面。",
            badge="待生成第 1 期",
        ),
    )
    _write(
        workspace / "apps" / "web" / "app.js",
        "// 第 1 期生成后替换为报修闭环逻辑\nconsole.log('advanced project web placeholder');\n",
    )
    _write(
        workspace / "apps" / "web" / "package.json",
        json.dumps(
            {
                "name": "advanced-web",
                "private": True,
                "type": "module",
                "scripts": {
                    "dev": "npx --yes serve -l 5175 .",
                    "build": "echo 'Static site - no build required'",
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
    )

    try:
        from mawp.runtime.project_deliver import (
            default_metric_command,
            write_phase_acceptance_note,
            write_smoke_script,
        )
        from mawp.runtime.deploy_scaffolder import scaffold_deploy_files
        from mawp.runtime.cicd_scaffolder import scaffold_cicd

        rel_root = f"workspaces/{project_id}"
        # store.root 即平台 workspace；脚手架目录在 workspaces/<id>
        write_smoke_script(store.root, rel_root)
        write_phase_acceptance_note(
            store.root,
            rel_root,
            phase_id=phase_list[0]["id"] if phase_list else "p1",
            metric_command=default_metric_command(rel_root),
        )
        # 生成部署脚手架
        try:
            scaffold_deploy_files(
                workspace,
                project_id=project_id,
                goal=title,
                has_frontend=True,
                has_backend=True,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] 部署脚手架生成失败: {exc}")
        # 生成 CI/CD 流水线
        try:
            scaffold_cicd(workspace, platform="github")
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] CI/CD 生成失败: {exc}")
    except OSError:
        pass

    store.save(project)
    return project


def _ensure_api_package(workspace: Path) -> Path:
    api_dir = workspace / "apps" / "api"
    api_dir.mkdir(parents=True, exist_ok=True)
    routers = api_dir / "routers"
    routers.mkdir(parents=True, exist_ok=True)
    init = routers / "__init__.py"
    if not init.is_file():
        init.write_text('"""API routers package."""\n', encoding="utf-8")
    return api_dir


def _ensure_fastapi_main(workspace: Path, title: str) -> Path:
    """确保存在可增量挂载的 FastAPI main，绝不无空壳覆盖已有路由实现。"""
    api_dir = _ensure_api_package(workspace)
    main = api_dir / "main.py"
    if main.is_file():
        txt = main.read_text(encoding="utf-8")
        if "FastAPI" in txt and re.search(r"\bapp\s*=", txt):
            return main
    _write(
        main,
        f'''"""{title} API"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="{title} API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {{"status": "ok", "service": "{title}"}}
''',
    )
    return main


def _mount_router(
    workspace: Path,
    *,
    title: str,
    import_stmt: str,
    include_stmt: str,
) -> str | None:
    """在 main.py 末尾挂载路由；已存在则跳过。返回相对路径或 None。"""
    main = _ensure_fastapi_main(workspace, title)
    txt = main.read_text(encoding="utf-8")
    if include_stmt in txt:
        return None
    if not txt.endswith("\n"):
        txt += "\n"
    if import_stmt not in txt:
        txt += f"\n{import_stmt}\n"
    txt += f"{include_stmt}\n"
    _write(main, txt)
    return "apps/api/main.py"


def generate_phase_mvp_repair(workspace: Path, project: AdvancedProject) -> list[str]:
    """生成第 1 期：业主报修闭环（可运行骨架）。已有可运行 main 时改为增量挂载。"""
    written: list[str] = []
    title = project.title
    api_dir = _ensure_api_package(workspace)
    main = api_dir / "main.py"
    has_live_api = False
    if main.is_file():
        txt = main.read_text(encoding="utf-8")
        has_live_api = "FastAPI" in txt and (
            "/api/repairs" in txt or "include_router" in txt or "routers" in txt
        )

    if has_live_api:
        # 已有工程：只补报修路由文件并挂载，禁止整文件覆盖
        repairs = api_dir / "routers" / "repairs.py"
        if not repairs.is_file():
            _write(
                repairs,
                '''"""报修路由（增量）。"""
from datetime import datetime
from uuid import uuid4
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/repairs", tags=["repairs"])
ORDERS: list[dict] = []


class RepairCreate(BaseModel):
    title: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=2, max_length=2000)
    location: str = "未填写"


@router.get("")
def list_orders():
    return {"items": ORDERS}


@router.post("")
def create_order(body: RepairCreate):
    row = {
        "id": f"R-{uuid4().hex[:8]}",
        "title": body.title,
        "description": body.description,
        "location": body.location,
        "status": "submitted",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    ORDERS.insert(0, row)
    return row


@router.post("/{order_id}/accept")
def accept_order(order_id: str):
    for o in ORDERS:
        if o["id"] == order_id:
            o["status"] = "accepted"
            return o
    raise HTTPException(404, "not found")
''',
            )
            written.append("apps/api/routers/repairs.py")
        mounted = _mount_router(
            workspace,
            title=title,
            import_stmt="from routers.repairs import router as repairs_router",
            include_stmt="app.include_router(repairs_router)",
        )
        if mounted:
            written.append(mounted)
        return written

    api_main = workspace / "apps" / "api" / "main.py"
    api_code = '''"""__TITLE__ · 第 1 期 API：报修闭环"""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="__TITLE__ API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

Status = Literal["submitted", "accepted", "scheduled", "done"]


class RepairCreate(BaseModel):
    title: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=2, max_length=2000)
    location: str = "未填写"
    contact: str = ""


class RepairOrder(RepairCreate):
    id: str
    status: Status = "submitted"
    created_at: str
    tenant_id: str = "demo-tenant"
    community_id: str = "demo-community"


ORDERS: list[RepairOrder] = []


@app.get("/health")
def health():
    return {"status": "ok", "phase": "p1-repair", "orders": len(ORDERS)}


@app.get("/api/repairs")
def list_repairs():
    return {"items": [o.model_dump() for o in ORDERS]}


@app.post("/api/repairs")
def create_repair(body: RepairCreate):
    order = RepairOrder(
        id=f"R-{uuid4().hex[:8]}",
        title=body.title,
        description=body.description,
        location=body.location,
        contact=body.contact,
        created_at=datetime.now().isoformat(timespec="seconds"),
    )
    ORDERS.insert(0, order)
    return order.model_dump()


@app.post("/api/repairs/{order_id}/accept")
def accept_repair(order_id: str):
    for o in ORDERS:
        if o.id == order_id:
            o.status = "accepted"
            return o.model_dump()
    raise HTTPException(404, "工单不存在")
'''
    _write(api_main, api_code.replace("__TITLE__", title))
    written.append(str(api_main.relative_to(workspace)))

    web_dir = workspace / "apps" / "web"
    write_theme_css(web_dir)
    _write(
        web_dir / "repair.html",
        app_page_html(
            title=f"{title} · 报修",
            heading=f"{title} · 第1期报修闭环",
            hint="运营后台",
            badge="P1",
            nav_links=[("./index.html", "总览"), ("./repair.html", "业主报修")],
            script_src="./app.js",
            page_id="repair",
            brand=title,
            brand_hint="运营后台",
            body_html="""
      <section class="panel">
        <h2>业主报修</h2>
        <label>标题</label>
        <input id="title" placeholder="例如：楼道灯不亮" />
        <label>位置</label>
        <input id="location" placeholder="例如：3号楼 2单元" />
        <label>联系方式</label>
        <input id="contact" placeholder="手机号" />
        <label>描述</label>
        <textarea id="desc" rows="4" placeholder="现象、可否上门时间…"></textarea>
        <div class="row">
          <button type="button" id="submit">提交报修</button>
          <button type="button" class="secondary" id="refresh">刷新工单</button>
        </div>
        <p class="muted" id="msg"></p>
      </section>
      <section class="panel">
        <h2>物业接单台</h2>
        <div id="list" class="muted">加载中…</div>
      </section>
            """,
        ),
    )
    written.append("apps/web/repair.html")
    _write(
        web_dir / "index.html",
        portal_html(
            title=title,
            subtitle=f"{title} · 业务总览",
            lead="从侧栏或下方卡片进入本期已交付模块。",
            badge="P1",
            hint="运营后台",
            cards=[
                PortalCard(
                    title="业主报修",
                    href="./repair.html",
                    desc="提交报修、物业接单",
                    tag="P1",
                    tone="ops",
                )
            ],
            script_src=None,
        ),
    )
    written.append("apps/web/index.html")
    link_web_module(
        web_dir,
        "./repair.html",
        "业主报修",
        desc="提交报修、物业接单",
        tag="P1",
        tone="ops",
        page_id="repair",
    )

    web_js = workspace / "apps" / "web" / "app.js"
    _write(
        web_js,
        """const API = localStorage.getItem('ADV_API') || 'http://127.0.0.1:8001';

async function loadList() {
  const box = document.getElementById('list');
  try {
    const res = await fetch(API + '/api/repairs');
    const data = await res.json();
    const items = data.items || [];
    if (!items.length) {
      box.innerHTML = '暂无工单';
      return;
    }
    box.innerHTML = items.map((o) => `
      <div class="order">
        <div><strong>${o.title}</strong> <span class="tag">${o.status}</span></div>
        <div class="muted">${o.location || ''} · ${o.created_at || ''} · ${o.id}</div>
        <div>${o.description || ''}</div>
        ${o.status === 'submitted' ? `<button data-id="${o.id}" class="accept">接单</button>` : ''}
      </div>
    `).join('');
    box.querySelectorAll('.accept').forEach((btn) => {
      btn.onclick = async () => {
        await fetch(API + '/api/repairs/' + btn.dataset.id + '/accept', { method: 'POST' });
        loadList();
      };
    });
  } catch (e) {
    box.innerHTML = '无法连接 API（请先启动 apps/api 的 uvicorn :8001）';
  }
}

document.getElementById('submit').onclick = async () => {
  const title = document.getElementById('title').value.trim();
  const description = document.getElementById('desc').value.trim();
  const location = document.getElementById('location').value.trim();
  const contact = document.getElementById('contact').value.trim();
  const msg = document.getElementById('msg');
  if (!title || !description) {
    msg.textContent = '请填写标题和描述';
    return;
  }
  try {
    await fetch(API + '/api/repairs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, description, location, contact }),
    });
    msg.textContent = '报修已提交';
    document.getElementById('title').value = '';
    document.getElementById('desc').value = '';
    loadList();
  } catch (e) {
    msg.textContent = '提交失败，请确认 API 已启动';
  }
};

document.getElementById('refresh').onclick = loadList;
loadList();
""",
    )
    written.append(str(web_js.relative_to(workspace)))

    _write(
        workspace / "docs" / "PHASE1.md",
        f"""# 第 1 期完成说明 · {title}

## 已生成

- `apps/api/main.py`：报修创建 / 列表 / 接单
- `apps/web/`：侧栏总览 + 业主报修表单 / 物业接单台

## 启动

```bash
cd apps/api && pip install -r requirements.txt && uvicorn main:app --reload --port 8001
cd apps/web && npx --yes serve -l 5175 .
```

浏览器打开 Web 地址，提交一条报修并在列表中「接单」。

## 对照 SRS

覆盖：报事报修主路径（提交 → 接单）。缴费、商城、多端小程序等见后续里程碑。
""",
    )
    written.append("docs/PHASE1.md")
    return written


def generate_phase_billing(workspace: Path, project: AdvancedProject) -> list[str]:
    """第 2 期：账单 / 模拟支付 —— 增量挂载，不覆盖既有 main.py。"""
    written: list[str] = []
    title = project.title
    api_dir = _ensure_api_package(workspace)
    bills = api_dir / "routers" / "bills.py"
    _write(
        bills,
        '''"""缴费账单路由（增量，不替换其它业务路由）。"""
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["bills"])


class Bill(BaseModel):
    id: str
    title: str
    amount: float
    status: str = "unpaid"
    due_at: str = ""


BILLS: list[Bill] = [
    Bill(id="B-1001", title="物业费 2026-08", amount=286.5, due_at="2026-08-31"),
    Bill(id="B-1002", title="停车费 2026-08", amount=150.0, due_at="2026-08-31"),
]


@router.get("/api/bills")
def list_bills():
    return {"items": [b.model_dump() for b in BILLS]}


@router.post("/api/bills/{bill_id}/pay")
def pay_bill(bill_id: str):
    for b in BILLS:
        if b.id == bill_id:
            b.status = "paid"
            return {
                "ok": True,
                "bill": b.model_dump(),
                "paid_at": datetime.now().isoformat(timespec="seconds"),
            }
    raise HTTPException(404, "账单不存在")
''',
    )
    written.append("apps/api/routers/bills.py")
    notes = api_dir / "routers" / "notifications.py"
    if not notes.is_file():
        _write(
            notes,
            '''"""欠费提醒占位。"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
def list_notes():
    return {"items": [{"id": "N-1", "title": "物业费将到期", "level": "warn"}]}
''',
        )
        written.append("apps/api/routers/notifications.py")

    for imp, inc in (
        ("from routers.bills import router as bills_router", "app.include_router(bills_router)"),
        (
            "from routers.notifications import router as notifications_router",
            "app.include_router(notifications_router)",
        ),
    ):
        mounted = _mount_router(workspace, title=title, import_stmt=imp, include_stmt=inc)
        if mounted:
            written.append(mounted)

    web = workspace / "apps" / "web"
    web.mkdir(parents=True, exist_ok=True)
    write_theme_css(web)
    _write(
        web / "billing.html",
        app_page_html(
            title=f"{title} · 缴费",
            heading=f"{title} · 第2期缴费",
            badge="P2",
            nav_links=[("./index.html", "总览"), ("./billing.html", "缴费")],
            page_id="billing",
            brand=title,
            brand_hint="运营后台",
            body_html="""
      <section class="panel">
        <h2>账单列表</h2>
        <div id="list">加载中…</div>
      </section>
      <script>
const API = localStorage.getItem('ADV_API') || 'http://127.0.0.1:8001';
async function load() {
  const box = document.getElementById('list');
  try {
    const data = await (await fetch(API + '/api/bills')).json();
    box.innerHTML = (data.items||[]).map(b => `<div>${b.title} · ¥${b.amount} · ${b.status}
      ${b.status==='unpaid'?`<button data-id="${b.id}">模拟支付</button>`:''}</div>`).join('') || '暂无';
    box.querySelectorAll('button[data-id]').forEach(btn => {
      btn.onclick = async () => {
        await fetch(API + '/api/bills/' + btn.dataset.id + '/pay', {method:'POST'});
        load();
      };
    });
  } catch(e) { box.textContent = '请先启动 API :8001'; }
}
load();
      </script>
            """,
        ),
    )
    written.append("apps/web/billing.html")
    if link_web_module(
        web,
        "./billing.html",
        "缴费中心",
        desc="账单列表与模拟支付",
        tag="P2",
        tone="life",
        page_id="billing",
    ):
        written.append("apps/web/index.html")
    _write(
        workspace / "docs" / "PHASE2.md",
        f"# 第 2 期 · 缴费 · {title}\n\n- `/api/bills`\n- `/api/notifications`\n- `apps/web/billing.html`\n\n增量挂载，不覆盖既有路由。\n",
    )
    written.append("docs/PHASE2.md")
    return written


def generate_phase_admin(workspace: Path, project: AdvancedProject) -> list[str]:
    """第 3 期：运营后台 —— 增量挂载，不覆盖既有 main.py。"""
    written: list[str] = []
    title = project.title
    api_dir = _ensure_api_package(workspace)
    _write(
        api_dir / "routers" / "admin.py",
        '''"""物业运营后台路由（增量）。"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/admin", tags=["admin"])
TICKETS = [
    {"id": "T-1", "title": "楼道灯", "status": "open", "assignee": "未分配"},
    {"id": "T-2", "title": "门禁", "status": "doing", "assignee": "张工"},
]


@router.get("/overview")
def overview():
    return {
        "communities": 1,
        "open_tickets": sum(1 for t in TICKETS if t["status"] == "open"),
        "roles": ["owner", "staff", "admin"],
    }


@router.get("/tickets")
def tickets():
    return {"items": TICKETS}
''',
    )
    written.append("apps/api/routers/admin.py")
    mounted = _mount_router(
        workspace,
        title=title,
        import_stmt="from routers.admin import router as admin_router",
        include_stmt="app.include_router(admin_router)",
    )
    if mounted:
        written.append(mounted)

    web = workspace / "apps" / "web"
    web.mkdir(parents=True, exist_ok=True)
    write_theme_css(web)
    _write(
        web / "admin.html",
        app_page_html(
            title=f"{title} · 后台",
            heading=f"{title} · 物业运营后台（第3期）",
            badge="P3",
            nav_links=[
                ("./index.html", "总览"),
                ("./billing.html", "缴费"),
                ("./admin.html", "后台"),
            ],
            page_id="admin",
            brand=title,
            brand_hint="运营后台",
            body_html="""
  <section class="panel" id="overview">加载概览…</section>
  <section class="panel" id="tickets">加载工单…</section>
<script>
const API = localStorage.getItem('ADV_API') || 'http://127.0.0.1:8001';
(async () => {
  try {
    const o = await (await fetch(API + '/api/admin/overview')).json();
    document.getElementById('overview').innerHTML =
      `<h3>概览</h3><div>小区 ${o.communities} · 待处理 ${o.open_tickets}</div>`;
    const t = await (await fetch(API + '/api/admin/tickets')).json();
    document.getElementById('tickets').innerHTML = '<h3>工单</h3>' +
      (t.items||[]).map(x => `<div>${x.id} · ${x.title} · ${x.status}</div>`).join('');
  } catch (e) {
    document.getElementById('overview').textContent = '请先启动 API :8001';
  }
})();
</script>
            """,
        ),
    )
    written.append("apps/web/admin.html")
    if link_web_module(
        web,
        "./admin.html",
        "运营后台",
        "权限、档案与工单管理",
        tag="P3",
        tone="ops",
        page_id="admin",
    ):
        written.append("apps/web/index.html")
    _write(
        workspace / "docs" / "PHASE3.md",
        f"# 第 3 期 · 运营后台 · {title}\n\n- `/api/admin/overview`\n- `/api/admin/tickets`\n- `apps/web/admin.html`\n\n增量挂载，不覆盖报修/缴费路由。\n",
    )
    written.append("docs/PHASE3.md")
    return written


def generate_phase_generic_increment(
    workspace: Path,
    project: AdvancedProject,
    phase: dict[str, Any],
) -> list[str]:
    """通用里程碑：写入可运行增量模块 + 页面，避免只落空文档。"""
    written: list[str] = []
    phase_id = str(phase.get("id") or "px")
    title = project.title
    goal = str(phase.get("goal") or phase.get("title") or phase_id)
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", phase_id).strip("-") or "phase"
    module_name = f"module_{slug.replace('-', '_')}"

    api = workspace / "apps" / "api" / "main.py"
    # 追加路由文件，保持 main 可 import
    mod_path = workspace / "apps" / "api" / f"{module_name}.py"
    _write(
        mod_path,
        f'''"""Auto increment for {phase_id}: {goal[:60]}"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/{slug}", tags=["{phase_id}"])
ITEMS: list[dict] = []


class ItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    note: str = ""


@router.get("/health")
def module_health():
    return {{"phase": "{phase_id}", "items": len(ITEMS), "goal": {goal!r}}}


@router.get("/items")
def list_items():
    return {{"items": ITEMS}}


@router.post("/items")
def create_item(body: ItemCreate):
    row = {{
        "id": f"I-{{uuid4().hex[:8]}}",
        "title": body.title,
        "note": body.note,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }}
    ITEMS.insert(0, row)
    return row
''',
    )
    written.append(str(mod_path.relative_to(workspace)))

    main_txt = api.read_text(encoding="utf-8") if api.is_file() else ""
    import_line = f"from {module_name} import router as {module_name}_router"
    include_line = f"app.include_router({module_name}_router)"
    if include_line not in main_txt:
        mounted = _mount_router(
            workspace,
            title=title,
            import_stmt=import_line,
            include_stmt=include_line,
        )
        if mounted:
            written.append(mounted)

    page = workspace / "apps" / "web" / f"{slug}.html"
    write_theme_css(workspace / "apps" / "web")
    phase_title = str(phase.get("title") or phase_id)
    _write(
        page,
        app_page_html(
            title=f"{title} · {phase_id}",
            heading=phase_title,
            badge=phase_id.upper(),
            brand=title,
            page_id=slug,
            nav_links=[("./index.html", "首页"), (f"./{slug}.html", phase_title)],
            body_html=f"""
      <section class="panel">
        <p class="muted">{goal}</p>
        <input id="title" placeholder="标题"/>
        <p><button type="button" id="add">新增条目</button></p>
        <pre id="out">…</pre>
      </section>
<script>
const API = localStorage.getItem('ADV_API') || 'http://127.0.0.1:8001';
const base = API + '/api/{slug}';
async function refresh() {{
  try {{
    const data = await (await fetch(base + '/items')).json();
    document.getElementById('out').textContent = JSON.stringify(data, null, 2);
  }} catch (e) {{
    document.getElementById('out').textContent = 'API 未启动';
  }}
}}
document.getElementById('add').onclick = async () => {{
  const title = document.getElementById('title').value.trim() || '未命名';
  await fetch(base + '/items', {{
    method: 'POST', headers: {{'Content-Type':'application/json'}},
    body: JSON.stringify({{ title, note: '{phase_id}' }})
  }});
  refresh();
}};
refresh();
</script>
            """,
        ),
    )
    written.append(str(page.relative_to(workspace)))

    if link_web_module(
        workspace / "apps" / "web",
        f"./{slug}.html",
        phase_title,
        goal[:80],
        tag=phase_id.upper(),
        tone="life",
        page_id=slug,
    ):
        written.append("apps/web/index.html")

    note = workspace / "docs" / f"PHASE_{phase_id.upper()}.md"
    _write(
        note,
        f"""# {phase.get('title') or phase_id}

目标：{goal}

## 已写入

- `apps/api/{module_name}.py` → `/api/{slug}/items`
- `apps/web/{slug}.html`

请启动 API 后打开增量页验证。
""",
    )
    written.append(str(note.relative_to(workspace)))
    return written


def generate_phase_mall(workspace: Path, project: AdvancedProject) -> list[str]:
    """第 4 期：商品列表 / 下单占位 / 团长入口 —— SQLite + 租户隔离，避免内存壳。"""
    written: list[str] = []
    title = project.title
    api_dir = _ensure_api_package(workspace)
    from mawp.runtime.data_layer_gate import DB_SCAFFOLD

    db_py = api_dir / "db.py"
    if not db_py.is_file():
        db_py.write_text(DB_SCAFFOLD, encoding="utf-8")
        (api_dir / "data").mkdir(parents=True, exist_ok=True)
        written.append("apps/api/db.py")
    _write(
        api_dir / "models_mall.py",
        '''"""商城数据模型（多租户）。"""
from __future__ import annotations

from pydantic import BaseModel


class Product(BaseModel):
    id: str
    tenant_id: str = "demo-tenant"
    community_id: str = "demo-community"
    name: str
    price: float
    stock: int = 0
    group_buy: bool = True


class MallOrder(BaseModel):
    id: str
    tenant_id: str = "demo-tenant"
    community_id: str = "demo-community"
    product_id: str
    product_name: str
    quantity: int = 1
    amount: float = 0.0
    captain_id: str = "C-1"
    status: str = "placed"
    created_at: str = ""


class Captain(BaseModel):
    id: str
    tenant_id: str = "demo-tenant"
    community_id: str = "demo-community"
    name: str
    building: str = ""
    orders: int = 0
''',
    )
    written.append("apps/api/models_mall.py")
    _write(
        api_dir / "routers" / "mall.py",
        '''"""商城 / 团购路由（SQLite + 租户隔离）。"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from db import get_conn

router = APIRouter(tags=["mall"])

DEFAULT_TENANT = "demo-tenant"
DEFAULT_COMMUNITY = "demo-community"


def _tenant(
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_community_id: str | None = Header(default=None, alias="X-Community-Id"),
) -> tuple[str, str]:
    return (x_tenant_id or DEFAULT_TENANT, x_community_id or DEFAULT_COMMUNITY)


def _ensure_mall_schema() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                community_id TEXT NOT NULL,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                stock INTEGER NOT NULL DEFAULT 0,
                group_buy INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS mall_orders (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                community_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                product_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                amount REAL NOT NULL,
                captain_id TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS captains (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                community_id TEXT NOT NULL,
                name TEXT NOT NULL,
                building TEXT NOT NULL,
                orders INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_products_tenant
                ON products(tenant_id, community_id);
            CREATE INDEX IF NOT EXISTS idx_orders_tenant
                ON mall_orders(tenant_id, community_id);
            """
        )
        conn.commit()
        n = conn.execute(
            "SELECT COUNT(*) AS c FROM products WHERE tenant_id=? AND community_id=?",
            (DEFAULT_TENANT, DEFAULT_COMMUNITY),
        ).fetchone()["c"]
        if int(n) == 0:
            conn.executemany(
                "INSERT INTO products(id, tenant_id, community_id, name, price, stock, group_buy) "
                "VALUES (?,?,?,?,?,?,1)",
                [
                    ("P-1001", DEFAULT_TENANT, DEFAULT_COMMUNITY, "社区鲜奶", 12.8, 40),
                    ("P-1002", DEFAULT_TENANT, DEFAULT_COMMUNITY, "时令蔬菜包", 19.9, 25),
                ],
            )
            conn.execute(
                "INSERT INTO captains(id, tenant_id, community_id, name, building, orders) "
                "VALUES (?,?,?,?,?,0)",
                ("C-1", DEFAULT_TENANT, DEFAULT_COMMUNITY, "1号楼团长", "1栋"),
            )
            conn.commit()


_ensure_mall_schema()


class OrderCreate(BaseModel):
    product_id: str
    quantity: int = Field(default=1, ge=1, le=99)
    captain_id: str = "C-1"


@router.get("/api/products")
def list_products(
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_community_id: str | None = Header(default=None, alias="X-Community-Id"),
):
    tenant_id, community_id = _tenant(x_tenant_id, x_community_id)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, tenant_id, community_id, name, price, stock, group_buy "
            "FROM products WHERE tenant_id=? AND community_id=?",
            (tenant_id, community_id),
        ).fetchall()
    return {
        "items": [
            {
                "id": r["id"],
                "tenant_id": r["tenant_id"],
                "community_id": r["community_id"],
                "name": r["name"],
                "price": r["price"],
                "stock": r["stock"],
                "group_buy": bool(r["group_buy"]),
            }
            for r in rows
        ]
    }


@router.post("/api/orders")
def create_order(
    body: OrderCreate,
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_community_id: str | None = Header(default=None, alias="X-Community-Id"),
):
    tenant_id, community_id = _tenant(x_tenant_id, x_community_id)
    with get_conn() as conn:
        product = conn.execute(
            "SELECT id, name, price FROM products "
            "WHERE id=? AND tenant_id=? AND community_id=?",
            (body.product_id, tenant_id, community_id),
        ).fetchone()
        if product is None:
            raise HTTPException(status_code=404, detail="商品不存在")
        row = {
            "id": f"O-{uuid4().hex[:8]}",
            "tenant_id": tenant_id,
            "community_id": community_id,
            "product_id": product["id"],
            "product_name": product["name"],
            "quantity": body.quantity,
            "amount": round(float(product["price"]) * body.quantity, 2),
            "captain_id": body.captain_id,
            "status": "placed",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        conn.execute(
            "INSERT INTO mall_orders(id, tenant_id, community_id, product_id, product_name, "
            "quantity, amount, captain_id, status, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                row["id"],
                row["tenant_id"],
                row["community_id"],
                row["product_id"],
                row["product_name"],
                row["quantity"],
                row["amount"],
                row["captain_id"],
                row["status"],
                row["created_at"],
            ),
        )
        conn.commit()
    return row


@router.get("/api/orders")
def list_orders(
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_community_id: str | None = Header(default=None, alias="X-Community-Id"),
):
    tenant_id, community_id = _tenant(x_tenant_id, x_community_id)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM mall_orders WHERE tenant_id=? AND community_id=? "
            "ORDER BY created_at DESC",
            (tenant_id, community_id),
        ).fetchall()
    return {"items": [dict(r) for r in rows]}


@router.get("/api/captains")
def list_captains(
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_community_id: str | None = Header(default=None, alias="X-Community-Id"),
):
    tenant_id, community_id = _tenant(x_tenant_id, x_community_id)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM captains WHERE tenant_id=? AND community_id=?",
            (tenant_id, community_id),
        ).fetchall()
    return {"items": [dict(r) for r in rows]}
''',
    )
    written.append("apps/api/routers/mall.py")
    mounted = _mount_router(
        workspace,
        title=title,
        import_stmt="from routers.mall import router as mall_router",
        include_stmt="app.include_router(mall_router)",
    )
    if mounted:
        written.append(mounted)

    web = workspace / "apps" / "web"
    web.mkdir(parents=True, exist_ok=True)
    write_theme_css(web)
    _write(
        web / "p4.html",
        app_page_html(
            title=f"{title} · 商城团购",
            heading=f"{title} · 商城/团购（第4期）",
            badge="P4",
            brand=title,
            page_id="p4",
            nav_links=[("./index.html", "首页"), ("./p4.html", "商城团购")],
            body_html="""
      <section class="panel">
        <p class="muted">商品列表、下单占位、团长端入口</p>
        <div id="products">加载中…</div>
        <h3>团长入口</h3>
        <pre id="captains">…</pre>
        <h3>最近订单</h3>
        <pre id="orders">…</pre>
      </section>
<script>
const API = localStorage.getItem('ADV_API') || 'http://127.0.0.1:8001';
async function j(path) {
  const r = await fetch(API + path);
  if (!r.ok) throw new Error(path);
  return r.json();
}
async function refresh() {
  try {
    const [products, captains, orders] = await Promise.all([
      j('/api/products'), j('/api/captains'), j('/api/orders')
    ]);
    const box = document.getElementById('products');
    box.innerHTML = (products.items || []).map((p) =>
      '<p><strong>' + p.name + '</strong> ￥' + p.price +
      ' <button type="button" data-id="' + p.id + '">下单</button></p>'
    ).join('') || '暂无商品';
    box.querySelectorAll('button').forEach((btn) => {
      btn.onclick = async () => {
        await fetch(API + '/api/orders', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({ product_id: btn.dataset.id, quantity: 1, captain_id: 'C-1' })
        });
        refresh();
      };
    });
    document.getElementById('captains').textContent = JSON.stringify(captains, null, 2);
    document.getElementById('orders').textContent = JSON.stringify(orders, null, 2);
  } catch (e) {
    document.getElementById('products').textContent = 'API 未启动';
  }
}
refresh();
</script>
            """,
        ),
    )
    written.append("apps/web/p4.html")
    if link_web_module(
        web,
        "./p4.html",
        "商城团购",
        "商品列表、下单占位、团长端入口",
        tag="P4",
        tone="life",
        page_id="p4",
    ):
        written.append("apps/web/index.html")
    _write(
        workspace / "docs" / "PHASE4.md",
        f"# 第 4 期 · 商城/团购 · {title}\n\n- `/api/products`\n- `/api/orders`\n- `/api/captains`\n- `apps/web/p4.html`\n\n增量挂载，不覆盖既有路由。\n",
    )
    written.append("docs/PHASE4.md")
    return written


def generate_phase_fallback(
    workspace: Path,
    project: AdvancedProject,
    phase: dict[str, Any] | None,
    phase_id: str,
) -> list[str]:
    """模板回退：按里程碑写可运行增量，而不是空说明。"""
    phase = phase or {"id": phase_id, "title": phase_id, "goal": ""}
    pid = str(phase.get("id") or phase_id)
    title = (phase.get("title") or "") + (phase.get("goal") or "")
    if pid == "p1":
        return generate_phase_mvp_repair(workspace, project)
    if pid == "p2" or any(k in title for k in ("缴费", "账单", "支付", "通知")):
        return generate_phase_billing(workspace, project)
    if pid == "p3" or any(k in title for k in ("后台", "运营", "工单管理", "权限")):
        return generate_phase_admin(workspace, project)
    if pid == "p4" or any(k in title for k in ("商城", "团购", "商品")):
        return generate_phase_mall(workspace, project)
    return generate_phase_generic_increment(workspace, project, phase)


def _finalize_phase_outcome(
    *,
    workspace: Path,
    phase: dict[str, Any],
    via: str,
    written: list[str],
    testing: dict[str, Any] | None,
) -> dict[str, Any]:
    placeholder = detect_placeholder_output(workspace, written)
    spec_gaps = validate_phase_against_spec(workspace, phase, written)
    outcome = resolve_phase_outcome(
        via=via,
        written=written,
        testing=testing,
        placeholder=placeholder,
        spec_gaps=spec_gaps,
    )
    try:
        from mawp.runtime.gap_report import (
            CapabilityStatus,
            build_gap_report,
            next_tasks_from_report,
            write_gap_artifacts,
        )

        report = build_gap_report(workspace)
        write_gap_artifacts(workspace, report)
        tasks = next_tasks_from_report(report)
        outcome["gap"] = {
            "completed": [i.title for i in report.by_status(CapabilityStatus.DONE)],
            "partial": [i.title for i in report.by_status(CapabilityStatus.PARTIAL)],
            "missing": [i.title for i in report.by_status(CapabilityStatus.MISSING)],
            "next_tasks": tasks[:12],
            "files": [
                "docs/GAP_WITH_SRS.md",
                "docs/NEXT_TASKS.json",
                "docs/gap_report.json",
            ],
        }
        # 全量 SRS 差距仅作可见性；不据此改写本期 status（分期交付下早期期必然缺后续能力）
    except Exception:  # noqa: BLE001
        outcome.setdefault("gap", None)
    return outcome


def _apply_phase_fields(
    p: dict[str, Any],
    *,
    written: list[str],
    via: str,
    outcome: dict[str, Any],
    run_info: dict[str, Any] | None = None,
    testing: Any = None,
    task_runs: Any = None,
    attempts: int = 1,
) -> None:
    p["status"] = outcome["status"]
    p["generated_files"] = written
    p["generated_at"] = utc_now()
    p["via"] = via
    p["degraded"] = bool(outcome.get("degraded"))
    p["attempts"] = attempts
    p["validation"] = {
        "placeholder": bool(outcome.get("placeholder")),
        "spec_gaps": list(outcome.get("spec_gaps") or []),
        "gap": outcome.get("gap"),
    }
    if run_info:
        p["run_id"] = run_info.get("run_id")
    if testing is not None:
        p["testing"] = testing
    if task_runs is not None:
        p["task_runs"] = task_runs


def _project_status_after_phases(phases: list[dict[str, Any]]) -> str:
    pending = [p for p in phases if p.get("status") not in _TERMINAL_PHASE_STATUSES]
    if pending:
        return "ready"
    if any(p.get("status") == "failed" for p in phases):
        return "failed"
    return "ready"


def phase_depends_on(phase: dict[str, Any]) -> list[str]:
    raw = phase.get("depends_on")
    if isinstance(raw, list):
        return [str(x) for x in raw if str(x).strip()]
    return []


def ensure_phase_depends_on(phases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """缺省 depends_on 时按列表顺序串成链，兼容旧项目。"""
    ids = [str(p.get("id") or "") for p in phases]
    for i, phase in enumerate(phases):
        if "depends_on" in phase:
            continue
        phase["depends_on"] = [ids[i - 1]] if i > 0 and ids[i - 1] else []
    return phases


def ready_pending_phases(phases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """依赖已全部真正完成的待生成里程碑（可并行波次）。

    仅 status=done 能解锁下游；partial/failed 不算完成，也不会再被自动波次拾取。
    """
    ensure_phase_depends_on(phases)
    done = {str(p["id"]) for p in phases if p.get("status") == "done"}
    ready: list[dict[str, Any]] = []
    for p in phases:
        if p.get("status") in _TERMINAL_PHASE_STATUSES:
            continue
        deps = phase_depends_on(p)
        if all(d in done for d in deps):
            ready.append(p)
    return ready


def _copy_workspace_for_sandbox(src: Path, dst: Path) -> None:
    import shutil

    if dst.exists():
        shutil.rmtree(dst, ignore_errors=True)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        src,
        dst,
        ignore=shutil.ignore_patterns(
            ".mawp_sandbox",
            "node_modules",
            ".git",
            "__pycache__",
            ".venv",
            "dist",
            "build",
        ),
    )


def _merge_sandbox_files(main: Path, sandbox: Path) -> list[str]:
    """把沙箱中相对主仓新增/变更的文件合并回去。

    对 apps/api/main.py 做保护：沙箱版若会丢掉主仓已有 include_router，则只合并缺失挂载行。
    """
    import shutil

    merged: list[str] = []
    if not sandbox.is_dir():
        return merged
    for path in sandbox.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(sandbox).as_posix()
        if rel.startswith(".mawp_sandbox/") or "/.mawp_sandbox/" in f"/{rel}":
            continue
        if rel.endswith("project.json"):
            continue
        target = main / rel
        if rel.replace("\\", "/") == "apps/api/main.py" and target.is_file():
            old = target.read_text(encoding="utf-8", errors="ignore")
            new = path.read_text(encoding="utf-8", errors="ignore")
            old_includes = {ln.strip() for ln in old.splitlines() if "include_router" in ln}
            new_includes = {ln.strip() for ln in new.splitlines() if "include_router" in ln}
            if old_includes - new_includes:
                # 沙箱 main 丢失既有路由：只把缺失挂载追加到主仓
                append_lines = []
                for ln in new.splitlines():
                    s = ln.strip()
                    if not s:
                        continue
                    if s.startswith("from ") and "import" in s and s not in old:
                        append_lines.append(s)
                    if "include_router" in s and s not in old:
                        append_lines.append(s)
                if append_lines:
                    txt = old if old.endswith("\n") else old + "\n"
                    txt += "\n" + "\n".join(append_lines) + "\n"
                    target.write_text(txt, encoding="utf-8")
                    merged.append(rel)
                continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        merged.append(rel)
    return merged


def generate_phase_by_id(
    store: AdvancedProjectStore,
    project_id: str,
    phase_id: str,
    *,
    config: Any | None = None,
    use_agents: bool = True,
    async_mode: bool = False,
    workspace_override: Path | None = None,
    persist_project: bool = True,
    verify_only: bool = False,
) -> dict[str, Any]:
    """生成指定里程碑；可写入沙箱目录且暂不落库（并行波次用）。"""
    project = store.load(project_id)
    if project is None:
        raise FileNotFoundError(f"项目不存在: {project_id}")

    ensure_phase_depends_on(project.phases)
    phase = next((p for p in project.phases if p["id"] == phase_id), None)
    if phase is None:
        raise ValueError(f"里程碑不存在: {phase_id}")

    workspace = Path(workspace_override) if workspace_override else Path(project.workspace)
    if persist_project:
        project.status = "generating"
        project.current_phase_id = phase_id
        store.save(project)

    # 并行沙箱：临时改写 workspace 路径给 Deliver / 模板
    original_workspace = project.workspace
    project.workspace = str(workspace)

    written: list[str] = []
    run_info: dict[str, Any] | None = None
    via = "template"
    deliver_testing = None
    deliver_task_runs = None
    deliver_changed = None
    last_error: BaseException | None = None
    attempts = 1

    if use_agents and config is not None:
        phase_payload = phase or {"id": phase_id, "title": phase_id, "goal": ""}

        def _call_deliver():
            return run_phase_via_deliver(
                config,
                project=project,
                phase=phase_payload,
                async_mode=async_mode,
                verify_only=verify_only,
            )

        deliver_result, attempts, last_error = run_deliver_with_retry(
            _call_deliver,
            max_attempts=PHASE_RETRY_ATTEMPTS,
            sleep=PHASE_RETRY_SLEEP,
        )
        if deliver_result is not None:
            written = list(deliver_result.get("written") or [])
            run_info = deliver_result.get("run")
            via = "verify" if verify_only else "deliver"
            deliver_testing = deliver_result.get("testing")
            deliver_task_runs = deliver_result.get("task_runs")
            deliver_changed = deliver_result.get("changed_files")
        else:
            via = f"template_fallback:{last_error}"

    allow_fallback = not verify_only
    if last_error is not None and not is_retryable_failure(last_error) and not written:
        allow_fallback = False

    if not written and allow_fallback:
        written = generate_phase_fallback(
            workspace,
            project,
            phase,
            phase_id,
        )
        if via == "deliver":
            via = "deliver+template"
        elif not via.startswith("template"):
            via = "template"

    if verify_only and not written:
        written = list((phase or {}).get("generated_files") or [])

    outcome = _finalize_phase_outcome(
        workspace=workspace,
        phase=phase or {"id": phase_id},
        via=via,
        written=written,
        testing=deliver_testing if isinstance(deliver_testing, dict) else None,
    )

    project.workspace = original_workspace

    if persist_project:
        for p in project.phases:
            if p["id"] == phase_id:
                _apply_phase_fields(
                    p,
                    written=written,
                    via=via,
                    outcome=outcome,
                    run_info=run_info,
                    testing=deliver_testing,
                    task_runs=deliver_task_runs,
                    attempts=attempts,
                )

        pending = [p for p in project.phases if p.get("status") not in _TERMINAL_PHASE_STATUSES]
        ready = ready_pending_phases(project.phases)
        project.current_phase_id = (
            (ready[0]["id"] if ready else None)
            or (pending[0]["id"] if pending else phase_id)
        )
        project.status = _project_status_after_phases(project.phases)
        if isinstance(outcome.get("gap"), dict):
            project.gap_summary = outcome["gap"]
        main_ws = Path(project.workspace)
        _write(
            main_ws / "docs" / "phases.json",
            json.dumps(project.phases, ensure_ascii=False, indent=2),
        )
        store.save(project)

    return {
        "project": project.to_dict() if persist_project else None,
        "phase_id": phase_id,
        "written": written,
        "via": via,
        "status": outcome["status"],
        "outcome": outcome,
        "attempts": attempts,
        "run": run_info,
        "changed_files": list(deliver_changed or written),
        "task_runs": list(deliver_task_runs or []),
        "testing": deliver_testing,
    }


def generate_current_phase(
    store: AdvancedProjectStore,
    project_id: str,
    *,
    config: Any | None = None,
    use_agents: bool = True,
    async_mode: bool = False,
    verify_only: bool = False,
) -> dict[str, Any]:
    project = store.load(project_id)
    if project is None:
        raise FileNotFoundError(f"项目不存在: {project_id}")

    ensure_phase_depends_on(project.phases)
    phase_id = project.current_phase_id or (project.phases[0]["id"] if project.phases else None)
    if not phase_id:
        raise ValueError("没有可生成的里程碑")

    # 若当前期被卡住依赖，跳到第一个就绪期
    ready = ready_pending_phases(project.phases)
    if ready and phase_id not in {p["id"] for p in ready}:
        phase_id = ready[0]["id"]

    return generate_phase_by_id(
        store,
        project_id,
        phase_id,
        config=config,
        use_agents=use_agents,
        async_mode=async_mode,
        verify_only=verify_only,
    )


def generate_remaining_phases(
    store: AdvancedProjectStore,
    project_id: str,
    *,
    config: Any | None = None,
    use_agents: bool = False,
    max_phases: int = 8,
    stop_on_smoke_fail: bool = True,
    parallel_workers: int = 2,
) -> dict[str, Any]:
    """按依赖波次生成剩余里程碑；同波次可沙箱并行再合并。

    冒烟失败时默认提前停止。parallel_workers<=1 时退化为串行。
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import shutil

    project = store.load(project_id)
    if project is None:
        raise FileNotFoundError(f"项目不存在: {project_id}")

    results: list[dict[str, Any]] = []
    waves: list[list[str]] = []
    stopped_early = False
    generated = 0
    workers = max(1, min(int(parallel_workers or 1), 4))
    limit = max(1, min(max_phases, 12))

    while generated < limit:
        project = store.load(project_id)
        if project is None:
            break
        ensure_phase_depends_on(project.phases)
        ready = ready_pending_phases(project.phases)
        if not ready:
            break

        batch = ready[: max(1, min(workers, limit - generated))]
        waves.append([str(p["id"]) for p in batch])
        main_ws = Path(project.workspace)

        if len(batch) == 1 or workers <= 1:
            pid = str(batch[0]["id"])
            project.current_phase_id = pid
            store.save(project)
            one = generate_phase_by_id(
                store,
                project_id,
                pid,
                config=config,
                use_agents=use_agents,
                async_mode=False,
            )
            results.append(
                {
                    "phase_id": one.get("phase_id"),
                    "via": one.get("via"),
                    "status": one.get("status"),
                    "written": one.get("written") or [],
                    "changed_files": one.get("changed_files") or [],
                    "task_runs": one.get("task_runs") or [],
                    "testing": one.get("testing"),
                }
            )
            generated += 1
            testing = one.get("testing") or {}
            if stop_on_smoke_fail and (
                testing.get("passed") is False or one.get("status") == "failed"
            ):
                stopped_early = True
                break
            continue

        # 同波次：各期在沙箱生成，再合并回主工作区
        sandbox_root = main_ws / ".mawp_sandbox"
        sandbox_root.mkdir(parents=True, exist_ok=True)

        def _job(phase_id: str) -> dict[str, Any]:
            sandbox = sandbox_root / phase_id
            _copy_workspace_for_sandbox(main_ws, sandbox)
            return generate_phase_by_id(
                store,
                project_id,
                phase_id,
                config=config,
                use_agents=use_agents,
                async_mode=False,
                workspace_override=sandbox,
                persist_project=False,
            )

        wave_results: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=len(batch)) as pool:
            futs = {pool.submit(_job, str(p["id"])): str(p["id"]) for p in batch}
            for fut in as_completed(futs):
                wave_results.append(fut.result())

        # 稳定顺序合并
        order = {str(p["id"]): i for i, p in enumerate(batch)}
        wave_results.sort(key=lambda r: order.get(str(r.get("phase_id")), 99))

        project = store.load(project_id)
        if project is None:
            break
        for one in wave_results:
            pid = str(one.get("phase_id") or "")
            sandbox = sandbox_root / pid
            merged = _merge_sandbox_files(main_ws, sandbox)
            written = list(one.get("written") or merged)
            via = f"parallel:{one.get('via')}"
            phase_meta = next((p for p in project.phases if p["id"] == pid), {"id": pid})
            outcome = one.get("outcome") or _finalize_phase_outcome(
                workspace=main_ws,
                phase=phase_meta,
                via=via,
                written=written,
                testing=one.get("testing") if isinstance(one.get("testing"), dict) else None,
            )
            for p in project.phases:
                if p["id"] == pid:
                    _apply_phase_fields(
                        p,
                        written=written,
                        via=via,
                        outcome=outcome,
                        testing=one.get("testing"),
                        task_runs=one.get("task_runs"),
                        attempts=int(one.get("attempts") or 1),
                    )
            results.append(
                {
                    "phase_id": pid,
                    "via": via,
                    "status": outcome["status"],
                    "written": written,
                    "changed_files": one.get("changed_files") or written,
                    "task_runs": one.get("task_runs") or [],
                    "testing": one.get("testing"),
                }
            )
            generated += 1
            testing = one.get("testing") or {}
            if stop_on_smoke_fail and (
                testing.get("passed") is False or outcome["status"] == "failed"
            ):
                stopped_early = True

        ready_next = ready_pending_phases(project.phases)
        pending = [p for p in project.phases if p.get("status") not in _TERMINAL_PHASE_STATUSES]
        project.current_phase_id = (
            (ready_next[0]["id"] if ready_next else None)
            or (pending[0]["id"] if pending else project.current_phase_id)
        )
        project.status = _project_status_after_phases(project.phases)
        # 合并回主仓后刷新全量差距报告
        try:
            from mawp.runtime.gap_report import (
                CapabilityStatus,
                build_gap_report,
                next_tasks_from_report,
                write_gap_artifacts,
            )

            report = build_gap_report(main_ws)
            write_gap_artifacts(main_ws, report)
            tasks = next_tasks_from_report(report)
            project.gap_summary = {
                "completed": [i.title for i in report.by_status(CapabilityStatus.DONE)],
                "partial": [i.title for i in report.by_status(CapabilityStatus.PARTIAL)],
                "missing": [i.title for i in report.by_status(CapabilityStatus.MISSING)],
                "next_tasks": tasks[:12],
                "files": [
                    "docs/GAP_WITH_SRS.md",
                    "docs/NEXT_TASKS.json",
                    "docs/gap_report.json",
                ],
            }
        except Exception:  # noqa: BLE001
            pass
        _write(
            main_ws / "docs" / "phases.json",
            json.dumps(project.phases, ensure_ascii=False, indent=2),
        )
        store.save(project)
        shutil.rmtree(sandbox_root, ignore_errors=True)
        if stopped_early:
            break

    project = store.load(project_id)
    return {
        "project": project.to_dict() if project else None,
        "results": results,
        "generated_count": len(results),
        "stopped_early": stopped_early,
        "waves": waves,
        "parallel_workers": workers,
    }


def run_phase_via_deliver(
    config: Any,
    *,
    project: AdvancedProject,
    phase: dict[str, Any],
    async_mode: bool = True,
    verify_only: bool = False,
) -> dict[str, Any]:
    """把当前里程碑交给 Deliver 链。P1 全量，后续期短链，verify_only 只冒烟。"""
    import time

    from mawp.core.engine import WorkflowEngine
    from mawp.storage.store import RunStore

    workspace = Path(project.workspace)
    root = config.workspace_path().resolve()
    try:
        project_root = workspace.resolve().relative_to(root).as_posix()
    except ValueError:
        project_root = workspace.as_posix()

    srs_path = workspace / "docs" / "SRS.md"
    srs_excerpt = ""
    if srs_path.is_file():
        from mawp.runtime.task_split import srs_slice_for_phase

        srs_excerpt = srs_slice_for_phase(
            srs_path.read_text(encoding="utf-8"),
            phase,
        )

    phase_title = str(phase.get("title") or phase.get("id") or "phase")
    phase_goal = str(phase.get("goal") or "")
    subtasks = phase_subtasks(phase)
    task_lines = "\n".join(
        f"- {t.get('id')}: {t.get('title')} {t.get('detail') or ''}".strip()
        for t in subtasks
    )
    goal = (
        f"【高级项目·分期】{project.title} / {phase_title}\n"
        f"本期目标：{phase_goal}\n"
        f"请按子任务拆分实现，避免一次生成过大模块：\n{task_lines}\n"
        f"请在 {project_root}/ 下实现可运行增量（API + Web），不要改平台源码。"
    )

    frontend_dir = f"{project_root}/apps/web"
    params: dict[str, Any] = {
        "goal": goal,
        "project_mode": True,
        "project_root": project_root,
        "project_title": project.title,
        "frontend_dir": frontend_dir,
        "phase_id": phase.get("id"),
        "srs_excerpt": srs_excerpt,
        "tasks": subtasks,
        # 真实冒烟走 metric_command；勿用 pass_on_attempt 故意先 fail
        "review_status": "pass",
        "debug_max_attempts": 2,
        "heal_max_rounds": 1,
        "coding_max_tasks": max(4, min(12, len(subtasks))),
        "verify_only": verify_only,
        "self_heal": not verify_only,
    }
    from mawp.runtime.deliver_profiles import select_deliver_workflow
    from mawp.runtime.project_deliver import ensure_project_metric

    ensure_project_metric(root, params, write_acceptance=not verify_only)

    rel_wf = select_deliver_workflow(phase, verify_only=verify_only)
    deliver_path = root / rel_wf
    if not deliver_path.is_file():
        alt = Path(config.workspace_path()) / rel_wf
        deliver_path = alt if alt.is_file() else deliver_path

    engine = WorkflowEngine(config)
    # 大项目默认异步启动再轮询；可用 MAWP_DELIVER_POLL_SECONDS 覆盖（默认 12 分钟）
    import os

    poll_seconds = int(
        os.environ.get("MAWP_DELIVER_POLL_SECONDS", str(DEFAULT_DELIVER_POLL_SECONDS))
    )
    record = engine.run_async(deliver_path, params_override=params)
    store = RunStore(config.workspace_path())
    terminal = {"DONE", "FAILED", "CANCELLED"}
    for _ in range(max(60, poll_seconds)):
        latest = store.load_run(record.run_id)
        if latest is not None:
            record = latest
        status = (record.status or "").upper()
        if status == "WAITING_USER":
            record = engine.resume(record.run_id, "approve")
            continue
        if status in terminal:
            break
        time.sleep(1)
    else:
        raise TimeoutError(
            f"Deliver 超时未完成({poll_seconds}s): {record.run_id} status={record.status}"
        )

    if (record.status or "").upper() == "FAILED" and not verify_only:
        raise RuntimeError(record.error or f"Deliver 失败: {record.run_id}")

    outs = record.node_outputs or {}
    coding = outs.get("coding") or {}
    frontend = outs.get("frontend") or {}
    testing = outs.get("testing") or outs.get("testing_1") or {}
    written: list[str] = []
    for key in ("changed_files", "artifacts"):
        for src in (coding, frontend):
            vals = src.get(key) or []
            if isinstance(vals, list):
                written.extend(str(v) for v in vals)
    seen: set[str] = set()
    uniq: list[str] = []
    for w in written:
        if w not in seen:
            seen.add(w)
            uniq.append(w)

    task_runs = coding.get("task_runs") or []
    task_lines = (
        "\n".join(
            f"- `{t.get('task_id')}` {t.get('title')}: "
            f"{'ok' if t.get('success', True) else 'fail'} · "
            f"{len(t.get('changed_files') or [])} files"
            for t in task_runs
            if isinstance(t, dict)
        )
        or "- （单次 Coding / stub）"
    )
    test_passed = testing.get("passed")
    test_log = str(testing.get("log_summary") or "")
    metric = str(testing.get("metric_command") or params.get("metric_command") or "")

    phase_note = workspace / "docs" / f"PHASE_{str(phase.get('id') or 'X').upper()}_DELIVER.md"
    _write(
        phase_note,
        f"""# {phase_title} · 八 Agent Deliver

- run_id: `{record.run_id}`
- status: `{record.status}`
- project_root: `{project_root}`
- coding.mode: `{coding.get('mode') or ''}`

## Coding 任务循环

{task_lines}

## 验收（Testing）

- passed: `{test_passed}`
- metric: `{metric}`
- log: {test_log or '（无）'}

## 产出文件

{chr(10).join(f'- `{p}`' for p in uniq) or '- （见 node_outputs）'}
""",
    )
    uniq.append(str(phase_note.relative_to(workspace)))

    return {
        "written": uniq,
        "run": record.to_dict(),
        "project_root": project_root,
        "testing": {
            "passed": test_passed,
            "log_summary": test_log,
            "metric_command": metric,
            "failures": list(testing.get("failures") or []),
        },
        "task_runs": task_runs,
        "changed_files": list(coding.get("changed_files") or []),
    }

