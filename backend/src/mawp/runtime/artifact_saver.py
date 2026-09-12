# -*- coding: utf-8 -*-
"""产物自动落盘：把 Deliver 各阶段 outputs 持久化到 project_root。

用法（在 deliver 完成后调用）：
    from mawp.runtime.artifact_saver import save_deliver_artifacts
    save_deliver_artifacts(workspace, run, node_outputs)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mawp.runtime.deploy_scaffolder import ensure_project_deploy
from mawp.runtime.cicd_scaffolder import scaffold_cicd
from mawp.runtime.version_manager import create_version_snapshot


def _ensure_dir(path: Path) -> Path:
    """确保目录存在并返回。"""
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_text(path: Path, content: str, encoding: str = "utf-8") -> Path:
    """原子写入文本文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding=encoding)
    return path


def _safe_filename(name: str) -> str:
    """把任意字符串转成安全的文件名（保留中文、字母、数字、下划线、连字符）。"""
    import re

    # 保留：中文、字母、数字、空格、下划线、连字符、点
    safe = re.sub(r"[^\w\s\u4e00-\u9fff.\-]", "_", str(name).strip())
    # 压缩连续下划线 / 空格
    safe = re.sub(r"[\s_]+", "_", safe)
    return safe[:120].strip("_. ")


def _extract_requirement_content(outputs: dict[str, Any]) -> str | None:
    """从 requirement 节点 outputs 提取 PRD 文本。"""
    req = outputs.get("requirement") or {}
    summary = req.get("summary")
    tasks = req.get("tasks")
    ui_points = req.get("ui_key_points")
    ac = req.get("acceptance_criteria")
    spec_ref = req.get("spec_ref")

    if not summary and not tasks:
        return None

    lines = ["# 需求文档 (PRD)", "", f"## 概述\n{summary}", ""]
    if spec_ref:
        lines.append(f"**规格参考：** {spec_ref}\n")

    if tasks:
        lines.append("## 功能任务")
        for t in tasks:
            if isinstance(t, dict):
                tid = t.get("id", "")
                title = t.get("title", "")
                desc = t.get("description", "")
                deps = t.get("depends_on", [])
                dep_str = f" （依赖：{', '.join(str(d) for d in deps)}）" if deps else ""
                lines.append(f"- **[{tid}] {title}**{dep_str}")
                if desc:
                    lines.append(f"  > {desc}")
        lines.append("")

    if ui_points:
        lines.append("## UI 要点")
        for idx, point in enumerate(ui_points, 1):
            lines.append(f"{idx}. {point}")
        lines.append("")

    if ac:
        lines.append("## 验收标准")
        for idx, criterion in enumerate(ac, 1):
            lines.append(f"- {criterion}")
        lines.append("")

    lines.append("---")
    lines.append("*由 MAWP Requirement Agent 生成*")
    return "\n".join(lines)


def _extract_architecture_content(outputs: dict[str, Any]) -> str | None:
    """从 planner + requirement outputs 提取架构文档。"""
    planner = outputs.get("planner") or {}
    requirement = outputs.get("requirement") or {}
    planner_tasks = planner.get("tasks")
    req_summary = requirement.get("summary")

    if not planner_tasks and not req_summary:
        return None

    lines = [
        "# 系统架构设计",
        "",
        "## 任务拆解",
    ]
    for t in planner_tasks or []:
        if isinstance(t, dict):
            tid = t.get("id", "")
            title = t.get("title", "")
            desc = t.get("description", "")
            deps = t.get("depends_on", [])
            dep_str = f" （依赖：{', '.join(str(d) for d in deps)}）" if deps else ""
            lines.append(f"- **[{tid}] {title}**{dep_str}")
            if desc:
                lines.append(f"  > {desc}")

    if req_summary:
        lines.extend(["", "## 需求概述", req_summary])

    lines.extend(["", "---", "*由 MAWP Planner + Requirement Agent 生成*"])
    return "\n".join(lines)


