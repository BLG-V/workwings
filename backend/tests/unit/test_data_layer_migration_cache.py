"""迁移脚本 / seed / 可插拔 Cache（memory | redis）。"""

from __future__ import annotations

from pathlib import Path

from mawp.runtime.cache_backend import Cache, get_cache, make_cache
from mawp.runtime.data_layer_gate import (
    assemble_data_layer,
    ensure_migration_and_seed,
    ensure_project_db_scaffold,
)


def test_ensure_migration_and_seed_writes_files(tmp_path: Path) -> None:
    root = "workspaces/demo"
    api = tmp_path / root / "apps" / "api"
    api.mkdir(parents=True)
    ensure_project_db_scaffold(tmp_path, root)
    written = ensure_migration_and_seed(tmp_path, root, phase_id="p4")
    assert any("migrations" in w and w.endswith(".sql") for w in written)
    assert any(w.endswith("seed.py") or "seed_" in w for w in written)
    mig_dir = tmp_path / root / "docs" / "migrations"
    assert mig_dir.is_dir()
    sqls = list(mig_dir.glob("*.sql"))
    assert sqls
    text = sqls[0].read_text(encoding="utf-8")
    assert "tenant_id" in text
    assert "CREATE TABLE" in text.upper() or "create table" in text.lower()
    seed = tmp_path / root / "scripts" / "seed_p4.py"
    assert seed.is_file()
    seed_txt = seed.read_text(encoding="utf-8")
    assert "demo-tenant" in seed_txt
    assert "demo-community" in seed_txt
    # idempotent
    again = ensure_migration_and_seed(tmp_path, root, phase_id="p4")
    assert again == []


def test_assemble_data_layer_includes_migration_seed_cache(tmp_path: Path) -> None:
    root = "workspaces/demo"
    (tmp_path / root / "apps" / "api").mkdir(parents=True)
    report = assemble_data_layer(tmp_path, root, phase_id="p2")
    assert "apps/api/db.py" in report.scaffolded
    assert any("migrations" in s for s in report.scaffolded)
    assert any("seed" in s for s in report.scaffolded)
    assert any(s.endswith("cache.py") for s in report.scaffolded)
    assert (tmp_path / root / "apps" / "api" / "cache.py").is_file()


def test_memory_cache_roundtrip() -> None:
    cache = make_cache("memory")
    assert cache.get("k") is None
    cache.set("k", {"v": 1}, ttl_seconds=60)
    assert cache.get("k") == {"v": 1}
    cache.delete("k")
    assert cache.get("k") is None


def test_get_cache_defaults_to_memory(monkeypatch) -> None:
    monkeypatch.delenv("MAWP_CACHE_BACKEND", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    c = get_cache(force_new=True)
    assert c.backend_name == "memory"
    c.set("a", "b")
    assert c.get("a") == "b"


def test_redis_backend_falls_back_when_unavailable(monkeypatch) -> None:
    monkeypatch.setenv("MAWP_CACHE_BACKEND", "redis")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6399/0")
    c = make_cache("redis", redis_url="redis://127.0.0.1:6399/0")
    # 无 redis 服务 / 无 redis 包时必须降级 memory，不能抛
    assert c.backend_name in {"memory", "redis"}
    c.set("x", "y", ttl_seconds=10)
    assert c.get("x") == "y"


def test_cache_protocol_is_pluggable() -> None:
    class Fake:
        backend_name = "fake"

        def __init__(self) -> None:
            self.d: dict = {}

        def get(self, key: str):
            return self.d.get(key)

        def set(self, key: str, value, ttl_seconds: int = 300) -> None:
            self.d[key] = value

        def delete(self, key: str) -> None:
            self.d.pop(key, None)

    fake: Cache = Fake()
    fake.set("t", 1)
    assert fake.get("t") == 1
