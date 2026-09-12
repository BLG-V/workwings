"""MAWP apps: 扫描 app.yaml、list / enable（C↔D 联调最小实现）。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class AppInfo:
    id: str
    name: str
    path: Path
    version: str = "0.0.0"
    enabled: bool = False
    entry_workflow: str | None = None
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "path": str(self.path),
            "version": self.version,
            "enabled": self.enabled,
            "entry_workflow": self.entry_workflow,
            "description": self.description,
        }


class AppRegistry:
    def __init__(self, workspace: Path):
        self.workspace = Path(workspace).resolve()
        self.apps_dir = self.workspace / "apps"
        self.state_path = self.workspace / ".mawp" / "apps" / "enabled.json"
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

    def _state_exists(self) -> bool:
        return self.state_path.is_file()

    def _load_enabled(self) -> set[str]:
        if not self.state_path.is_file():
            return set()
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return set()
        if isinstance(data, list):
            return {str(x) for x in data}
        if isinstance(data, dict):
            return {str(k) for k, v in data.items() if v}
        return set()

    def _save_enabled(self, enabled: set[str]) -> None:
        self.state_path.write_text(
            json.dumps(sorted(enabled), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _scan_raw(self) -> list[AppInfo]:
        found: list[AppInfo] = []
        if not self.apps_dir.is_dir():
            return found
        for child in sorted(self.apps_dir.iterdir()):
            app_yaml = child / "app.yaml"
            if not child.is_dir() or not app_yaml.is_file():
                continue
            raw = yaml.safe_load(app_yaml.read_text(encoding="utf-8")) or {}
            app_id = str(raw.get("id") or child.name)
            found.append(
                AppInfo(
                    id=app_id,
                    name=str(raw.get("name") or app_id),
                    path=child,
                    version=str(raw.get("version") or "0.0.0"),
                    enabled=False,
                    entry_workflow=raw.get("entry_workflow"),
                    description=str(raw.get("description") or ""),
                )
            )
        return found

    def discover(self) -> list[AppInfo]:
        """扫描 apps/。无 enabled.json 时默认全部启用（演示友好）。"""
        found = self._scan_raw()
        if not found:
            return found
        if not self._state_exists():
            for info in found:
                info.enabled = True
            return found
        enabled = self._load_enabled()
        for info in found:
            info.enabled = info.id in enabled
        return found

    def list_apps(self) -> list[AppInfo]:
        return self.discover()

    def enable(self, app_id: str) -> AppInfo:
        apps = {a.id: a for a in self._scan_raw()}
        if app_id not in apps:
            raise KeyError(f"未找到 App: {app_id}")
        if self._state_exists():
            enabled = self._load_enabled()
        else:
            enabled = set(apps)
        enabled.add(app_id)
        self._save_enabled(enabled)
        info = apps[app_id]
        info.enabled = True
        return info

    def disable(self, app_id: str) -> AppInfo:
        apps = {a.id: a for a in self._scan_raw()}
        if app_id not in apps:
            raise KeyError(f"未找到 App: {app_id}")
        if self._state_exists():
            enabled = self._load_enabled()
        else:
            # 默认全开 → 首次停用时固化为「其余仍启用」
            enabled = set(apps)
        enabled.discard(app_id)
        self._save_enabled(enabled)
        info = apps[app_id]
        info.enabled = False
        return info
