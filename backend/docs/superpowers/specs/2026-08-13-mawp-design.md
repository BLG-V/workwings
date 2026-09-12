# MAWP 多 Agent 工作流平台 — 设计规格

| 属性 | 说明 |
|------|------|
| 产品代号 | MAWP（智流 · 多 Agent 开发平台） |
| 文档版本 | v1.0 |
| 日期 | 2026-08-13 |
| 状态 | 已评审（对话确认第 1–3 节） |
| 依据 | 团队分工与项目进度表 v1.1；基线仓库 `AI代码开发Agent` |
| Phase 1 目标 | 可安装通用内核 + SDK/App 扩展闭环 |

---

## 1. 背景与决策

### 1.1 问题

课程交付物要求通用工作流内核（YAML 编排、校验/执行、人工确认、Tool/Agent、策略、CLI、SDK/App），而现有 `AI代码开发Agent` 是代码开发专用 Copilot，能力可复用但产品边界不同。

### 1.2 改造策略（已确认）

**方案 A：复制后抬升内核、收束业务。**

- 将 `d:\专高六项目\AI代码开发Agent` 完整复制到 `d:\专高六项目\多Agent工作流平台`（排除 `.pytest_cache`、`__pycache__`、`.agent` 运行时数据）。
- 原仓库保留，作对照与回退。
- 不采用原地演进（避免冲掉旧交付物）。
- 不采用从零抽核重写（5 周工期风险过高）。

### 1.3 产品定位变化

| | 旧 | 新（MAWP Phase 1） |
|--|----|-------------------|
| 定位 | 代码开发专用 Copilot | 可安装通用工作流内核 + 扩展 |
| 主路径 | Goal / gstack / autoresearch | `workflow.yaml` → validate/run |
| 扩展 | 内置 Agent 写死 | SDK register + App 装卸 |

---

## 2. 包名、入口与目录

### 2.1 命名冻结

| 项 | 旧 | 新 |
|----|----|----|
| Python 包 | `agent` | `mawp` |
| CLI 入口 | `agent` | `platform` |
| 配置文件 | `agent.config.yaml` | `mawp.config.yaml` |
| 本地数据目录 | `.agent/` | `.mawp/` |
| PyPI/项目名 | `ai-code-agent` | `mawp` |

### 2.2 目标目录结构

```
多Agent工作流平台/
├── pyproject.toml                 # name=mawp；scripts.platform → mawp.cli.main:main
├── mawp.config.yaml.example
├── README.md
├── docs/
│   ├── superpowers/specs/         # 本设计与后续计划
│   └── （保留旧 AI Agent 文档作参考）
├── src/mawp/
│   ├── core/                      # 【新建】A：Schema / 校验 / 执行引擎 / 状态机
│   ├── runtime/                   # 【迁改】AgentSpec + Agent 运行时
│   ├── llm/                       # 【迁】mock / openai / anthropic
│   ├── tools/                     # 【迁】Registry + 内置 echo 等
│   ├── security/                  # 【迁】policy + audit
│   ├── cli/                       # 【改】validate / run / status / approve…
│   ├── storage/                   # 【新建】Run / Session / 事件 → .mawp/
│   ├── sdk/                       # 【新建】register_tool / register_agent
│   ├── apps/                      # 【新建】App 装载逻辑
│   ├── config/                    # 【改】对齐 mawp.config.yaml
│   └── legacy/                    # 可选：goal/gstack/autoresearch 暂存
├── examples/
│   ├── hello-workflow/
│   └── branch-human/
├── apps/
│   └── demo-code-agent/           # W4：旧业务收成官方 demo App
└── tests/
```

### 2.3 模块迁留改

| 模块 | 策略 | 主责 |
|------|------|------|
| `llm/`、`tools/`、`security/` | 迁入；`agent` → `mawp` import；逻辑尽量不动 | B |
| `config/` | 改字段与路径默认值 | C |
| `cli/` | 改入口名；W2 起实现 validate/run | C |
| `goal/`、`gstack/`、`autoresearch/`、`rag/`、`api/` | W1–W3：源码保留在包内（可放 `mawp/legacy/`），**不**挂到 `platform` 主命令；W4 迁入 `apps/demo-code-agent` | D |
| `orchestrator/`、`memory/` | 仅作参考；新建 `core/` + `storage/`，不改造旧模块冒充通用引擎 | A / C |
| `core/`、`sdk/`、`apps/`、`examples/` | 新建 | A / D |

