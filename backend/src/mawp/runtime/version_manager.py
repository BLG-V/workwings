# -*- coding: utf-8 -*-
"""版本管理：为每次 Deliver 生成可回溯的产物快照，并支持 diff / 回滚。"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


SNAPSHOT_DIR_NAME = "versions"
LATEST_FILE_NAME = "latest.json"


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_text_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _read_text_if_exists(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


@dataclass
class VersionSnapshotResult:
    ok: bool
    snapshot_id: str
    snapshot_path: str
    project_path: str
    files: list[str]
    copied_count: int
    manifest_path: str
    latest_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "snapshot_id": self.snapshot_id,
            "snapshot_path": self.snapshot_path,
            "project_path": self.project_path,
            "files": self.files,
            "copied_count": self.copied_count,
            "manifest_path": self.manifest_path,
            "latest_path": self.latest_path,
        }


def _build_snapshot_id(run_id: str | None = None) -> str:
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    if run_id:
        return f"{stamp}-{str(run_id)[:8]}"
    return stamp


def _iter_project_files(project_path: Path) -> list[Path]:
    skip = {"node_modules", ".git", "__pycache__", ".venv", "venv", ".mawp", SNAPSHOT_DIR_NAME}
    files: list[Path] = []
    for path in sorted(project_path.rglob("*")):
        if not path.is_file():
            continue
        if skip.intersection(path.relative_to(project_path).parts):
            continue
        files.append(path)
    return files


def _copy_tree(src: Path, dst: Path) -> list[str]:
    copied: list[str] = []
    for path in _iter_project_files(src):
        rel = path.relative_to(src)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied.append(rel.as_posix())
    return copied


def create_version_snapshot(
    project_path: Path | str,
    *,
    run_id: str | None = None,
    label: str | None = None,
    note: str | None = None,
    include_docs: bool = True,
    status: str | None = None,
) -> dict[str, Any]:
    """创建项目版本快照。"""
    project_path = Path(project_path).resolve()
    if not project_path.is_dir():
        return {"ok": False, "error": f"project path not found: {project_path}"}

    versions_dir = _ensure_dir(project_path / SNAPSHOT_DIR_NAME)
    snapshot_id = _build_snapshot_id(run_id)
    snapshot_path = versions_dir / snapshot_id
    snapshot_path.mkdir(parents=True, exist_ok=True)

    files = _copy_tree(project_path, snapshot_path)

    manifest = {
        "snapshot_id": snapshot_id,
        "run_id": run_id,
        "label": label or snapshot_id,
        "note": note,
        "status": status,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "project_path": str(project_path),
        "file_count": len(files),
        "files": files,
    }
    manifest_path = snapshot_path / "manifest.json"
    _safe_text_write(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2))

    latest = {
        "snapshot_id": snapshot_id,
        "snapshot_path": str(snapshot_path),
        "manifest_path": str(manifest_path),
        "label": label or snapshot_id,
        "created_at": manifest["created_at"],
        "status": status,
    }
    latest_path = versions_dir / LATEST_FILE_NAME
    _safe_text_write(latest_path, json.dumps(latest, ensure_ascii=False, indent=2))

    if include_docs:
        docs_dir = _ensure_dir(project_path / "docs")
        _safe_text_write(
            docs_dir / "VERSION_LATEST.json",
            json.dumps(latest, ensure_ascii=False, indent=2),
        )

    return VersionSnapshotResult(
        ok=True,
        snapshot_id=snapshot_id,
        snapshot_path=str(snapshot_path),
        project_path=str(project_path),
        files=files,
        copied_count=len(files),
        manifest_path=str(manifest_path),
        latest_path=str(latest_path),
    ).to_dict()


def list_version_snapshots(project_path: Path | str) -> dict[str, Any]:
    project_path = Path(project_path).resolve()
    versions_dir = project_path / SNAPSHOT_DIR_NAME
    if not versions_dir.is_dir():
        return {"ok": True, "snapshots": []}

    snapshots: list[dict[str, Any]] = []
    for snap_dir in sorted([p for p in versions_dir.iterdir() if p.is_dir()], reverse=True):
        manifest = snap_dir / "manifest.json"
        data: dict[str, Any] = {}
        if manifest.is_file():
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        snapshots.append(
            {
                "snapshot_id": snap_dir.name,
                "path": str(snap_dir),
                "label": data.get("label") or snap_dir.name,
                "created_at": data.get("created_at"),
                "file_count": data.get("file_count", 0),
                "run_id": data.get("run_id"),
                "status": data.get("status"),
                "note": data.get("note"),
            }
        )
    return {"ok": True, "snapshots": snapshots}


def diff_snapshot_to_current(
    project_path: Path | str,
    snapshot_id: str,
    *,
    rel_path: str | None = None,
) -> dict[str, Any]:
    project_path = Path(project_path).resolve()
    snapshot_path = project_path / SNAPSHOT_DIR_NAME / snapshot_id
    if not snapshot_path.is_dir():
        return {"ok": False, "error": f"snapshot not found: {snapshot_id}"}

    import difflib

    if rel_path:
        current = _read_text_if_exists(project_path / rel_path)
        old = _read_text_if_exists(snapshot_path / rel_path)
        diff = "".join(
            difflib.unified_diff(
                old.splitlines(keepends=True),
                current.splitlines(keepends=True),
                fromfile=f"snapshot/{snapshot_id}/{rel_path}",
                tofile=f"current/{rel_path}",
            )
        )
        return {
            "ok": True,
            "snapshot_id": snapshot_id,
            "path": rel_path,
            "diff": diff,
            "has_diff": bool(diff.strip()),
        }

    # 全量 diff 概览
    snapshot_files = {p.relative_to(snapshot_path).as_posix() for p in snapshot_path.rglob("*") if p.is_file()}
    current_files = {p.relative_to(project_path).as_posix() for p in _iter_project_files(project_path)}
    added = sorted(current_files - snapshot_files)
    removed = sorted(snapshot_files - current_files)
    common = sorted(current_files & snapshot_files)
    changed: list[str] = []
    for rel in common[:200]:
        current = _read_text_if_exists(project_path / rel)
        old = _read_text_if_exists(snapshot_path / rel)
        if current != old:
            changed.append(rel)
    return {
        "ok": True,
        "snapshot_id": snapshot_id,
        "added": added,
        "removed": removed,
        "changed": changed,
        "summary": {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
        },
    }


def restore_version_snapshot(
    project_path: Path | str,
    snapshot_id: str,
    *,
    overwrite: bool = True,
) -> dict[str, Any]:
    project_path = Path(project_path).resolve()
    snapshot_path = project_path / SNAPSHOT_DIR_NAME / snapshot_id
    if not snapshot_path.is_dir():
        return {"ok": False, "error": f"snapshot not found: {snapshot_id}"}

    restored: list[str] = []
    for src in snapshot_path.rglob("*"):
        if not src.is_file():
            continue
        if src.name == "manifest.json":
            continue
        rel = src.relative_to(snapshot_path)
        dst = project_path / rel
        if dst.exists() and not overwrite:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        restored.append(rel.as_posix())

    return {
        "ok": True,
        "snapshot_id": snapshot_id,
        "restored_files": restored,
        "restored_count": len(restored),
    }


# --- 兼容平台 API 的包装函数 ---

def list_versions(project_path: Path | str) -> list[dict[str, Any]]:
    data = list_version_snapshots(project_path)
    return list(data.get("snapshots") or [])


def get_version_detail(project_path: Path | str, version: str) -> dict[str, Any] | None:
    project_path = Path(project_path).resolve()
    snap = project_path / SNAPSHOT_DIR_NAME / version
    if not snap.is_dir():
        return None

    manifest = snap / "manifest.json"
    data: dict[str, Any] = {}
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    return {
        "version": version,
        "path": str(snap),
        "manifest": data,
        "files": data.get("files", []),
    }


def rollback_to_version(project_path: Path | str, version: str) -> dict[str, Any]:
    result = restore_version_snapshot(project_path, version, overwrite=True)
    if not result.get("ok"):
        return result

    # 记录回滚标记，方便 UI 显示
    project_path = Path(project_path).resolve()
    versions_dir = project_path / SNAPSHOT_DIR_NAME
    latest_path = versions_dir / LATEST_FILE_NAME
    marker = {
        "snapshot_id": version,
        "rolled_back_at": datetime.utcnow().isoformat() + "Z",
    }
    _safe_text_write(latest_path, json.dumps(marker, ensure_ascii=False, indent=2))
    docs_dir = _ensure_dir(project_path / "docs")
    _safe_text_write(docs_dir / "VERSION_LATEST.json", json.dumps(marker, ensure_ascii=False, indent=2))
    return {"ok": True, **result, "rolled_back": True}


def diff_versions(project_path: Path | str, version_a: str, version_b: str) -> dict[str, Any]:
    """对比两个版本快照之间的差异。"""
    project_path = Path(project_path).resolve()
    path_a = project_path / SNAPSHOT_DIR_NAME / version_a
    path_b = project_path / SNAPSHOT_DIR_NAME / version_b
    if not path_a.is_dir():
        return {"ok": False, "error": f"version not found: {version_a}"}
    if not path_b.is_dir():
        return {"ok": False, "error": f"version not found: {version_b}"}

    files_a = {p.relative_to(path_a).as_posix() for p in path_a.rglob("*") if p.is_file()}
    files_b = {p.relative_to(path_b).as_posix() for p in path_b.rglob("*") if p.is_file()}
    added = sorted(files_b - files_a)
    removed = sorted(files_a - files_b)
    common = sorted(files_a & files_b)

    changed: list[str] = []
    for rel in common[:500]:
        a = _read_text_if_exists(path_a / rel)
        b = _read_text_if_exists(path_b / rel)
        if a != b:
            changed.append(rel)

    return {
        "ok": True,
        "version_a": version_a,
        "version_b": version_b,
        "added": added,
        "removed": removed,
        "changed": changed,
        "summary": {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
        },
    }
