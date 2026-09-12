from __future__ import annotations

import fnmatch


def normalize_rel_path(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def is_test_path(rel_path: str) -> bool:
    normalized = normalize_rel_path(rel_path)
    if normalized.startswith("tests/"):
        return True
    if normalized.startswith("test_") and normalized.endswith(".py"):
        return True
    return "/tests/" in normalized or normalized.endswith("_test.py")


def path_matches_scope(rel_path: str, scope_entry: str) -> bool:
    normalized = normalize_rel_path(rel_path)
    scope = normalize_rel_path(scope_entry)
    if not scope:
        return False
    if normalized == scope:
        return True
    if fnmatch.fnmatch(normalized, scope):
        return True
    scope_dir = scope.rstrip("/")
    if normalized.startswith(scope_dir + "/"):
        return True
    return False


def path_in_write_scope(
    rel_path: str,
    scope_files: list[str],
    *,
    deny_files: list[str] | None = None,
    allow_tests: bool = True,
) -> bool:
    normalized = normalize_rel_path(rel_path)

    for denied in deny_files or []:
        if path_matches_scope(normalized, denied):
            return False

    if allow_tests and is_test_path(normalized):
        return True

    if not scope_files:
        return False

    return any(path_matches_scope(normalized, scope) for scope in scope_files)


def valid_scope_files(paths: list[str]) -> list[str]:
    """过滤 Issue 中的占位符路径。"""
    invalid = {"（实现时确定）", "（待补充）", ""}
    return [p for p in paths if p and p not in invalid and not p.startswith("（")]