**原则：** W2 最小闭环只依赖 `core + tools(echo) + llm(mock) + cli + storage`。

---

## 3. 角色与里程碑对齐

| 角色 | 成员 | 主责 |
|------|------|------|
| A 工作流引擎 | 王振同 | Schema / 校验 / 执行 / 状态机 / condition / human |
| B 智能与安全 | 李子玉 | Agent / Tool / LLM / 策略审计 |
| C 交互与落地 | 李铭宇 | CLI / `.mawp` 存储 / 配置安装 / Run 摘要 |
| D 扩展与交付 | 孙浩铭 | SDK / App / 样例 / 文档与演示 |

周里程碑：W1 对齐 → W2 hello 闭环 → W3 四节点+人工+安全 → W4 SDK/App → W5 AC 全绿。细项以《团队分工与项目进度表》v1.1 为准。

---

## 4. W1 接口一页纸（冻结）

变更须先改示例与本规格备注，相关负责人确认后再合代码。

### 4.1 `workflow.yaml` Schema（最小必填）

```yaml
id: hello
name: Hello Workflow
version: "0.1.0"
entry: start
params: {}
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

**P0 节点类型**

| type | 含义 | 产出 |
|------|------|------|
| `start` | 入口；须唯一且等于 `entry` | — |
| `end` | 结束 | Run → DONE |
| `tool` | 调用 ToolRegistry | `nodes.<id>.outputs` |
| `agent` | 调用 Agent 运行时 | 同上 |
| `condition` | 表达式 + default 分支 | 不写业务 output |
| `human_checkpoint` | 暂停等待用户 | 恢复后写入 decision |

**静态校验（失败 → CLI exit ≠ 0）：** 缺字段、缺节点、悬空边、未知 type、start/end 约束、默认拒绝环。

**模板变量：** `${params.x}` / `${nodes.<id>.outputs.y}` / `${vars.z}`

**节点字段约定**

- `tool` 节点：`tool`（工具名）+ `input`（dict）
- `agent` 节点：`agent`（AgentSpec 名）+ `input` + 可选 `max_steps`

### 4.2 A ↔ B 调用签名

```text
ToolRegistry.execute(name: str, args: dict, ctx: ToolCallContext) -> ToolResult
ToolResult = { success: bool, data: Any, error: str|null, duration_ms: int }

AgentRuntime.run(spec_ref: str, input: dict, ctx: RunContext) -> AgentResult
AgentResult = { success: bool, output: dict, tool_calls: list, error: str|null }
```

约定：

- Agent 只能经 ToolRegistry 访问外部，禁止直访 OS。
- 高危操作：Policy 默认拒绝；可配置转为 `human_checkpoint`。
- 必须提供可单测的 mock LLM；无 API Key 时 hello（纯 tool）仍可跑。

与旧代码对齐：现有 `ToolResult` 四字段保持不变；`LLMAdapter.chat` 接口保留。

### 4.3 Session / Run 状态机

```text
INIT → RUNNING ⇄ WAITING_USER → DONE
                ↘ FAILED
                ↘ CANCELLED
```

**Human checkpoint 载荷（W3 编码前冻结）**

```json
{
  "run_id": "...",
  "node_id": "approve_deploy",
  "reason": "高危操作确认",
  "allowed": ["approve", "reject", "input"]
}
```

恢复命令：`platform approve | reject | input`（仅当状态为 `WAITING_USER`）。

### 4.4 CLI 契约

| 命令 | 成功 | 失败 |
|------|------|------|
| `platform validate <file>` | exit 0 | exit ≠ 0 + 错误列表 |
| `platform run <workflow>` | 打印 `run_id`；正常结束为 DONE | FAILED → 非 0 |
| `platform run status <run_id>` | 状态 + 当前节点 | 不存在 → 非 0 |
| `platform approve / reject / input` | 恢复执行 | 非 WAITING → 非 0 |

存储布局（W2 可用 JSON/JSONL，不必上 SQLite）：

```text
.mawp/
├── runs/
├── sessions/
└── events/
```

### 4.5 与旧 Goal 流程的边界

旧 Goal `approve` / ship **不复用**为通用 Human 协议。通用 checkpoint 独立实现，避免与代码开发业务绑死。旧流程在 W4 作为 demo App 接入。

---

## 5. 数据流与 W2 主路径

### 5.1 运行时数据流

```text
CLI (platform run)
  → 加载 workflow.yaml + mawp.config.yaml
  → core.validate（可内嵌于 run）
  → storage 创建 Run（INIT → RUNNING）
  → engine 从 entry 沿 edges 推进
       ├─ tool  → ToolRegistry.execute → 写 outputs + 事件
       ├─ agent → AgentRuntime（可多轮 tool-calling）→ outputs
       ├─ condition → 选边
       └─ human_checkpoint → WAITING_USER + 落盘 checkpoint
  → end → DONE + Run 摘要
