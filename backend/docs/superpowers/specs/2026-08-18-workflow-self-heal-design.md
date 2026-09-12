# 工作流自主迭代（Self-Heal）— 设计规格

| 属性 | 说明 |
|------|------|
| 产品 | 智流 MAWP / AgentFlow |
| 文档版本 | v1.0 |
| 日期 | 2026-08-18 |
| 状态 | 待用户审阅（对话已确认架构 / 数据流 / 测试范围） |
| 范围 | deliver 主链运行时自愈：瞬时故障 + 质量回环 |
| 非目标 | Supervisor Agent、新节点类型、改 YAML 隐式回边、自动 push/merge、跨 run 记忆 |

---

## 1. 背景与决策

### 1.1 问题

`demo-code-agent-deliver` 运行记录中大量 `FAILED`。截图中两类失败占主导：

1. `节点: review 超过 max_steps=6` — Agent 持续调工具却不输出最终 JSON，硬上限后整次 run 失败。
2. `节点: coding OpenAI 请求失败: Server disconnected without sending a response.` — LLM 断线后直接失败。

现有保护不足以「带着问题去修」：

| 已有机制 | 实际效果 |
|----------|----------|
| `node_max_retries` | 同节点原样重跑，不分析原因、不换策略 |
| `testing → debug → testing` 回边 | 仅覆盖测试失败；`max_traversals` 用尽后仍可能 FAILED |
| `review blocking → human_review` | 审查不通过立刻等人，不自动回 coding |
| `AgentRuntime.chat()` | 不走 `chat_with_retry`，断线无退避 |
| `error_classifier` | 已能分类测试失败，但未接到引擎跳转 |
| gstack `auto_fix_blocking` | 走 Goal/Issue 流水线，不服务 YAML deliver run |

### 1.2 已确认决策

- **覆盖范围 C**：质量问题（测试失败、审查 blocking）与运行时故障（断线、`max_steps`）都要自动处理。
- **停手规则 A**：达到 `heal_max_rounds` 后进入人工确认（`WAITING_USER`），不直接 FAILED（图上无 `human_review` 时除外）。
- **实现方案 2**：引擎级 `SelfHealPolicy`，不新增 Supervisor Agent，不改 YAML 节点图。

---

## 2. 架构

### 2.1 位置

自愈加在现有调度链上，不新增工作流节点类型。

```
AgentRuntime / LLM              WorkflowEngine                 前端
  chat_with_retry                  _schedule
  max_steps 收尾回合     →        SelfHealPolicy      →     heal_* 事件
                                    │
                         error_classifier + debug 回环
```

三个落点：

1. **`AgentRuntime`**（瞬时 + 步数）：`chat()` 改为 `chat_with_retry`；撞上 `max_steps` 时先做一轮禁止工具、必须输出 JSON 的收尾；仍失败则带着工具调用摘要再开一轮。
2. **`SelfHealPolicy`**（新模块，由引擎调用）：对 Agent 失败、测试未过、审查 blocking 分类，决定同节点重试、跳到 `coding`/`debug`、或停到人工。
3. **运行记录**：写入 `heal_attempt` / `heal_handoff`（瞬时重试沿用已有 `node_retry`）。Runs / Studio 已能展示 `node_retry`，补这两类即可。

### 2.2 生效范围

- **默认开启**：deliver 主链（`demo-code-agent-deliver` 及同类 planner→…→ship，以工作流含 `testing`+`review`+`coding`/`debug` 节点为准）。
- **关闭**：`params.self_heal: false`，或非 deliver 图（如 `hello-workflow`）。关闭后行为与本功能上线前完全一致。
- 审查 blocking 先自动修；满轮次后再进现有 `human_review`。

### 2.3 明确不做

- 新的 Supervisor Agent、新节点类型。
- 在 YAML 中画出引擎隐式回边（编排页看不到的边会造成误解）。
- 自动 git push / merge。
- 跨 run 的历史记忆；自愈状态只存在于当次 `RunRecord`。

---

## 3. 组件与接口

### 3.1 `mawp.runtime.self_heal`

新文件，单一职责：根据当前节点结果给出下一步，不执行 Agent、不写文件。

