from __future__ import annotations

from mawp.core.models import ALLOWED_NODE_TYPES, Workflow, WorkflowEdge
from mawp.core.validate_w3 import validate_w3_nodes


def validate_workflow(workflow: Workflow) -> list[str]:
    errors: list[str] = []

    for field in ("id", "name", "version", "entry"):
        if not getattr(workflow, field):
            errors.append(f"缺少必填字段: {field}")

    if not workflow.nodes:
        errors.append("nodes 不能为空")

    ids = [n.id for n in workflow.nodes]
    if any(not i for i in ids):
        errors.append("存在空的 node.id")
    seen: set[str] = set()
    for nid in ids:
        if not nid:
            continue
        if nid in seen:
            errors.append(f"重复的 node.id: {nid}")
        seen.add(nid)

    starts = [n for n in workflow.nodes if n.type == "start"]
    ends = [n for n in workflow.nodes if n.type == "end"]
    if len(starts) != 1:
        errors.append(f"必须恰好有 1 个 start 节点，当前 {len(starts)} 个")
    if len(ends) < 1:
        errors.append("至少需要 1 个 end 节点")

    node_map = workflow.node_map()
    if workflow.entry and workflow.entry not in node_map:
        errors.append(f"entry 指向不存在的节点: {workflow.entry}")
    elif workflow.entry and node_map[workflow.entry].type != "start":
        errors.append(f"entry 必须指向 start 节点: {workflow.entry}")

    for node in workflow.nodes:
        if node.type not in ALLOWED_NODE_TYPES:
            errors.append(f"未知节点类型: {node.id}.type={node.type}")
        if node.type == "tool" and not node.tool:
            errors.append(f"tool 节点缺少 tool 字段: {node.id}")
        if node.type == "agent" and not node.agent:
            errors.append(f"agent 节点缺少 agent 字段: {node.id}")

    for edge in workflow.edges:
        if not edge.from_id or not edge.to_id:
            errors.append("边缺少 from/to")
            continue
        if edge.from_id not in node_map:
            errors.append(f"边 from 不存在: {edge.from_id}")
        if edge.to_id not in node_map:
            errors.append(f"边 to 不存在: {edge.to_id}")
        if edge.from_id == edge.to_id:
            errors.append(f"禁止自环: {edge.from_id}")
        if edge.loop and edge.max_traversals is not None and edge.max_traversals < 1:
            errors.append(
                f"loop 边 max_traversals 须 ≥ 1: {edge.from_id} -> {edge.to_id}"
            )

    # 非 end 须有出边
    for node in workflow.nodes:
        if node.type == "end":
            continue
        if not workflow.outgoing(node.id):
            errors.append(f"非 end 节点缺少出边: {node.id}")

    # 环检测：默认拒绝；显式 loop 回边允许（deliver Testing↔Debug）
    cycle = _find_cycle(workflow)
    if cycle:
        if not _cycle_allowed(workflow, cycle):
            errors.append(
                "检测到环: "
                + " -> ".join(cycle)
                + "（若为 deliver 回边，请在回边上标注 loop: true，"
                "并设置 max_traversals 或 default_loop_max）"
            )

    # W3：condition / human_checkpoint
    errors.extend(validate_w3_nodes(workflow))

    return errors


def _edge_key(edge: WorkflowEdge) -> tuple[str, str, str | None]:
    return (edge.from_id, edge.to_id, edge.when)


def _cycle_allowed(workflow: Workflow, cycle: list[str]) -> bool:
    """cycle 形如 [a, b, c, a]；要求环上至少一条显式 loop 边，且有限次数。"""
    if len(cycle) < 2:
        return False
    pairs = list(zip(cycle[:-1], cycle[1:]))
    loop_edges: list[WorkflowEdge] = []
    for frm, to in pairs:
        matched = [
            e for e in workflow.edges if e.from_id == frm and e.to_id == to and e.loop
        ]
        loop_edges.extend(matched)
    if not loop_edges:
        return False
    for e in loop_edges:
        limit = e.max_traversals if e.max_traversals is not None else workflow.default_loop_max
        if limit is None or int(limit) < 1:
            return False
    return True


def _find_cycle(workflow: Workflow) -> list[str] | None:
    graph = {n.id: [e.to_id for e in workflow.outgoing(n.id)] for n in workflow.nodes}
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def dfs(node: str) -> list[str] | None:
        visiting.add(node)
        stack.append(node)
        for nxt in graph.get(node, []):
            if nxt in visiting:
                if nxt in stack:
                    i = stack.index(nxt)
                    return stack[i:] + [nxt]
                return [node, nxt]
            if nxt not in visited:
                found = dfs(nxt)
                if found:
                    return found
        stack.pop()
        visiting.remove(node)
        visited.add(node)
        return None

    for nid in graph:
        if nid not in visited:
            found = dfs(nid)
            if found:
                return found
    return None
