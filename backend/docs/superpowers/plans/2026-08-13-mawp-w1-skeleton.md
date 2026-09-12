# MAWP W1 对齐周 — 改名骨架 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把已复制的 AI Code Agent 基线改成可安装的 `mawp` 包与 `platform` CLI，并落下 `core/storage/sdk/apps` 空骨架与 hello 样例草案，为 W2 引擎闭环做准备。

**Architecture:** 机械重命名 `src/agent` → `src/mawp`，配置/存储默认路径切到 `.mawp/`；旧 Goal/gstack/autoresearch 代码保留在包内但不作为本周主交付；新建空包与接口说明，不实现执行引擎。

**Tech Stack:** Python ≥3.11、Typer、Pydantic、PyYAML、hatchling、pytest

**Spec:** `docs/superpowers/specs/2026-08-13-mawp-design.md` §2、§4

**Out of scope (W2+):** YAML 校验/执行引擎、echo Tool 业务闭环、Human approve、SDK register、App 装卸

---

## File structure (W1 锁定)

| 路径 | 职责 |
|------|------|
| `src/mawp/` | 唯一 Python 包根（由 `src/agent/` 重命名） |
| `src/mawp/core/` | 工作流引擎占位（W2 实现） |
| `src/mawp/storage/` | Run/Session/事件存储占位 |
| `src/mawp/sdk/` | register_tool/agent 占位 |
| `src/mawp/apps/` | App 装载占位 |
| `src/mawp/runtime/` | AgentRuntime 占位（W2–W3） |
| `src/mawp/cli/main.py` | `platform` 入口；保留旧子命令以便测试暂不崩 |
| `mawp.config.yaml.example` | 新配置示例 |
| `examples/hello-workflow/workflow.yaml` | W2 样例草案 |
| `docs/interfaces/w1-api-onepager.md` | 冻结接口一页纸（摘自规格） |
| `pyproject.toml` | `name=mawp`，`scripts.platform` |

---

### Task 1: 包目录重命名 + pyproject

**Files:**
- Rename: `src/agent/` → `src/mawp/`
- Modify: `pyproject.toml`
- Modify: `.gitignore`

- [ ] **Step 1: 重命名目录**

```powershell
cd "d:\专高六项目\多Agent工作流平台"
Move-Item -LiteralPath "src\agent" -Destination "src\mawp"
```

Expected: `src/mawp/cli/main.py` 存在；`src/agent` 不存在。

- [ ] **Step 2: 更新 `pyproject.toml`**

将项目元数据与入口改为：

```toml
[project]
name = "mawp"
version = "0.1.0"
description = "MAWP — 多 Agent 工作流平台（可安装通用内核 + SDK/App）"
readme = "README.md"
requires-python = ">=3.11"
# dependencies 保持不变

[project.scripts]
platform = "mawp.cli.main:main"
# 过渡期可选保留旧入口，W1 推荐只留 platform：
# agent = "mawp.cli.main:main"

[tool.hatch.build.targets.wheel]
packages = ["src/mawp"]

[tool.hatch.build.targets.wheel.force-include]
"src/mawp/api/static" = "mawp/api/static"

[tool.hatch.build.targets.sdist]
packages = ["src/mawp"]
```

- [ ] **Step 3: 更新 `.gitignore`**

确保包含：

```gitignore
.mawp/
mawp.config.yaml
.agent/
agent.config.yaml
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: rename package agent to mawp and update pyproject"
```

---

### Task 2: 全库 import 与字符串替换

**Files:**
- Modify: 所有 `src/mawp/**/*.py`、`tests/**/*.py`、`scripts/**/*.py` 中的 `agent` 包引用

- [ ] **Step 1: 用脚本批量替换 import**

在仓库根运行（只改 `.py`）：

```python
from pathlib import Path
roots = [Path("src/mawp"), Path("tests"), Path("scripts")]
repls = [
    ("from agent.", "from mawp."),
    ("import agent.", "import mawp."),
    ("import agent\n", "import mawp\n"),
    ("import agent\r\n", "import mawp\r\n"),
]
for root in roots:
    if not root.exists():
        continue
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        new = text
        for a, b in repls:
            new = new.replace(a, b)
        if new != text:
            path.write_text(new, encoding="utf-8")
            print("updated", path)
```

- [ ] **Step 2: 检查残留**

```powershell
rg "from agent\.|import agent" --glob "*.py" -n
```

Expected: 无匹配（或仅文档/注释中的历史名称）。

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: rewrite imports from agent to mawp"
```

---

### Task 3: 配置默认路径切到 `.mawp` / `mawp.config.yaml`

**Files:**
- Modify: `src/mawp/config/loader.py`
- Modify: `src/mawp/cli/main.py`（默认配置文件名与 help）
- Create: `mawp.config.yaml.example`（可由 `agent.config.yaml.example` 复制改路径）
- Delete or keep: `agent.config.yaml.example`（W1 可保留并标注 deprecated，或删除只留 mawp 版）

- [ ] **Step 1: 改 loader 默认路径**

在 `loader.py` 中把：

- `index_path: str = ".agent/index"` → `".mawp/index"`
- exclude 列表中的 `".agent"` → `".mawp"`
- 任何 `load_config` 默认文件名 `agent.config.yaml` → `mawp.config.yaml`
- audit / 其他写死 `.agent` 的默认值同步改为 `.mawp`

并全局在 `src/mawp` 内搜索 `".agent"`，业务存储默认改为 `".mawp"`（样例仓库 `examples/sample-repo` 内历史数据可不动）。

- [ ] **Step 2: 生成 `mawp.config.yaml.example`**

复制 example，将注释与路径改为 `.mawp`，文件头注明产品为 MAWP。

- [ ] **Step 3: Commit**

```bash
git commit -am "chore: switch default config and data dir to mawp"
```

---

### Task 4: CLI 入口改为 `platform` + 命令树可见

**Files:**
- Modify: `src/mawp/cli/main.py`
- Modify: `src/mawp/__init__.py`（如有版本字符串）

- [ ] **Step 1: 改 Typer app 名称与 help**

```python
app = typer.Typer(
    name="platform",
    help="MAWP 多 Agent 工作流平台 — validate / run / SDK·App 扩展",
    no_args_is_help=True,
)
```

将 callback docstring / 面板文案中的「AI 代码开发 Agent」改为「MAWP」。

- [ ] **Step 2: 增加 W1 占位命令（不实现引擎）**

```python
@app.command("validate")
def validate_cmd(
    file: Path = typer.Argument(..., exists=True, dir_okay=False),
) -> None:
    """校验 workflow.yaml（W2 实现）。"""
    console.print("[yellow]validate 尚未实现（计划 W2）。[/yellow] 文件:", file)
    raise typer.Exit(code=2)