```python
class HealReason(str, Enum):
    TRANSIENT = "transient"           # 断线 / 5xx / 空响应
    MAX_STEPS = "max_steps"           # 工具轮次耗尽
    TEST_FAILED = "test_failed"       # testing.passed == false
    REVIEW_BLOCKING = "review_blocking"
    AGENT_FAILED = "agent_failed"     # 其他 success=False
    NONE = "none"

class HealAction(str, Enum):
    CONTINUE = "continue"             # 按 YAML 出边
    RETRY_NODE = "retry_node"         # 同节点瞬时重试（不计 heal）
    RERUN_WITH_SUMMARY = "rerun_with_summary"  # max_steps 摘要重开（计 1 heal）
    GOTO = "goto"                     # 跳到 coding / debug（计 1 heal）
    HANDOFF = "handoff"               # 预算耗尽 → 人工或 FAILED

@dataclass
class HealDecision:
    action: HealAction
    reason: HealReason
    target_node_id: str | None = None
    consume_heal_round: bool = False
    context: dict[str, Any] = field(default_factory=dict)
```

`SelfHealPolicy.decide(workflow, run, node, result_or_error) -> HealDecision` 是唯一入口。

### 3.2 `AgentRuntime` 变更

- 所有 LLM 调用走 `llm.chat_with_retry`（已有指数退避，`max_retries=3`）。
- 工具循环在 `step == max_steps - 1` 且仍在调工具时：追加一条系统/用户消息「禁止再调用工具，必须输出最终 JSON」，再请求一次（收尾回合，不计入新的 heal）。
- 收尾仍无合法 JSON：返回 `success=False, error="超过 max_steps=N"`，并在 `output` 中附 `tool_calls` 摘要，供引擎摘要重开。
- 现有 `test_agent_runtime_respects_max_steps`：改为「纯工具循环且收尾也失败才报错」；新增「收尾成功出 JSON」用例。

### 3.3 `WorkflowEngine` 变更

- `_run_agent_node` 瞬时失败继续用 `node_max_retries` / `node_retry_delay`；**不再**对 `max_steps`、审查 blocking、测试失败做无差别同节点重试。
- `_schedule` 在 agent 节点结束后、选 YAML 出边之前询问 `SelfHealPolicy`。
- `GOTO` 时设置 `current_id = target`，不调用 `_take_edge`（因此不占用 `max_traversals`）。
- 自愈跳转写入 `run.heal` 与事件；`heal` 字段随 `save_run` 持久化。

### 3.4 工作流参数（可覆盖）

| 参数 | 默认 | 含义 |
|------|------|------|
| `self_heal` | `true`（仅 deliver 检测通过时） | 总开关 |
| `heal_max_rounds` | `3` | 计入预算的自愈次数上限 |
| `heal_on_review_blocking` | `true` | blocking 是否先自动回 coding/debug |
| `node_max_retries` | `3`（已有） | 仅瞬时故障 |
| `node_retry_delay` | `2.0`（已有） | 瞬时重试间隔秒 |
| `debug_max_attempts` | `5`（已有） | 与 heal 取更紧上限 |

---

## 4. 数据流

每次 Agent 节点结束或抛错，引擎走同一决策，不另开并行调度。

```
节点结果
  ├─ 成功且非质量问题 → CONTINUE（YAML 出边）
  ├─ 瞬时故障
  │     RETRY_NODE，最多 node_max_retries 次，不计入 heal_max_rounds
  ├─ max_steps 耗尽
  │     ① AgentRuntime 收尾回合（禁工具、只出 JSON）
  │     ② 仍失败 → RERUN_WITH_SUMMARY，计 1 次 heal
  ├─ testing.passed == false
  │     优先走 YAML 上已有 debug 回边（计入 max_traversals）
  │     同时把 error_classifier 修复指令写入 debug input
  │     该次回环计 1 次 heal；与 max_traversals / debug_max_attempts 取更紧
  └─ review.status == blocking 或其余 agent 失败
        预算未满 → GOTO coding（project_mode 下走现有 debug 修复路径）
        带上 findings / error / repair_instruction，随后仍经 testing
        计 1 次 heal
```

`GOTO` 目标规则：

- 图中存在 `debug` 且失败来自 testing → `debug`
- 图中存在 `coding` 且失败来自 review / 通用 agent 失败 → `coding`
- 两者都无 → `HANDOFF`

自愈跳到 `coding`/`debug` 时必须带失败上下文，禁止空上下文重跑。

---

## 5. 停手与错误处理

### 5.1 预算

| 计不计入 | 行为 |
|----------|------|
| 不计 | 瞬时故障的同节点重试；max_steps 收尾回合（仍在同一 AgentRuntime.run 内） |
| 计 1 | max_steps 摘要重开、测试失败进 debug、审查 blocking 回 coding、其他 AGENT_FAILED 的 GOTO |
| 耗尽 | `HANDOFF` |

`node_max_retries` 只服务瞬时故障，避免与质量回环叠成「3×3」空转。

显式 `debug → testing` 回边保留。引擎 `GOTO` 不走 YAML 边，故不占用 `max_traversals`。测试失败场景：**heal 次数与回边次数取更紧的那个**，避免同一失败被修两次。