```

**事件最小字段：** `run_id, ts, type, node_id?, status?, duration_ms?, error?`  
**事件类型 P0：** `run_start | node_start | node_end | waiting_user | run_end`

### 5.2 W2「hello 可跑」序列

样例路径：`examples/hello-workflow/workflow.yaml`（`start → tool:echo → end`）

1. `platform validate …` → exit 0  
2. `platform run …` → 不依赖真 LLM；echo 走 ToolRegistry  
3. `.mawp/runs/<run_id>.json` 状态为 DONE  
4. 事件中可见 echo 成功与耗时  

**W2 明确不做：** condition、human、真 LLM 必选、App 装卸、SDK register。  
**W3 补齐：** `examples/branch-human` + approve；策略拦截（AC-03）。

---

## 6. 错误处理

| 场景 | 行为 |
|------|------|
| validate 失败 | 不创建 Run；exit ≠ 0；打印错误列表 |
| 节点 `success=false` | 默认 Run → FAILED；记录 `failed_node_id`（P0） |
| Policy 拒绝 | `ToolResult.success=false` + 审计；若要求人工则转 WAITING_USER |
| LLM 无 Key / 失败 | hello 不依赖 LLM；agent 节点给出明确错误（可提示 mock） |
| 非 WAITING 时 approve | exit ≠ 0；Run 状态不变 |
| 静态环 | validate 拒绝 |

**P1（W4，可砍）：** 节点超时、fail/continue/goto、取消 Run → CANCELLED。

---

## 7. 测试与验收边界

| 层 | 测什么 | Phase 1 不强制 |
|----|--------|----------------|
| A | Schema、调度、状态机、condition/human | 真 LLM 质量 |
| B | echo、mock LLM、白名单、高危拒绝 | 多厂商效果对比 |
| C | CLI exit code、`.mawp` 读写、status/approve | 复杂 TUI |
| D | hello/branch 样例、文档可复制命令 | 旧 Goal 全量 E2E 全绿 |

旧 `goal/gstack/autoresearch` 相关测试可 skip 或迁至 demo App，**不阻塞** AC-01~06。

**Phase 1 成功标准：**

- AC-01~06、UC-01~06 可按分工表演示  
- `pip install -e .` 后按快速开始能跑通 hello  
- 无业务 App / 禁用 App 时 hello 仍成功（AC-05）

---

## 8. 风险（继承分工表，设计层强调）

| ID | 风险 | 缓解 |
|----|------|------|
| R1 | Schema 不定导致返工 | W1 以本文 §4 为冻结草案；变更走评审 |
| R2 | A/B 节点协议不一致 | §4.2 签名与 ToolResult 四字段写死 |
| R3 | Human 与 CLI 状态机不对齐 | W3 前先实现 §4.3 载荷再编码 |
| R4 | 真 LLM 不稳定 | mock 保验收；真调用加分 |
| R5 | 文档滞后 | 样例与命令随周同步，不堆到 W5 |
| R6 | 安装临期失败 | W4 提前干净环境试装 |

---

## 9. 明确非目标（Phase 1）

- 多租户 / 云端 Session  
- Web UI 作为主验收路径（旧 FastAPI 可保留但不挡 AC）  
- 自动 merge / 强制真网 LLM  
- 完整兼容旧 Goal CLI 的所有子命令作为平台主命令  

---

## 10. 下一步

1. 用户确认本规格文件无异议。  
2. 编写实现计划（writing-plans）：复制仓库 → 改名骨架 → 按 W1–W2 切开可并行任务。  
3. 再开始改代码。
