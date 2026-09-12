# W1 接口一页纸（冻结）

> 变更须先改示例与本文件，相关负责人确认后再合代码。  
> 完整设计见 `docs/superpowers/specs/2026-08-13-mawp-design.md` §4。  
> **W3 增量：** §5（condition / human_checkpoint / approve）；样例 `examples/branch-human/`。

## 1. workflow.yaml 最小示例

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

P0 节点类型：`start` | `end` | `tool` | `agent` | `condition` | `human_checkpoint`

## 2. A ↔ B 调用签名

```text
ToolRegistry.execute(name, args, ctx) -> ToolResult
ToolResult = { success, data, error, duration_ms }

AgentRuntime.run(spec_ref, input, ctx) -> AgentResult
AgentResult = { success, output, tool_calls, error }
```

## 3. Run 状态机

```text
INIT → RUNNING ⇄ WAITING_USER → DONE
                ↘ FAILED
                ↘ CANCELLED
```

## 4. CLI exit 约定

| 命令 | 成功 | 失败 |
|------|------|------|
| `platform validate <file>` | 0 | ≠ 0 |
| `platform run <workflow>` | 0（DONE **或** 合法 `WAITING_USER`） | ≠ 0（FAILED 等） |
| `platform status <run_id>` | 0 | ≠ 0 |
| `platform approve/reject/input` | 0 | ≠ 0（非 WAITING） |

> 说明：原草案写过 `platform run status`；因 Typer 子命令与位置参数冲突，W2 落地为独立命令 `platform status`。

**W3 冻结（A/C）：** `platform run` 进入 `WAITING_USER` 时打印 `run_id` + reason + 下一步命令，**exit code = 0**（合法暂停）；FAILED 等异常为非 0。

存储根：`.mawp/runs/`、`.mawp/sessions/`、`.mawp/events/`

---

## 5. W3：condition / human_checkpoint（草案，A/D 对齐后冻结）

官方样例：`examples/branch-human/workflow.yaml`。

### 5.1 condition 选边

- 条件写在 **edges** 上：`when: "<expr>"` 或 `when: default`。  
- 从同一 `condition` 节点出发：至少一条带表达式，**恰好一条** `when: default`。  
- 表达式可访问：`params` / `nodes.<id>.outputs` / `vars`（求值细节由 A 实现；建议支持 `==` 与简单字符串比较）。  
- 模板语法仍为 `${...}`；`when` 本身是表达式字符串，**不要**再包一层 `${}`。

```yaml
- id: check_risk
  type: condition
# ...
edges:
  - from: check_risk
    to: approve_deploy
    when: "params.risk == 'high'"
  - from: check_risk
    to: auto_ok
    when: default
```

> **否决（相对旧 SRS）：** 节点内 `when: [{expr, goto}, {default}]` + `edges: [[a,b]]` 元组写法与 W2 已落地的 list-nodes/`from`/`to` 冲突，W3 不以该形态为准。

### 5.2 human_checkpoint

```yaml
- id: approve_deploy
  type: human_checkpoint
  reason: "高危操作确认"
  allowed: ["approve", "reject", "input"]
```

落盘 checkpoint 载荷：

```json
{
  "run_id": "...",
  "node_id": "approve_deploy",
  "reason": "高危操作确认",
  "allowed": ["approve", "reject", "input"]
}
```

恢复：`platform approve|reject|input <run_id>`（仅 `WAITING_USER`）。  
恢复后写入 `nodes.<id>.outputs`，建议：

```json
{ "decision": "approve", "input": null }
```

### 5.3 与旧 Goal approve 的边界

通用 checkpoint **独立**于 legacy `agent approve` / ship；勿复用 Goal 存储路径。
