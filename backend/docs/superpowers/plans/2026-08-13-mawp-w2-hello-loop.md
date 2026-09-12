# MAWP W2 主路径周 — hello 闭环 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 打通 `platform validate` + `platform run` 最小闭环：hello 流（start→echo→end）可校验、可执行、Run 落盘到 `.mawp/`，exit code 符合接口一页纸。

**Architecture:** `core` 负责加载/校验/按边调度；`tools.echo` 经 ToolRegistry 执行；`storage` 写 Run JSON 与事件 JSONL；CLI 只做参数与退出码。W2 不实现 condition/human/agent 节点（遇到则 FAILED 并提示）。

**Tech Stack:** Python 3.11+、PyYAML、Typer、现有 ToolRegistry / PolicyEngine

**Spec:** `docs/superpowers/specs/2026-08-13-mawp-design.md` §5；`docs/interfaces/w1-api-onepager.md`

**Out of scope:** condition、human_checkpoint、真 LLM、SDK/App、cancel/timeout

---

## File map

| 文件 | 职责 |
|------|------|
| `src/mawp/core/models.py` | Workflow / Node / Edge / ValidationError |
| `src/mawp/core/loader.py` | YAML/JSON → Workflow |
| `src/mawp/core/validate.py` | 静态校验 |
| `src/mawp/core/template.py` | `${params.x}` / `${nodes.id.outputs.k}` |
| `src/mawp/core/engine.py` | 执行与状态推进 |
| `src/mawp/storage/store.py` | `.mawp/runs` + `.mawp/events` |
| `src/mawp/tools/echo_tools.py` | echo 安全回显 |
| `src/mawp/tools/registry.py` | 注册 echo |
| `src/mawp/cli/main.py` | validate / run / run status |
| `tests/unit/test_workflow_core.py` | 校验与模板 |
| `tests/unit/test_workflow_engine.py` | hello 执行 |
| `tests/unit/test_echo_tool.py` | echo |

---

### Task 1: Schema 模型 + 加载 + 校验（TDD）

**Files:**
- Create: `src/mawp/core/models.py`, `loader.py`, `validate.py`
- Test: `tests/unit/test_workflow_core.py`

- [ ] **Step 1: 写失败测试**

```python
from pathlib import Path
from mawp.core.loader import load_workflow
from mawp.core.validate import validate_workflow

def test_hello_workflow_validates(tmp_path: Path):
    src = Path("examples/hello-workflow/workflow.yaml")
    wf = load_workflow(src)
    errors = validate_workflow(wf)
    assert errors == []

def test_missing_entry_fails(tmp_path: Path):
    p = tmp_path / "bad.yaml"
    p.write_text("id: x\nname: x\nversion: '1'\nentry: nope\nnodes: []\nedges: []\n", encoding="utf-8")
    wf = load_workflow(p)
    errors = validate_workflow(wf)
    assert any("entry" in e.lower() or "nope" in e for e in errors)
```

- [ ] **Step 2: 运行确认失败** — `pytest tests/unit/test_workflow_core.py -q` → ImportError

- [ ] **Step 3: 实现 models / loader / validate**

校验规则（失败即错误字符串列表）：
- 必填：`id,name,version,entry,nodes,edges`
- 节点 `id` 唯一；`type` ∈ {start,end,tool,agent,condition,human_checkpoint}
- 恰好一个 `start`；至少一个 `end`；`entry` 指向存在的 start 节点
- `tool` 节点必须有 `tool` 字段
- 边 `from`/`to` 必须指向已有节点；拒绝自环与任意环（DFS）
- 悬空：非 end 节点必须有出边；start 必须有出边

- [ ] **Step 4: 测试通过并 commit**

---

### Task 2: 模板替换 + echo Tool

**Files:**
- Create: `src/mawp/core/template.py`, `src/mawp/tools/echo_tools.py`
- Modify: `src/mawp/tools/registry.py`
- Test: `tests/unit/test_echo_tool.py`（可并入 core 测试）

- [ ] **Step 1: 模板**

```python
def render_value(value, *, params: dict, nodes_outputs: dict, vars: dict | None = None):
    # 递归处理 dict/list/str；字符串替换 ${params.a} ${nodes.n.outputs.k} ${vars.x}
```

- [ ] **Step 2: echo**

```python
def echo(policy, *, text: str = "") -> dict:
    return {"text": str(text)}
```

注册：`allowed_agents={"workflow", "coding", "requirement", "testing", "review"}`（引擎用 `agent_name="workflow"`）。

- [ ] **Step 3: 测试 echo execute 成功**

---

### Task 3: storage + engine

**Files:**
- Create: `src/mawp/storage/store.py`, `src/mawp/core/engine.py`
- Test: `tests/unit/test_workflow_engine.py`

- [ ] **Step 1: RunStore**

根目录：`workspace/.mawp/`  
- `runs/<run_id>.json`：`run_id, workflow_id, status, current_node_id, params, node_outputs, failed_node_id, error, created_at, updated_at`  
- `events/<run_id>.jsonl`：一行一个事件  

`run_id` 用 `uuid4().hex[:12]`。

- [ ] **Step 2: Engine.run(workflow, config, params_override=None) -> RunRecord**

状态：INIT→RUNNING→DONE/FAILED  
节点：
- `start`：记事件，沿唯一出边前进  
- `tool`：render input → `ToolRegistry.execute` → 写入 `node_outputs[node_id]`；失败则 FAILED  
- `end`：DONE  
- 其他 type：FAILED（W2 未实现）

- [ ] **Step 3: 用 hello-workflow 测 DONE 且 outputs.echo1.text 含 hello world**

---

### Task 4: CLI 接线

**Files:**
- Modify: `src/mawp/cli/main.py`
- Modify: `examples/hello-workflow/README.md`

- [ ] **Step 1: `_get_context` 向上查找 parent.obj**

- [ ] **Step 2: `validate` 调 validate_workflow；有错误打印并 exit 1；成功 exit 0**

- [ ] **Step 3: `run` 改为 typer 子应用**

- `platform run <workflow.yaml>` → Engine；成功打印 run_id/status；DONE→0，否则→1  
- `platform run status <run_id>` → 读存储；找不到→1

- [ ] **Step 4: 手动冒烟**

```bash
platform validate examples/hello-workflow/workflow.yaml
platform run examples/hello-workflow/workflow.yaml
platform run status <run_id>
```

- [ ] **Step 5: commit + push**

---

## Spec coverage

| 项 | 任务 |
|----|------|
| validate exit 约定 | Task 4 |
| run hello + echo | Task 2–4 |
| `.mawp` 持久化 | Task 3 |
| mock LLM | 不需要（hello 无 agent 节点） |
| condition/human | Out of scope → W3 |
