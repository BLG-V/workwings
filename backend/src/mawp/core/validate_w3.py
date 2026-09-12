"""W3 validation extensions: condition edge when + human_checkpoint fields."""

from __future__ import annotations

from mawp.core.models import Workflow


def validate_w3_nodes(workflow: Workflow) -> list[str]:
    """Extra checks aligned with docs/interfaces/w1-api-onepager.md §5."""
    errors: list[str] = []
    node_map = workflow.node_map()

    for node in workflow.nodes:
        if node.type == "human_checkpoint":
            reason = node.raw.get("reason")
            if not isinstance(reason, str) or not reason.strip():
                errors.append(
                    f"[node={node.id}] human_checkpoint 缺少必填字段 reason"
                )
            allowed = node.raw.get("allowed")
            if allowed is not None:
                if not isinstance(allowed, list) or not allowed:
                    errors.append(
                        f"[node={node.id}] allowed 必须是非空字符串数组"
                    )
                else:
                    for i, item in enumerate(allowed):
                        if not isinstance(item, str) or not item.strip():
                            errors.append(
                                f"[node={node.id}] allowed[{i}] 必须是非空字符串"
                            )

        if node.type == "condition":
            outs = workflow.outgoing(node.id)
            expr_edges = 0
            default_edges = 0
            for edge in outs:
                when = edge.when
                if when is None or when == "":
                    errors.append(
                        f"[node={node.id}] condition 出边缺少 when "
                        f"({edge.from_id} -> {edge.to_id})"
                    )
                    continue
                if when == "default":
                    default_edges += 1
                    continue
                if not isinstance(when, str):
                    errors.append(
                        f"[node={node.id}] when 必须是字符串或 default "
                        f"({edge.from_id} -> {edge.to_id})"
                    )
                    continue
                expr_edges += 1
                if edge.to_id not in node_map:
                    errors.append(
                        f"[node={node.id}] when 目标不存在: {edge.to_id}"
                    )
            if expr_edges < 1:
                errors.append(
                    f"[node={node.id}] condition 至少需要一条带表达式的出边"
                )
            if default_edges != 1:
                errors.append(
                    f"[node={node.id}] condition 必须恰好一条 when: default "
                    f"（当前 {default_edges}）"
                )

    return errors
