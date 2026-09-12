from __future__ import annotations

import re
from typing import Any

_PARAM_VAR = re.compile(r"\$\{(params|vars)\.([A-Za-z0-9_]+)\}")
_NODE_OUT = re.compile(r"\$\{nodes\.([A-Za-z0-9_]+)\.outputs\.([A-Za-z0-9_]+)\}")


def render_value(
    value: Any,
    *,
    params: dict[str, Any],
    nodes_outputs: dict[str, dict[str, Any]],
    vars: dict[str, Any] | None = None,
) -> Any:
    vars_map = vars or {}
    if isinstance(value, str):
        return _render_string(
            value, params=params, nodes_outputs=nodes_outputs, vars=vars_map
        )
    if isinstance(value, list):
        return [
            render_value(v, params=params, nodes_outputs=nodes_outputs, vars=vars_map)
            for v in value
        ]
    if isinstance(value, dict):
        return {
            k: render_value(v, params=params, nodes_outputs=nodes_outputs, vars=vars_map)
            for k, v in value.items()
        }
    return value


def _render_string(
    text: str,
    *,
    params: dict[str, Any],
    nodes_outputs: dict[str, dict[str, Any]],
    vars: dict[str, Any],
) -> str:
    def repl_param(match: re.Match[str]) -> str:
        kind, key = match.group(1), match.group(2)
        source = params if kind == "params" else vars
        if key not in source:
            raise KeyError(f"模板变量不存在: {kind}.{key}")
        return str(source[key])

    def repl_node(match: re.Match[str]) -> str:
        node_id, key = match.group(1), match.group(2)
        outputs = nodes_outputs.get(node_id) or {}
        if key not in outputs:
            raise KeyError(f"模板变量不存在: nodes.{node_id}.outputs.{key}")
        return str(outputs[key])

    out = _PARAM_VAR.sub(repl_param, text)
    out = _NODE_OUT.sub(repl_node, out)
    return out
