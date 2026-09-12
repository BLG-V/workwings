from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path

from mawp.security.policy import PolicyEngine

MAX_READ_BYTES = 512 * 1024
MAX_GREP_MATCHES = 200


def _rel_path(policy: PolicyEngine, path: Path) -> str:
    return path.relative_to(policy.workspace).as_posix()


def _read_text(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    if len(raw) > MAX_READ_BYTES:
        raw = raw[:MAX_READ_BYTES]
    for encoding in ("utf-8", "gbk", "latin-1"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8"


def read_file(
    policy: PolicyEngine,
    *,
    path: str,
    start_line: int | None = None,
    end_line: int | None = None,
) -> dict:
    resolved = policy.check_read(path)
    if not resolved.is_file():
        raise FileNotFoundError(f"文件不存在: {resolved}")

    content, encoding = _read_text(resolved)
    lines = content.splitlines(keepends=True)

    if start_line is not None or end_line is not None:
        s = max((start_line or 1) - 1, 0)
        e = end_line if end_line is not None else len(lines)
        lines = lines[s:e]
        content = "".join(lines)

    return {
        "path": _rel_path(policy, resolved),
        "content": content,
        "encoding": encoding,
        "line_count": len(content.splitlines()),
    }


def write_file(
    policy: PolicyEngine,
    *,
    path: str,
    content: str,
    dry_run: bool = False,
    agent_name: str = "coding",
) -> dict:
    resolved = policy.check_write(path, agent_name)
    existed = resolved.exists()
    previous = resolved.read_text(encoding="utf-8") if existed else ""

    if dry_run:
        return {
            "path": _rel_path(policy, resolved),
            "dry_run": True,
            "would_create": not existed,
            "previous_size": len(previous),
            "new_size": len(content),
        }

    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")
    return {
        "path": _rel_path(policy, resolved),
        "created": not existed,
        "bytes_written": len(content.encode("utf-8")),
    }


MAX_BATCH_FILES = 24


def write_files(
    policy: PolicyEngine,
    *,
    files: list[dict],
    dry_run: bool = False,
    agent_name: str = "coding",
) -> dict:
    """一次写入多个文件，降低大项目生成的工具往返次数。"""
    if not isinstance(files, list) or not files:
        raise ValueError("files 必须是非空数组，形如 [{path, content}, ...]")
    if len(files) > MAX_BATCH_FILES:
        raise ValueError(f"单次最多写入 {MAX_BATCH_FILES} 个文件，收到 {len(files)}")

    written: list[dict] = []
    for item in files:
        if not isinstance(item, dict):
            raise ValueError("files 中每一项必须是对象 {path, content}")
        path = str(item.get("path") or "").strip()
        content = item.get("content")
        if not path:
            raise ValueError("files[].path 不能为空")
        if content is None:
            raise ValueError(f"files[].content 缺失: {path}")
        result = write_file(
            policy,
            path=path,
            content=str(content),
            dry_run=dry_run,
            agent_name=agent_name,
        )
        written.append(result)

    return {
        "count": len(written),
        "dry_run": dry_run,
        "files": written,
        "paths": [f.get("path") for f in written],
    }


def edit_file(
    policy: PolicyEngine,
    *,
    path: str,
    old_string: str,
    new_string: str,
    agent_name: str = "coding",
) -> dict:
    resolved = policy.check_write(path, agent_name)
    if not resolved.is_file():
        raise FileNotFoundError(f"文件不存在: {resolved}")

    content, encoding = _read_text(resolved)
    count = content.count(old_string)
    if count == 0:
        norm_content = content.replace("\r\n", "\n")
        norm_old = old_string.replace("\r\n", "\n")
        norm_new = new_string.replace("\r\n", "\n")
        if norm_content.count(norm_old) == 0:
            raise ValueError("未找到要替换的内容")
        if norm_content.count(norm_old) > 1:
            raise ValueError(
                f"匹配到 {norm_content.count(norm_old)} 处，请提供更精确的 old_string"
            )
        updated = norm_content.replace(norm_old, norm_new, 1)
        resolved.write_text(updated, encoding="utf-8")
        return {
            "path": _rel_path(policy, resolved),
            "replacements": 1,
            "encoding": encoding,
        }
    if count > 1:
        raise ValueError(f"匹配到 {count} 处，请提供更精确的 old_string")

    updated = content.replace(old_string, new_string, 1)
    resolved.write_text(updated, encoding="utf-8")
    return {
        "path": _rel_path(policy, resolved),
        "replacements": 1,
        "encoding": encoding,
    }


def _should_skip_dir(name: str, exclude: set[str]) -> bool:
    if name in exclude:
        return True
    return name in {".git", "node_modules", "__pycache__", ".mawp"}


def list_dir(
    policy: PolicyEngine,
    *,
    path: str = ".",
    recursive: bool = False,
    exclude: list[str] | None = None,
) -> dict:
    resolved = policy.check_read(path)
    if not resolved.is_dir():
        raise NotADirectoryError(f"不是目录: {resolved}")

    skip = set(exclude or [])
    entries: list[dict] = []

    def walk(current: Path) -> None:
        for child in sorted(current.iterdir(), key=lambda p: p.name.lower()):
            rel = _rel_path(policy, child)
            if child.is_dir():
                entries.append({"path": rel, "type": "dir"})
                if recursive and not _should_skip_dir(child.name, skip):
                    walk(child)
            else:
                entries.append({"path": rel, "type": "file", "size": child.stat().st_size})

    walk(resolved)
    return {"path": _rel_path(policy, resolved), "entries": entries}


def glob_search(
    policy: PolicyEngine,
    *,
    pattern: str,
    exclude: list[str] | None = None,
) -> dict:
    skip = set(exclude or [])
    matches: list[str] = []

    for path in policy.workspace.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(policy.workspace)
        if any(part in skip for part in rel.parts):
            continue
        try:
            policy.check_read(str(rel))
        except Exception:
            continue
        if fnmatch.fnmatch(path.name, pattern) or fnmatch.fnmatch(rel.as_posix(), pattern):
            matches.append(rel.as_posix())

    matches.sort()
    return {"pattern": pattern, "matches": matches[:500]}


def grep(
    policy: PolicyEngine,
    *,
    pattern: str,
    path: str = ".",
    glob_pattern: str | None = None,
) -> dict:
    base = policy.check_read(path)
    regex = re.compile(pattern)
    results: list[dict] = []

    files: list[Path]
    if base.is_file():
        files = [base]
    else:
        files = [p for p in base.rglob("*") if p.is_file()]

    for file_path in files:
        rel = _rel_path(policy, file_path)
        if glob_pattern and not fnmatch.fnmatch(file_path.name, glob_pattern):
            continue
        try:
            policy.check_read(rel)
        except Exception:
            continue

        try:
            text, _ = _read_text(file_path)
        except OSError:
            continue

        for idx, line in enumerate(text.splitlines(), start=1):
            if regex.search(line):
                results.append({"path": rel, "line": idx, "text": line[:500]})
                if len(results) >= MAX_GREP_MATCHES:
                    return {"pattern": pattern, "matches": results, "truncated": True}

    return {"pattern": pattern, "matches": results, "truncated": False}
