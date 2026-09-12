from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from mawp.core.models import Workflow, WorkflowEdge, WorkflowNode


def load_workflow(path: Path | str) -> Workflow:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    suffix = file_path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        raw = yaml.safe_load(text) or {}
    elif suffix == ".json":
        import json

        raw = json.loads(text)
    else:
        # 默认按 YAML 解析
        raw = yaml.safe_load(text) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"工作流根节点必须是对象: {file_path}")
    return parse_workflow_dict(raw, source_path=str(file_path.resolve()))


def parse_workflow_dict(raw: dict[str, Any], *, source_path: str | None = None) -> Workflow:
    nodes_raw = raw.get("nodes") or []
    edges_raw = raw.get("edges") or []
    if not isinstance(nodes_raw, list) or not isinstance(edges_raw, list):
        raise ValueError("nodes/edges 必须是数组")

    nodes: list[WorkflowNode] = []
    for item in nodes_raw:
        if not isinstance(item, dict):
            raise ValueError("node 必须是对象")
        nodes.append(
            WorkflowNode(
                id=str(item.get("id", "")),
                type=str(item.get("type", "")),
                tool=item.get("tool"),
                agent=item.get("agent"),
                input=dict(item.get("input") or {}),
                raw=dict(item),
            )
        )

    edges: list[WorkflowEdge] = []
    for item in edges_raw:
        if not isinstance(item, dict):
            raise ValueError("edge 必须是对象")
        loop = bool(item.get("loop") or False)
        max_trav = item.get("max_traversals")
        if max_trav is not None:
            try:
                max_trav = int(max_trav)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"edge max_traversals 必须是整数: {item}") from exc
        edges.append(
            WorkflowEdge(
                from_id=str(item.get("from", "")),
                to_id=str(item.get("to", "")),
                when=item.get("when"),
                loop=loop,
                max_traversals=max_trav,
                raw=dict(item),
            )
        )

    default_loop_max = raw.get("default_loop_max", 3)
    try:
        default_loop_max = int(default_loop_max)
    except (TypeError, ValueError) as exc:
        raise ValueError("default_loop_max 必须是整数") from exc

    return Workflow(
        id=str(raw.get("id", "")),
        name=str(raw.get("name", "")),
        version=str(raw.get("version", "")),
        entry=str(raw.get("entry", "")),
        params=dict(raw.get("params") or {}),
        nodes=nodes,
        edges=edges,
        source_path=source_path,
        default_loop_max=default_loop_max,
        raw=dict(raw),
    )
