# W4 · deliver.yaml 字段对齐（A ↔ D）

> A（王振同）提出引擎侧契约；D 的 `apps/demo-code-agent/workflows/deliver.yaml` 按本文件对齐。  
> Agent 本期可 mock；真 Agent 由 B/C 替换，**outputs 键名保持稳定**。  
> D 扩展（AC-08）：在冻结环路上插入 `requirement`、`frontend`；**不改** §2 已冻结键名。

## 1. 拓扑

### 1.1 引擎冻结（A · `examples/deliver/workflow.yaml`）

```text
start → planner → coding → testing → check_test
                                   ├─ fail → debug → testing   # edge: loop: true
                                   └─ pass → review → check_review
                                                    ├─ blocking → human_review → ship
                                                    └─ pass → ship → end
```

### 1.2 App 主链（D · AC-08）

```text
start → planner → requirement → coding → frontend → testing → check_test
        ├─ fail → debug → testing   # loop: true（同 A）
        └─ pass → review → check_review
             ├─ blocking → human_review → ship → end
             └─ pass → ship → end
```

- Testing fail→Debug→Retest：使用 **显式回边** `loop: true` + `max_traversals`（或工作流 `default_loop_max`）。
- Review `blocking`：**不得**无确认进入 Ship；经 `condition` + `human_checkpoint`。

## 2. 节点 outputs（冻结）

### planner（`type: agent`, `agent: planner`）

```yaml
tasks:
  - id: T1
    title: "..."
    depends_on: []
status: ok   # ok | failed
count: 1
```

### testing（`agent: testing`）

```yaml
passed: true          # bool — condition 用
status: pass          # pass | fail
failures: []          # list[str]
log_summary: "..."
attempt: 1            # 回边重入时递增
```

### review（`agent: review`）

```yaml
status: pass          # pass | blocking
blocking_count: 0
findings:
  - level: blocking   # blocking | suggestion | nit
    file: "..."
    message: "..."
```

### ship（`agent: ship`）

```yaml
status: ok
delivery_notes: "..."
auto_push: false      # 禁止自动 push/merge
auto_merge: false
```

### human_checkpoint（复用 W3）

恢复后：

```yaml
decision: approve | reject | input
input: ...
```

### D 扩展（可增键，勿改冻结键）

**requirement**（建议）：`status` / `summary` / `spec_ref` / `tasks`（继承 planner.tasks）/ `ui_key_points` / `acceptance_criteria`

**frontend**（建议）：`status` / `frontend_dir` / `pages` / `artifacts` / `ui_key_points`

## 3. params（演示用）

| 键 | 含义 | 示例 |
|----|------|------|
| `goal` | 目标一句话 | `AC-08 deliver with frontend page` |
| `pass_on_attempt` | 第几次 testing 判定通过 | `1` / `2` |
| `review_status` | mock Review 结果 | `pass` / `blocking` |

## 4. 回边 YAML

```yaml
- from: debug
  to: testing
  loop: true
  max_traversals: 3
```

未标注 `loop: true` 的环仍被 validate 拒绝。

## 5. 验收

```bash
# A 引擎样例
platform validate examples/deliver/workflow.yaml
platform run examples/deliver/workflow.yaml

# D App（含 Requirement / Frontend）
platform validate apps/demo-code-agent/workflows/deliver.yaml
platform run apps/demo-code-agent/workflows/deliver.yaml
platform run apps/demo-code-agent/workflows/deliver.yaml --params pass_on_attempt=2
platform run apps/demo-code-agent/workflows/deliver.yaml --params review_status=blocking
# → WAITING_USER → platform approve <run_id> → DONE
```

官方样例：`examples/deliver/workflow.yaml`  
App 样例：`apps/demo-code-agent/workflows/deliver.yaml`