@app.command("run")
def run_cmd(
    workflow: Path = typer.Argument(..., exists=True, dir_okay=False),
) -> None:
    """执行工作流（W2 实现）。"""
    console.print("[yellow]run 尚未实现（计划 W2）。[/yellow] 文件:", workflow)
    raise typer.Exit(code=2)
```

保留现有 `goal` / `research` 等子命令本周不删除，避免大批测试一次性全红；README 标明它们为 legacy。

- [ ] **Step 3: 可编辑安装并冒烟**

```powershell
pip install -e ".[dev]"
platform --help
```

Expected: help 中出现 `validate`、`run`，入口名为 `platform`。

- [ ] **Step 4: Commit**

```bash
git commit -am "feat(cli): expose platform entry with validate/run stubs"
```

---

### Task 5: 新建空包骨架 + 接口一页纸

**Files:**
- Create: `src/mawp/core/__init__.py`
- Create: `src/mawp/storage/__init__.py`
- Create: `src/mawp/sdk/__init__.py`
- Create: `src/mawp/apps/__init__.py`
- Create: `src/mawp/runtime/__init__.py`
- Create: `docs/interfaces/w1-api-onepager.md`
- Create: `examples/hello-workflow/workflow.yaml`
- Create: `examples/hello-workflow/README.md`

- [ ] **Step 1: 写空包 `__init__.py`**

每个文件内容示例：

```python
"""MAWP core: workflow schema, validation, and execution engine (W2+)."""

__all__: list[str] = []
```

`storage` / `sdk` / `apps` / `runtime` 各写对应一句话 docstring。

- [ ] **Step 2: 接口一页纸**

`docs/interfaces/w1-api-onepager.md` 从规格 §4 摘录：Schema 示例、ToolResult 四字段、状态机、CLI exit 约定。标题注明「W1 冻结，变更需评审」。

- [ ] **Step 3: hello 样例草案**

`examples/hello-workflow/workflow.yaml`：

```yaml
id: hello
name: Hello Workflow
version: "0.1.0"
entry: start
params:
  name: world
nodes:
  - id: start
    type: start
  - id: echo1
    type: tool
    tool: echo
    input:
      text: "hello ${params.name}"
  - id: end
    type: end
edges:
  - from: start
    to: echo1
  - from: echo1
    to: end
```

README 写明：W2 起可用 `platform validate` / `platform run`。

- [ ] **Step 4: Commit**

```bash
git add src/mawp/core src/mawp/storage src/mawp/sdk src/mawp/apps src/mawp/runtime docs/interfaces examples/hello-workflow
git commit -m "feat: add W1 package stubs, API onepager, and hello-workflow draft"
```

---

### Task 6: README + 最小测试回归

**Files:**
- Modify: `README.md`
- Test: 现有单测（允许 legacy 相关失败稍后处理；至少 `test_config` / `test_tools` / `test_llm_adapter` 应能收集）

- [ ] **Step 1: 重写 README 开头**

说明：本仓库为 MAWP；基于 AI 代码开发 Agent 改造；安装 `pip install -e .`；入口 `platform --help`；设计见 `docs/superpowers/specs/2026-08-13-mawp-design.md`。

- [ ] **Step 2: 跑一组冒烟测试**

```powershell
pytest tests/unit/test_config.py tests/unit/test_tools.py tests/unit/test_llm_adapter.py -q
```

Expected: PASS（若因路径 `.agent` 残留失败，回到 Task 3 补齐）。

- [ ] **Step 3: Commit + Push**

```bash
git add README.md
git commit -m "docs: rewrite README for MAWP W1 skeleton"
git push origin main
```

---

## W2+ 后续计划（本文件不展开）

| 周 | 计划文件（待建） | 目标 |
|----|------------------|------|
| W2 | `2026-08-XX-mawp-w2-hello-loop.md` | validate+run、echo、mock、`.mawp` 持久化 |
| W3 | `…-w3-human-security.md` | condition/human、approve、策略 |
| W4 | `…-w4-sdk-app.md` | SDK/App + demo |
| W5 | `…-w5-acceptance.md` | AC/UC 全绿与文档 |

---

## Spec coverage (自检)

| 规格项 | 本计划任务 |
|--------|------------|
| 包名/CLI/配置/`.mawp` | Task 1–4 |
| 目录 core/storage/sdk/apps | Task 5 |
| 接口冻结文档化 | Task 5 onepager |
| hello 样例草案 | Task 5 |
| 引擎/校验实现 | 明确 Out of scope → W2 |
| legacy 不挂主验收 | Task 4 保留子命令但 README 标明 legacy |

无 TBD/TODO 占位步骤。
