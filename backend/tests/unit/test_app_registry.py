"""AppRegistry：缺省启用与 enable/disable 固化。"""

from __future__ import annotations

from pathlib import Path

from mawp.apps.registry import AppRegistry


def _seed_app(workspace: Path, app_id: str = "demo-code-agent") -> Path:
    app_dir = workspace / "apps" / app_id
    app_dir.mkdir(parents=True)
    (app_dir / "app.yaml").write_text(
        f"id: {app_id}\nname: Demo\nversion: '0.1.0'\nentry_workflow: w.yaml\n",
        encoding="utf-8",
    )
    return app_dir


def test_discover_defaults_enabled_without_state(tmp_path: Path) -> None:
    _seed_app(tmp_path)
    registry = AppRegistry(tmp_path)
    apps = registry.list_apps()
    assert len(apps) == 1
    assert apps[0].id == "demo-code-agent"
    assert apps[0].enabled is True
    assert not (tmp_path / ".mawp" / "apps" / "enabled.json").is_file()


def test_disable_persists_allowlist(tmp_path: Path) -> None:
    _seed_app(tmp_path, "a")
    _seed_app(tmp_path, "b")
    registry = AppRegistry(tmp_path)
    registry.disable("a")
    apps = {x.id: x for x in registry.list_apps()}
    assert apps["a"].enabled is False
    assert apps["b"].enabled is True
    state = (tmp_path / ".mawp" / "apps" / "enabled.json").read_text(encoding="utf-8")
    assert '"b"' in state
    assert '"a"' not in state


def test_explicit_empty_allowlist_means_all_disabled(tmp_path: Path) -> None:
    _seed_app(tmp_path)
    state_dir = tmp_path / ".mawp" / "apps"
    state_dir.mkdir(parents=True)
    (state_dir / "enabled.json").write_text("[]", encoding="utf-8")
    registry = AppRegistry(tmp_path)
    assert registry.list_apps()[0].enabled is False