### 5.2 HANDOFF

1. 若图上存在 `human_review`（或任意 `human_checkpoint`）：`status=WAITING_USER`，checkpoint.reason 包含最后失败原因与 `heal.round/max_rounds`。
2. 否则：`status=FAILED`，`error` 写明已尝试轮次和最后原因。

### 5.3 其他约定

- 自愈跳转目标不存在或非 deliver 图：不吞异常；有人审节点则交人，否则 FAILED。
- `self_heal: false` 或非 deliver：与现在完全一致。
- 人工 `reject` **不**触发新一轮自愈。
- `approve` / `input` 按现有 `human_review → ship` 出边恢复，不自动再进 coding。

---

## 6. Run 状态与前端

### 6.1 `RunRecord.heal`

```json
{
  "enabled": true,
  "round": 2,
  "max_rounds": 3,
  "last_reason": "review_blocking",
  "last_from": "review",
  "last_to": "coding"
}
```

持久化在现有 run JSON 中；`RunStore` 对未知字段保持兼容（多写 `heal` 键即可）。

### 6.2 事件

| type | 何时 | 主要字段 |
|------|------|----------|
| `node_retry` | 瞬时重试（已有） | `attempt`, `max_retries`, `error` |
| `heal_attempt` | 计入预算的一次自愈开始 | `reason`, `from`, `to`, `round`, `max_rounds` |
| `heal_handoff` | 预算耗尽交人 | `reason`, `round`, `max_rounds` |

不强制使用 `heal_start`；首次 `heal_attempt` 即表示自愈开始，避免事件膨胀。

### 6.3 前端

- `RunMonitor` / Studio 将 `heal_attempt`、`heal_handoff` 标为琥珀色（与 `node_retry` 同类）。
- 运行状态旁显示「自愈 {round}/{max_rounds}」（`run.heal` 或最近事件）。
- 不新增页面；不在前端做修复决策。
- `WAITING_USER` 仍用现有 approve / reject / input。

---

## 7. 测试

全部使用 mock LLM，不打真实 API。

| 用例 | 期望 |
|------|------|
| 断线后第 2 次成功 | 节点成功；仅 `node_retry`；`heal.round == 0` |
| 工具调用撑满 max_steps，收尾出 JSON | 节点成功，无 heal |
| 收尾仍失败后摘要重开成功 | `heal.round == 1`，有 `heal_attempt` |
| testing 未过 | 进入 debug，input 含分类后的修复指令 |
| review blocking，预算未满 | 跳到 coding，不进 `human_review` |
| `heal_max_rounds` 用尽 | `WAITING_USER` + `heal_handoff`，不 FAILED |
| `self_heal: false` | 与当前 FAILED / 人审行为相同 |
| hello-workflow | 不受影响，仍 DONE |
| 人工 reject | 不启动新自愈 |

文件计划：

- `backend/tests/unit/test_self_heal_policy.py` — 决策表
- `backend/tests/unit/test_agent_runtime.py` — 收尾回合 / 仍失败
- `backend/tests/unit/test_workflow_engine.py` 或新 `test_engine_self_heal.py` — 引擎跳转与 HANDOFF
- 前端：`RunMonitor` 事件着色，无独立单测则手工对照现有 `node_retry` 样式

---

## 8. 实现落点（供后续计划）

| 文件 | 职责 |
|------|------|
| `backend/src/mawp/runtime/self_heal.py` | **新建** Policy / Decision |
| `backend/src/mawp/runtime/agent_runtime.py` | `chat_with_retry` + 收尾回合 + 摘要 |
| `backend/src/mawp/core/engine.py` | 调度接入 Policy；写 `run.heal` 与事件 |
| `backend/src/mawp/storage/store.py` | `RunRecord.heal` 字段（若模型显式列出） |
| `backend/src/mawp/runtime/error_classifier.py` | 已有，testing 失败时调用 |
| `backend/apps/demo-code-agent/workflows/deliver.yaml` | 仅增加默认 params 注释/键，不改边 |
| `src/components/RunMonitor.tsx` | heal 事件展示 |
| `src/pages/StudioPage/StudioPage.tsx` | 同上（若已监听 node_retry） |

---

## 9. 验收

1. 复现「review 超过 max_steps」类失败时，run 出现 `heal_attempt` 并尝试收尾或回 coding，而不是第一次越限就 FAILED。
2. 复现 coding 断线时，出现 `node_retry` 且多数情况下节点可恢复。
3. review blocking 在 3 轮内可自动回 coding→testing→review；满 3 轮后 `WAITING_USER`。
4. `self_heal: false` 与 `hello-workflow` 回归通过。