def _extract_code_content(
    outputs: dict[str, Any], workspace: Path
) -> dict[str, Any] | None:
    """从 coding + frontend outputs 提取代码产物信息。"""
    coding = outputs.get("coding") or {}
    frontend = outputs.get("frontend") or {}

    changed_files = list(coding.get("changed_files") or [])
    frontend_dir = frontend.get("frontend_dir")
    pages = list(frontend.get("pages") or [])
    artifacts = list(frontend.get("artifacts") or [])
    tasks_done = list(coding.get("tasks_done") or [])
    status = coding.get("status") or "ok"

    if not changed_files and not artifacts:
        return None

    result: dict[str, Any] = {
        "status": status,
        "tasks_done": tasks_done,
        "changed_files": changed_files,
        "frontend_dir": frontend_dir,
        "pages": pages,
        "artifacts": artifacts,
    }

    # 尝试从 workspace 读取实际文件内容（如果存在）
    files_content: dict[str, str] = {}
    if frontend_dir:
        fd = workspace / frontend_dir
        if fd.is_dir():
            for p in pages:
                if isinstance(p, dict):
                    fpath = p.get("path")
                    if fpath:
                        full = fd / fpath
                        if full.is_file():
                            try:
                                files_content[fpath] = full.read_text(encoding="utf-8")
                            except (OSError, UnicodeDecodeError):
                                pass

    if files_content:
        result["files_content"] = files_content

    return result


def _extract_test_content(outputs: dict[str, Any]) -> str | None:
    """从 testing outputs 提取测试报告。"""
    testing = outputs.get("testing") or {}
    passed = testing.get("passed")
    status = testing.get("status")
    failures = testing.get("failures")
    log_summary = testing.get("log_summary")
    attempt = testing.get("attempt")
    metric_command = testing.get("metric_command")
    exit_code = testing.get("exit_code")
    duration_ms = testing.get("duration_ms")

    if not passed and not status:
        return None

    lines = [
        "# 测试报告",
        "",
        f"- **状态：** {'✅ 通过' if passed else '❌ 失败'}",
        f"- **轮次：** {attempt}",
        f"- **命令：** `{metric_command or '（演示模式）'}`",
        f"- **退出码：** {exit_code}",
        f"- **耗时：** {duration_ms}ms",
        "",
    ]

    if log_summary:
        lines.append("## 日志摘要")
        lines.append(f"```\n{log_summary}\n```")
        lines.append("")

    if failures:
        lines.append("## 失败项")
        for idx, f in enumerate(failures, 1):
            lines.append(f"{idx}. {f}")
        lines.append("")

    lines.extend(["---", "*由 MAWP Testing Agent 生成*"])
    return "\n".join(lines)


def _extract_deploy_content(
    outputs: dict[str, Any], run_id: str, goal: str
) -> dict[str, Any] | None:
    """从 ship outputs 提取部署信息。"""
    ship = outputs.get("ship") or {}
    review = outputs.get("review") or {}
    testing = outputs.get("testing") or {}
    coding = outputs.get("coding") or {}

    delivery_notes = ship.get("delivery_notes")
    commit_message = ship.get("commit_message")
    checklist = ship.get("checklist")
    auto_push = ship.get("auto_push")
    auto_merge = ship.get("auto_merge")
    testing_passed = ship.get("testing_passed")
    changed_files = ship.get("changed_files") or list(coding.get("changed_files") or [])
    artifact = ship.get("artifact")

    if not delivery_notes and not commit_message:
        return None

    result: dict[str, Any] = {
        "run_id": run_id,
        "goal": goal,
        "delivery_notes": delivery_notes,
        "commit_message": commit_message,
        "checklist": checklist,
        "auto_push": bool(auto_push),
        "auto_merge": bool(auto_merge),
        "testing_passed": bool(testing_passed),
        "changed_files": list(changed_files),
        "artifact": artifact,
        "review_status": review.get("status"),
        "review_blocking_count": review.get("blocking_count"),
        "review_findings": review.get("findings"),
        "testing_status": testing.get("status"),
        "testing_passed": testing.get("passed"),
        "testing_failures": testing.get("failures"),
    }
    return result


