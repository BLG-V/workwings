from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


ALLOWED_NODE_TYPES = frozenset(
    {"start", "end", "tool", "agent", "condition", "human_checkpoint"}
)


@dataclass
class WorkflowNode:
    id: str
    type: str
    tool: str | None = None
    agent: str | None = None
    input: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowEdge:
    from_id: str
    to_id: str
    when: str | None = None
    # 显式回边（deliver Testing↔Debug）：loop=true + max_traversals 有限次数
    loop: bool = False
    max_traversals: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class Workflow:
    id: str
    name: str
    version: str
    entry: str
    params: dict[str, Any] = field(default_factory=dict)
    nodes: list[WorkflowNode] = field(default_factory=list)
    edges: list[WorkflowEdge] = field(default_factory=list)
    source_path: str | None = None
    # 工作流级默认：回边最大穿越次数（可被边 max_traversals 覆盖）
    default_loop_max: int = 3
    raw: dict[str, Any] = field(default_factory=dict)

    def node_map(self) -> dict[str, WorkflowNode]:
        return {n.id: n for n in self.nodes}

    def outgoing(self, node_id: str) -> list[WorkflowEdge]:
        return [e for e in self.edges if e.from_id == node_id]
