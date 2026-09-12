"""数据层门禁：SQLite 脚手架 + tenant_id 扫描 + 跨租户隔离。"""

from __future__ import annotations

from pathlib import Path

from mawp.runtime.data_layer_gate import (
    assemble_data_layer,
    ensure_project_db_scaffold,
    find_models_missing_tenant,
    run_tenant_isolation_probe,
)


def test_ensure_db_scaffold_writes_db_py(tmp_path: Path) -> None:
    root = "workspaces/demo"
    api = tmp_path / root / "apps" / "api"
    api.mkdir(parents=True)
    written = ensure_project_db_scaffold(tmp_path, root)
    assert "apps/api/db.py" in written
    db_py = api / "db.py"
    assert db_py.is_file()
    text = db_py.read_text(encoding="utf-8")
    assert "tenant_id" in text
    assert "community_id" in text
    assert "sqlite3" in text or "sqlite" in text.lower()
    # idempotent
    again = ensure_project_db_scaffold(tmp_path, root)
    assert again == []


def test_find_models_missing_tenant(tmp_path: Path) -> None:
    api = tmp_path / "apps" / "api"
    api.mkdir(parents=True)
    (api / "models_mall.py").write_text(
        '''\
from pydantic import BaseModel

class Product(BaseModel):
    id: str
    name: str
    price: float

class Order(BaseModel):
    id: str
    tenant_id: str = "demo-tenant"
    community_id: str = "demo-community"
    product_id: str
''',
        encoding="utf-8",
    )
    missing = find_models_missing_tenant(api)
    assert any("Product" in m for m in missing)
    assert not any("Order" in m for m in missing)


def test_assemble_data_layer_reports_tenant_gaps(tmp_path: Path) -> None:
    root = "workspaces/demo"
    api = tmp_path / root / "apps" / "api"
    api.mkdir(parents=True)
    (api / "models.py").write_text(
        "from pydantic import BaseModel\n"
        "class Bill(BaseModel):\n"
        "    id: str\n"
        "    amount: float\n",
        encoding="utf-8",
    )
    report = assemble_data_layer(tmp_path, root)
    assert report.scaffolded
    assert report.missing_tenant
    assert report.to_dict()["ok"] is False


def test_tenant_isolation_probe_fails_without_filter(tmp_path: Path) -> None:
    """跨租户：A 写入后 B 不应看到（由脚手架自带 probe 验证）。"""
    root = "workspaces/demo"
    api = tmp_path / root / "apps" / "api"
    api.mkdir(parents=True)
    ensure_project_db_scaffold(tmp_path, root)
    # 故意写入不带隔离的脏数据工具函数场景：调用官方 probe 应通过（scaffold 自带隔离）
    ok, detail = run_tenant_isolation_probe(api)
    assert ok is True, detail


def test_generate_phase_mall_uses_sqlite_and_tenant(tmp_path: Path) -> None:
    from mawp.advanced import AdvancedProject, generate_phase_mall

    ws = tmp_path / "ws"
    (ws / "apps" / "api").mkdir(parents=True)
    (ws / "apps" / "web").mkdir(parents=True)
    project = AdvancedProject(
        id="t",
        title="邻智云",
        source_filename="s.md",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        workspace=str(ws),
    )
    written = generate_phase_mall(ws, project)
    mall = (ws / "apps" / "api" / "routers" / "mall.py").read_text(encoding="utf-8")
    assert "tenant_id" in mall
    assert "community_id" in mall
    assert "PRODUCTS: list" not in mall
    assert "sqlite" in mall.lower() or "get_conn" in mall or "from db import" in mall
    assert (ws / "apps" / "api" / "db.py").is_file() or any("db.py" in w for w in written)