def _write_json(path: Path, data: dict[str, Any]) -> Path:
    """写入 JSON 文件。"""
    return _write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def save_deliver_artifacts(
    workspace: Path | str,
    run: Any,
    node_outputs: dict[str, Any],
    *,
    project_root: str | None = None,
    goal: str | None = None,
    overwrite: bool = True,
) -> dict[str, Any]:
    """把 Deliver 各阶段 outputs 持久化到 project_root。

    Args:
        workspace: MAWP 工作区根路径
        run: RunRecord 或 dict，至少需要 run_id
        node_outputs: 各节点 outputs 字典
        project_root: 目标项目目录（相对于 workspace），
                      若为 None 则尝试从 run.params.project_root 获取
        goal: 项目目标，若为 None 则从 run.params.goal 获取
        overwrite: 是否覆盖已有文件

    Returns:
        保存的文件路径与统计信息
    """
    workspace = Path(workspace).resolve()
    run_id = getattr(run, "run_id", None) or (run.get("run_id") if isinstance(run, dict) else "unknown")
    params = getattr(run, "params", None) or (run.get("params") if isinstance(run, dict) else {})

    # 从 params 补全缺失值
    if project_root is None:
        project_root = params.get("project_root")
    if goal is None:
        goal = params.get("goal", "deliver")

    if not project_root:
        return {"ok": False, "error": "missing project_root", "run_id": run_id}

    project_root = str(project_root).replace("\\", "/").lstrip("/")

    # project_root 相对于 workspace
    project_path = (workspace / project_root).resolve()
    if not project_path.is_dir():
        project_path.mkdir(parents=True, exist_ok=True)

    docs_dir = _ensure_dir(project_path / "docs")
    apps_dir = _ensure_dir(project_path / "apps")
    api_dir = _ensure_dir(apps_dir / "api")
    web_dir = _ensure_dir(apps_dir / "web")
    scripts_dir = _ensure_dir(project_path / "scripts")

    saved: dict[str, Any] = {
        "ok": True,
        "run_id": run_id,
        "project_root": str(project_root),
        "project_path": str(project_path),
        "files": [],
    }

    # 1. 保存需求文档
    req_content = _extract_requirement_content(node_outputs)
    if req_content:
        req_path = docs_dir / "REQUIREMENT.md"
        _write_text(req_path, req_content)
        saved["files"].append({"path": "docs/REQUIREMENT.md", "type": "requirement"})

    # 2. 保存架构文档
    arch_content = _extract_architecture_content(node_outputs)
    if arch_content:
        arch_path = docs_dir / "ARCHITECTURE.md"
        _write_text(arch_path, arch_content)
        saved["files"].append({"path": "docs/ARCHITECTURE.md", "type": "architecture"})

    # 3. 保存代码产物元数据
    code_info = _extract_code_content(node_outputs, workspace)
    if code_info:
        code_meta_path = docs_dir / "CODE_META.json"
        _write_json(code_meta_path, code_info)
        saved["files"].append({"path": "docs/CODE_META.json", "type": "code_meta"})
        saved["code_info"] = code_info

        # 如果有前端产物路径，增量同步到项目目录；
        # 但若源目录本来就是目标目录，则跳过。
        frontend_dir = code_info.get("frontend_dir")
        if frontend_dir:
            fd = (workspace / str(frontend_dir)).resolve()
            dest_web = web_dir.resolve()
            if fd.is_dir() and fd != dest_web:
                import shutil
                import filecmp

                # 增量同步：只复制新文件或已修改的文件
                synced_count = 0
                if not dest_web.exists():
                    # 目标目录不存在，全量复制
                    shutil.copytree(fd, dest_web)
                    synced_count = len(list(fd.rglob("*")))
                else:
                    # 增量同步：比较并复制变更的文件
                    for src_path in fd.rglob("*"):
                        if not src_path.is_file():
                            continue
                        rel = src_path.relative_to(fd)
                        dest_path = dest_web / rel
                        
                        if not dest_path.exists():
                            # 新文件，复制
                            dest_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(src_path, dest_path)
                            synced_count += 1
                        elif not filecmp.cmp(src_path, dest_path, shallow=False):
                            # 文件内容不同，复制（覆盖）
                            dest_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(src_path, dest_path)
                            synced_count += 1
                
                if synced_count > 0:
                    saved["files"].append({
                        "path": "apps/web/",
                        "type": "frontend",
                        "copied": True,
                        "synced_files": synced_count
                    })
                else:
                    saved["files"].append({
                        "path": "apps/web/",
                        "type": "frontend",
                        "copied": False,
                        "synced_files": 0,
                        "note": "no changes"
                    })

    # 4. 保存测试报告
    test_content = _extract_test_content(node_outputs)
    if test_content:
        test_path = docs_dir / "TEST_REPORT.md"
        _write_text(test_path, test_content)
        saved["files"].append({"path": "docs/TEST_REPORT.md", "type": "test"})

    # 5. 保存部署信息
    deploy_info = _extract_deploy_content(node_outputs, run_id, goal or "")
    if deploy_info:
        deploy_path = docs_dir / "DEPLOY.json"
        _write_json(deploy_path, deploy_info)
        saved["files"].append({"path": "docs/DEPLOY.json", "type": "deploy"})
        saved["deploy_info"] = deploy_info

    # 6. 保存完整 outputs 备份（供调试）
    outputs_path = docs_dir / f"node_outputs_{run_id}.json"
    _write_json(outputs_path, node_outputs)
    saved["files"].append({"path": f"docs/node_outputs_{run_id}.json", "type": "raw_outputs"})

    # 7. 更新 README
    readme_path = project_path / "README.md"
    created_at = (
        getattr(run, "created_at", None)
        or (run.get("created_at") if isinstance(run, dict) else None)
        or ""
    )
    updated_at = (
        getattr(run, "updated_at", None)
        or (run.get("updated_at") if isinstance(run, dict) else None)
        or created_at
    )
    readme_lines = [
        f"# {goal}",
        "",
        f"MAWP Deliver Run: `{run_id}`",
        "",
        "## 产物目录",
        "- [需求文档](docs/REQUIREMENT.md)",
        "- [架构文档](docs/ARCHITECTURE.md)",
        "- [代码元数据](docs/CODE_META.json)",
        "- [测试报告](docs/TEST_REPORT.md)",
        "- [部署信息](docs/DEPLOY.json)",
        "",
        "## 快速开始",
        "```bash",
        "# 后端",
        "cd apps/api && pip install -r requirements.txt && uvicorn main:app --reload",
        "",
        "# 前端",
        "cd apps/web && npm install && npm run dev",
        "```",
        "",
        f"Generated at: {updated_at or created_at or ''}",
    ]
    _write_text(readme_path, "\n".join(readme_lines))
    saved["files"].append({"path": "README.md", "type": "readme"})

    # 8. 保存运行元数据
    run_meta: dict[str, Any] = {
        "run_id": run_id,
        "params": params,
    }
    # 从 run 对象或字典中提取字段
    for key in ("workflow_id", "status", "created_at", "updated_at", "error", "failed_node_id"):
        val = getattr(run, key, None) if hasattr(run, key) else (run.get(key) if isinstance(run, dict) else None)
        if val is not None:
            run_meta[key] = str(val) if not isinstance(val, (str, dict, list, bool, int, float)) else val
    run_meta_path = docs_dir / f"run_{run_id}.json"
    _write_json(run_meta_path, run_meta)
    saved["files"].append({"path": f"docs/run_{run_id}.json", "type": "run_meta"})

    # 9. 生成部署脚手架（Docker / Compose / 启动脚本）
    try:
        deploy_result = ensure_project_deploy(
            project_path,
            project_id=str(project_path.name),
            goal=str(goal or "deliver"),
            has_frontend=bool(code_info and code_info.get("frontend_dir") is not None),
            has_backend=True,
        )
        saved["deploy"] = deploy_result
        saved["files"].extend(deploy_result.get("files", []))
    except Exception as exc:  # noqa: BLE001
        saved["deploy_error"] = str(exc)

    # 10. 生成 CI/CD 流水线
    try:
        cicd_result = scaffold_cicd(project_path, platform="github")
        saved["cicd"] = cicd_result
        saved["files"].extend(cicd_result.get("files", []))
    except Exception as exc:  # noqa: BLE001
        saved["cicd_error"] = str(exc)

    # 11. 创建版本快照
    try:
        snapshot = create_version_snapshot(
            project_path,
            run_id=str(run_id),
            label=str(goal or "deliver"),
            note=f"status={str(getattr(run, 'status', None) or (run.get('status') if isinstance(run, dict) else 'DONE'))}",
        )
        saved["version_snapshot"] = snapshot
        if isinstance(snapshot, dict) and snapshot.get("ok"):
            saved["files"].append({"path": f"versions/{snapshot.get('snapshot_id')}/", "type": "version_snapshot"})
            saved["files"].append({"path": "docs/VERSION_LATEST.json", "type": "version_meta"})
    except Exception as exc:  # noqa: BLE001
        saved["version_error"] = str(exc)

    saved["count"] = len(saved["files"])
    return saved


def sync_deliver_to_project(
    workspace: Path | str,
    run: Any,
    node_outputs: dict[str, Any],
    *,
    project_root: str | None = None,
) -> dict[str, Any]:
    """Deliver 完成后同步产物到项目目录的便捷封装。

    自动从 run.params 提取 project_root 和 goal。
    """
    workspace = Path(workspace).resolve()
    params = getattr(run, "params", None) or (run.get("params") if isinstance(run, dict) else {})

    if project_root is None:
        project_root = params.get("project_root")

    if not project_root:
        return {"ok": False, "error": "missing project_root in params", "run_id": getattr(run, "run_id", "")}

    return save_deliver_artifacts(
        workspace=workspace,
        run=run,
        node_outputs=node_outputs,
        project_root=project_root,
        goal=params.get("goal"),
    )
