"""数据层确定性门禁：SQLite 脚手架 + tenant 字段扫描 + 跨租户探活。

不新增 Agent。coding 后写入/补齐 apps/api/db.py，扫描 models 缺租户字段，
冒烟可调用 run_tenant_isolation_probe。
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DB_REL = "apps/api/db.py"

DB_SCAFFOLD = '''\
"""SQLite 数据层脚手架（MAWP project_mode）。

约定：
- 业务表必须带 tenant_id + community_id
- 查询默认按租户过滤；跨租户不可见
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "app.db"


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """创建最小示例表（可被业务扩展）。"""
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tenant_demo (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                community_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tenant_demo_tenant "
            "ON tenant_demo(tenant_id, community_id)"
        )
        conn.commit()


def tenant_isolation_ok() -> tuple[bool, str]:
    """写入租户 A 后，租户 B 查询应为空。"""
    init_db()
    with get_conn() as conn:
        conn.execute("DELETE FROM tenant_demo")
        conn.execute(
            "INSERT INTO tenant_demo(id, tenant_id, community_id, title, created_at) "
            "VALUES (?, ?, ?, ?, datetime('now'))",
            ("T-A1", "tenant-a", "community-a", "only-a"),
        )
        conn.commit()
        rows_b = conn.execute(
            "SELECT id FROM tenant_demo WHERE tenant_id=? AND community_id=?",
            ("tenant-b", "community-b"),
        ).fetchall()
        rows_a = conn.execute(
            "SELECT id FROM tenant_demo WHERE tenant_id=? AND community_id=?",
            ("tenant-a", "community-a"),
        ).fetchall()
    if rows_b:
        return False, "tenant-b saw tenant-a rows (isolation broken)"
    if not rows_a:
        return False, "tenant-a seed missing"
    return True, "tenant isolation ok"


if __name__ == "__main__":
    ok, msg = tenant_isolation_ok()
    print("TENANT_ISOLATION:", "PASS" if ok else "FAIL", msg)
    raise SystemExit(0 if ok else 1)
