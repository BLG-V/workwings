"""最小 SDK 示例：register_tool + register_agent。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from mawp.config.loader import load_config
from mawp.runtime.agent_runtime import AgentRuntime
from mawp.tools.registry import ToolRegistry


def main() -> int:
    plugin_path = ROOT / "apps" / "demo-code-agent" / "plugins" / "hello_plugin.py"
    spec = importlib.util.spec_from_file_location("hello_plugin", plugin_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    config = load_config(ROOT / "mawp.config.yaml.example")
    registry = ToolRegistry(config)
    runtime = AgentRuntime(config, registry=registry)
    mod.register(registry, runtime)

    tools = sorted(t.name for t in registry.list_tools())
    agents = sorted(runtime._specs.keys())  # noqa: SLF001 — 演示用
    print("tools:", ", ".join(tools))
    print("agents:", ", ".join(agents))
    assert "demo_version" in tools
    assert "demo_greeter" in agents
    print("OK: register_tool / register_agent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