'''


_SKIP_MODEL_NAMES = {
    "BaseModel",
    "ItemCreate",
    "OrderCreate",
    "RepairCreate",
    "Base",
}


@dataclass
class DataLayerReport:
    scaffolded: list[str] = field(default_factory=list)
    missing_tenant: list[str] = field(default_factory=list)
    isolation_ok: bool | None = None
    isolation_detail: str = ""
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.missing_tenant and not self.errors and self.isolation_ok is not False

    def to_dict(self) -> dict[str, Any]:
        return {
            "scaffolded": list(self.scaffolded),
            "missing_tenant": list(self.missing_tenant),
            "isolation_ok": self.isolation_ok,
            "isolation_detail": self.isolation_detail,
            "errors": list(self.errors),
            "ok": self.ok,
        }


def ensure_project_db_scaffold(workspace: Path, project_root: str) -> list[str]:
    """写入 apps/api/db.py（已存在则跳过）。返回相对路径列表。"""
    root = str(project_root or "").replace("\\", "/").rstrip("/")
    if root in {".", ""}:
        api = workspace / "apps" / "api"
        rel = "apps/api/db.py"
    else:
        api = workspace / root / "apps" / "api"
        rel = "apps/api/db.py"
    if not api.is_dir():
        return []
    db_py = api / "db.py"
    if db_py.is_file():
        return []
    db_py.parent.mkdir(parents=True, exist_ok=True)
    db_py.write_text(DB_SCAFFOLD, encoding="utf-8")
    (api / "data").mkdir(parents=True, exist_ok=True)
    (api / "data" / ".gitkeep").write_text("", encoding="utf-8")
    return [rel]


def _class_has_field(node: ast.ClassDef, name: str) -> bool:
    for stmt in node.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            if stmt.target.id == name:
                return True
        if isinstance(stmt, ast.Assign):
            for t in stmt.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    return True
    return False


def _is_entity_model(node: ast.ClassDef) -> bool:
    """启发式：带 id 注解的 Pydantic/业务模型，排除 *Create DTO。"""
    if node.name in _SKIP_MODEL_NAMES:
        return False
    if node.name.endswith("Create") or node.name.endswith("Update"):
        return False
    bases = []
    for b in node.bases:
        if isinstance(b, ast.Name):
            bases.append(b.id)
        elif isinstance(b, ast.Attribute):
            bases.append(b.attr)
    if not any(x in {"BaseModel", "Base"} for x in bases):
        # 也接受显式带 id + 多字段的普通 class（少见）
        if not _class_has_field(node, "id"):
            return False
    return _class_has_field(node, "id")


def find_models_missing_tenant(api_dir: Path) -> list[str]:
    """扫描 models*.py / *model*.py 中缺 tenant_id 或 community_id 的实体。"""
    missing: list[str] = []
    if not api_dir.is_dir():
        return missing
    files: list[Path] = []
    files.extend(api_dir.glob("models*.py"))
    files.extend(api_dir.glob("*_models.py"))
    for path in sorted(set(files)):
        if path.name.startswith("_"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            if not _is_entity_model(node):
                continue
            has_t = _class_has_field(node, "tenant_id")
            has_c = _class_has_field(node, "community_id")
            if not (has_t and has_c):
                rel = path.as_posix()
                if api_dir.name == "api":
                    # prefer relative to api
                    try:
                        rel = path.relative_to(api_dir).as_posix()
                    except ValueError:
                        pass
                missing.append(f"{rel}::{node.name}")
    return missing


def run_tenant_isolation_probe(api_dir: Path) -> tuple[bool, str]:
    """执行 apps/api/db.py 的 tenant_isolation_ok（若存在）。"""
    db_py = api_dir / "db.py"
    if not db_py.is_file():
        return False, "apps/api/db.py missing"
    import importlib.util
    import sys

    # 独立目录加载，避免污染
    mod_name = f"mawp_tenant_probe_{abs(hash(str(api_dir))) % 10_000_000}"
    spec = importlib.util.spec_from_file_location(mod_name, db_py)
    if spec is None or spec.loader is None:
        return False, "cannot load db.py"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:  # noqa: BLE001
        return False, f"db.py import failed: {exc}"
    fn = getattr(mod, "tenant_isolation_ok", None)
    if not callable(fn):
        return False, "db.py missing tenant_isolation_ok()"
    try:
        ok, detail = fn()
        return bool(ok), str(detail)
    except Exception as exc:  # noqa: BLE001
        return False, f"tenant probe error: {exc}"


DB_REL = "apps/api/db.py"
CACHE_REL = "apps/api/cache.py"

CACHE_SCAFFOLD = '''\
"""可插拔缓存（MAWP）。默认 memory；MAWP_CACHE_BACKEND=redis 时用 Redis。"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Any


class MemoryCache:
    backend_name = "memory"

    def __init__(self) -> None:
        self._data: dict[str, tuple[Any, float | None]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            value, expires = item
            if expires is not None and time.time() > expires:
                self._data.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        expires = time.time() + max(0, int(ttl_seconds)) if ttl_seconds else None
        with self._lock:
            self._data[key] = (value, expires)

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)


def get_cache():
    backend = (os.environ.get("MAWP_CACHE_BACKEND") or "memory").strip().lower()
    if backend == "redis":
        try:
            import redis  # type: ignore

            url = os.environ.get("REDIS_URL") or "redis://127.0.0.1:6379/0"
            client = redis.Redis.from_url(url, decode_responses=True)
            client.ping()

            class RedisCache:
                backend_name = "redis"

                def get(self, key: str) -> Any:
                    raw = client.get(key)
                    if raw is None:
                        return None
                    try:
                        return json.loads(raw)
                    except json.JSONDecodeError:
                        return raw

                def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
                    payload = json.dumps(value, ensure_ascii=False, default=str)
                    if ttl_seconds and ttl_seconds > 0:
                        client.setex(key, int(ttl_seconds), payload)
                    else:
                        client.set(key, payload)

                def delete(self, key: str) -> None:
                    client.delete(key)

            return RedisCache()
        except Exception:
            pass
    return MemoryCache()


cache = get_cache()
'''


def _project_paths(workspace: Path, project_root: str) -> tuple[Path, Path, str]:
    """返回 (api_dir, project_abs, root_label)。root_label 用于相对路径。"""
    root = str(project_root or "").replace("\\", "/").rstrip("/")
    if root in {".", ""}:
        return workspace / "apps" / "api", workspace, ""
    return workspace / root / "apps" / "api", workspace / root, root


def ensure_cache_scaffold(workspace: Path, project_root: str) -> list[str]:
    api, _proj, _root = _project_paths(workspace, project_root)
    if not api.is_dir():
        return []
    path = api / "cache.py"
    if path.is_file():
        return []
    path.write_text(CACHE_SCAFFOLD, encoding="utf-8")
    return [CACHE_REL]


def ensure_migration_and_seed(
    workspace: Path,
    project_root: str,
    *,
    phase_id: str | None = None,
) -> list[str]:
    """写入 docs/migrations/*.sql 与 scripts/seed_{phase}.py（已存在则跳过）。"""
    api, proj, _root = _project_paths(workspace, project_root)
    if not api.is_dir():
        return []
    pid = (phase_id or "phase").strip().lower() or "phase"
    mig_dir = proj / "docs" / "migrations"
    scripts = proj / "scripts"
    mig_dir.mkdir(parents=True, exist_ok=True)
    scripts.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    existing = sorted(mig_dir.glob(f"*_{pid}.sql"))
    if not existing:
        seq = 1
        while (mig_dir / f"{seq:03d}_{pid}.sql").is_file():
            seq += 1
        sql_name = f"{seq:03d}_{pid}.sql"
        (mig_dir / sql_name).write_text(
            f"""-- MAWP migration · {pid}
-- 业务表必须含 tenant_id + community_id，并建联合索引

CREATE TABLE IF NOT EXISTS tenant_demo (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    community_id TEXT NOT NULL,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tenant_demo_tenant
    ON tenant_demo(tenant_id, community_id);

-- phase={pid}：可在此追加本期业务表
""",
            encoding="utf-8",
        )
        written.append(f"docs/migrations/{sql_name}")

    seed_path = scripts / f"seed_{pid}.py"
    if not seed_path.is_file():
        seed_id = f"SEED-{pid.upper()}"
        seed_path.write_text(
            f'''\
"""Seed data for {pid} — demo-tenant / demo-community."""
from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "apps" / "api" / "data" / "app.db"
TENANT = "demo-tenant"
COMMUNITY = "demo-community"
SEED_ID = "{seed_id}"


def main() -> int:
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tenant_demo (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            community_id TEXT NOT NULL,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tenant_demo_tenant "
        "ON tenant_demo(tenant_id, community_id)"
    )
    row = conn.execute(
        "SELECT id FROM tenant_demo WHERE id=?",
        (SEED_ID,),
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO tenant_demo(id, tenant_id, community_id, title, created_at) "
            "VALUES (?, ?, ?, ?, datetime('now'))",
            (SEED_ID, TENANT, COMMUNITY, "seed for {pid}"),
        )
        conn.commit()
        print(f"SEED OK: inserted {{SEED_ID}} for {{TENANT}}/{{COMMUNITY}}")
    else:
        print(f"SEED OK: already present {{SEED_ID}}")
    other = conn.execute(
        "SELECT id FROM tenant_demo WHERE tenant_id=? AND community_id=?",
        ("other-tenant", "other-community"),
    ).fetchall()
    conn.close()
    if other:
        print("SEED FAIL: cross-tenant leak")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
''',
            encoding="utf-8",
        )
        written.append(f"scripts/seed_{pid}.py")

    return written


def assemble_data_layer(
    workspace: Path,
    project_root: str,
    *,
    phase_id: str | None = None,
) -> DataLayerReport:
    """补脚手架、扫描缺租户、跑隔离探活。"""
    report = DataLayerReport()
    root = str(project_root or "").replace("\\", "/").rstrip("/")
    api, _proj, _ = _project_paths(workspace, root or ".")
    if not api.is_dir():
        report.errors.append("apps/api missing")
        return report

    scaffolded: list[str] = []
    scaffolded.extend(ensure_project_db_scaffold(workspace, root or "."))
    scaffolded.extend(ensure_cache_scaffold(workspace, root or "."))
    scaffolded.extend(
        ensure_migration_and_seed(workspace, root or ".", phase_id=phase_id)
    )
    report.scaffolded = scaffolded
    report.missing_tenant = find_models_missing_tenant(api)
    mem_hits = detect_memory_only_business_store(api)
    for rel in mem_hits:
        report.errors.append(f"memory-only store without tenant: {rel}")
    ok, detail = run_tenant_isolation_probe(api)
    report.isolation_ok = ok
    report.isolation_detail = detail
    if not ok:
        report.errors.append(f"tenant isolation: {detail}")
    return report


_MEMORY_STORE = re.compile(
    r"^(PRODUCTS|ORDERS|ITEMS|CAPTAINS)\s*:\s*list\[",
    re.MULTILINE,
)


def detect_memory_only_business_store(api_dir: Path) -> list[str]:
    """商城等业务仍用内存 list 且文件内无 tenant_id → 记为数据层缺口。"""
    hits: list[str] = []
    if not api_dir.is_dir():
        return hits
    routers = api_dir / "routers"
    paths = list(api_dir.glob("*.py"))
    if routers.is_dir():
        paths.extend(routers.glob("*.py"))
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if not _MEMORY_STORE.search(text):
            continue
        if "tenant_id" in text and ("get_conn" in text or "sqlite" in text.lower()):
            continue
        if "tenant_id" not in text:
            try:
                rel = path.relative_to(api_dir).as_posix()
            except ValueError:
                rel = path.name
            hits.append(rel)
    return hits
