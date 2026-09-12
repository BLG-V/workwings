# Workflow Self-Heal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver 主链在瞬时故障与质量失败时自动迭代修复，预算耗尽后交人，而不是第一次出错就 FAILED。

**Architecture:** 纯决策模块 `SelfHealPolicy` 不执行 Agent；`AgentRuntime` 负责 `chat_with_retry` 与 max_steps 收尾回合；`WorkflowEngine` 在 agent 节点结束后应用决策（同节点瞬时重试 / 摘要重开 / GOTO coding|debug / HANDOFF）；前端只展示 `heal_attempt` 与 `heal_handoff`。

**Tech Stack:** Python 3.11+、现有 WorkflowEngine / AgentRuntime / pytest、React `RunMonitor` + Studio。

**Spec:** `backend/docs/superpowers/specs/2026-08-18-workflow-self-heal-design.md`

**Git:** 本仓库用户规则为未明确要求时不 commit。各 Task 的 commit 步可跳过。

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/src/mawp/runtime/self_heal.py` | **新建** HealReason/HealAction/HealDecision/SelfHealPolicy |
| `backend/src/mawp/runtime/agent_runtime.py` | `chat_with_retry` + 收尾回合 + LLMError→AgentRunResult |
| `backend/src/mawp/storage/store.py` | `RunRecord.heal` |
| `backend/src/mawp/core/engine.py` | 调度接入 Policy；写事件与 heal 状态 |
| `backend/apps/demo-code-agent/workflows/deliver.yaml` | 默认 params 注释 |
| `backend/examples/deliver/workflow.yaml` | 同上 |
| `src/components/RunMonitor.tsx` | heal 事件着色 + 自愈 2/3 |
| `src/pages/StudioPage/StudioPage.tsx` | heal 思考步骤文案 |
| `backend/tests/unit/test_self_heal_policy.py` | **新建** 决策表 |
| `backend/tests/unit/test_agent_runtime.py` | 收尾回合 |
| `backend/tests/unit/test_engine_self_heal.py` | **新建** 引擎跳转 / HANDOFF |
| `backend/src/mawp/runtime/__init__.py` | 导出 Policy |

---

### Task 1: SelfHealPolicy 决策表（TDD）

**Files:**
- Create: `backend/src/mawp/runtime/self_heal.py`
- Test: `backend/tests/unit/test_self_heal_policy.py`

- [ ] **Step 1: 写失败测试** `backend/tests/unit/test_self_heal_policy.py`

```python
from __future__ import annotations

from mawp.core.models import Workflow, WorkflowEdge, WorkflowNode
from mawp.runtime.agents import AgentResult
from mawp.runtime.self_heal import HealAction, HealReason, SelfHealPolicy
from mawp.storage.store import RunRecord


def _deliver_wf() -> Workflow:
    return Workflow(
        id="demo-code-agent-deliver",
        name="deliver",
        version="0.2.0",
        entry="start",
        params={"self_heal": True, "heal_max_rounds": 3, "heal_on_review_blocking": True},
        nodes=[
            WorkflowNode(id="start", type="start"),
            WorkflowNode(id="coding", type="agent", agent="coding"),
            WorkflowNode(id="testing", type="agent", agent="testing"),
            WorkflowNode(id="debug", type="agent", agent="debug"),
            WorkflowNode(id="review", type="agent", agent="review"),
            WorkflowNode(id="check_review", type="condition"),
            WorkflowNode(id="human_review", type="human_checkpoint"),
            WorkflowNode(id="end", type="end"),
        ],
        edges=[
            WorkflowEdge(from_id="start", to_id="coding"),
            WorkflowEdge(from_id="coding", to_id="testing"),
            WorkflowEdge(from_id="testing", to_id="debug", when="nodes.testing.outputs.passed == false", loop=True, max_traversals=5),
            WorkflowEdge(from_id="testing", to_id="review", when="default"),
            WorkflowEdge(from_id="debug", to_id="testing", loop=True, max_traversals=5),
            WorkflowEdge(from_id="review", to_id="check_review"),
            WorkflowEdge(from_id="check_review", to_id="human_review", when="nodes.review.outputs.status == 'blocking'"),
            WorkflowEdge(from_id="check_review", to_id="end", when="default"),
            WorkflowEdge(from_id="human_review", to_id="end"),
        ],
    )


def _run(**heal) -> RunRecord:
    base = {"enabled": True, "round": 0, "max_rounds": 3, "last_reason": None, "last_from": None, "last_to": None}
    base.update(heal)
    return RunRecord(run_id="r1", workflow_id="demo-code-agent-deliver", status="RUNNING", params={"self_heal": True, "heal_max_rounds": 3}, heal=base)


def test_disabled_returns_continue() -> None:
    wf = _deliver_wf()
    run = _run()
    run.params["self_heal"] = False
    d = SelfHealPolicy().decide(wf, run, wf.node_map()["testing"], AgentResult(success=True, output={"passed": False}))
    assert d.action == HealAction.CONTINUE
    assert d.reason == HealReason.NONE


def test_hello_graph_not_deliver() -> None:
    wf = Workflow(
        id="hello", name="h", version="1", entry="start",
        nodes=[WorkflowNode(id="start", type="start"), WorkflowNode(id="end", type="end")],
        edges=[WorkflowEdge(from_id="start", to_id="end")],
    )
    run = RunRecord(run_id="r", workflow_id="hello", status="RUNNING", params={})
    d = SelfHealPolicy().decide(wf, run, wf.node_map()["start"], AgentResult(success=False, error="x"))
    assert d.action == HealAction.CONTINUE


def test_transient_retry_node() -> None:
    wf = _deliver_wf()
    d = SelfHealPolicy().decide(wf, _run(), wf.node_map()["coding"], AgentResult(success=False, error="OpenAI 请求失败: Server disconnected without sending a response."))
    assert d.action == HealAction.RETRY_NODE
    assert d.reason == HealReason.TRANSIENT
    assert d.consume_heal_round is False


def test_max_steps_rerun_with_summary() -> None:
    wf = _deliver_wf()
    d = SelfHealPolicy().decide(wf, _run(), wf.node_map()["review"], AgentResult(success=False, error="超过 max_steps=6"))
    assert d.action == HealAction.RERUN_WITH_SUMMARY
    assert d.reason == HealReason.MAX_STEPS
    assert d.consume_heal_round is True


def test_test_failed_continue_yaml_debug_and_consume_heal() -> None:
    wf = _deliver_wf()
    d = SelfHealPolicy().decide(wf, _run(), wf.node_map()["testing"], AgentResult(success=True, output={"passed": False, "failures": ["boom"], "log_summary": "err"}))
    assert d.action == HealAction.CONTINUE
    assert d.reason == HealReason.TEST_FAILED
    assert d.consume_heal_round is True
    assert "repair_instruction" in d.context


def test_review_blocking_goto_coding() -> None:
    wf = _deliver_wf()
    d = SelfHealPolicy().decide(wf, _run(), wf.node_map()["review"], AgentResult(success=True, output={"status": "blocking", "blocking_count": 1, "findings": ["x"]}))
    assert d.action == HealAction.GOTO
    assert d.target_node_id == "coding"
    assert d.reason == HealReason.REVIEW_BLOCKING
    assert d.consume_heal_round is True


def test_budget_exhausted_handoff() -> None:
    wf = _deliver_wf()
    d = SelfHealPolicy().decide(wf, _run(round=3), wf.node_map()["review"], AgentResult(success=True, output={"status": "blocking", "blocking_count": 1}))
    assert d.action == HealAction.HANDOFF
    assert d.target_node_id == "human_review"


def test_agent_failed_goto_coding() -> None:
    wf = _deliver_wf()
    d = SelfHealPolicy().decide(wf, _run(), wf.node_map()["frontend"] if False else wf.node_map()["review"], AgentResult(success=False, error="unknown boom"))
    # review node + generic fail → GOTO coding
    assert d.action == HealAction.GOTO
    assert d.target_node_id == "coding"
```

修正最后一用例：用 coding 节点以外的失败。`review` 的 generic fail 走 AGENT_FAILED → GOTO coding。把 `frontend` 假分支删掉，节点用 `coding` 失败时若无其他修复目标：coding 失败 GOTO `debug`（图中有 debug）。

最终 `test_agent_failed_goto_debug`：coding 节点 `success=False error="boom"` → GOTO debug。

- [ ] **Step 2: 运行确认失败**

```
cd backend
python -m pytest tests/unit/test_self_heal_policy.py -q
```

Expected: `ImportError: cannot import name 'SelfHealPolicy'`

- [ ] **Step 3: 实现** `backend/src/mawp/runtime/self_heal.py`

完整模块：

- `HealReason`: `transient | max_steps | test_failed | review_blocking | agent_failed | none`
- `HealAction`: `continue | retry_node | rerun_with_summary | goto | handoff`
- `HealDecision(action, reason, target_node_id=None, consume_heal_round=False, context={})`
- `is_deliver_graph(workflow)`: 节点 id 或 agent 名同时包含 testing、review、以及 coding 或 debug
- `self_heal_enabled(workflow, run)`: deliver 图 且 `params.self_heal` 缺省 True；显式 false 则关
- `is_transient_error(text)`: 大小写不敏感匹配 `disconnected|timeout|temporar|429|502|503|504|connection reset|server disconnected`
- `is_max_steps_error(text)`: `"max_steps" in text`
- `heal_budget_left(run)`: `(run.heal or {}).get("round", 0) < int(params.heal_max_rounds or 3)`
- `first_human_node_id(workflow)`: 第一个 `type==human_checkpoint` 的 id
- `decide(workflow, run, node, result: AgentResult) -> HealDecision`

决策顺序（命中即返回）：

1. 未启用 → CONTINUE / NONE
2. `result.success is False` 且 transient → RETRY_NODE（不计 heal）
3. `result.success is False` 且 max_steps：预算有 → RERUN_WITH_SUMMARY；否则 HANDOFF
4. 当前节点 agent/id 为 testing 且 `output.passed is False`：预算有 → CONTINUE + TEST_FAILED + consume + `context.repair_instruction`（调用 `build_repair_instruction(classify_error(...))`）；否则 HANDOFF
5. 当前节点 agent/id 为 review 且 `output.status == blocking`：`heal_on_review_blocking` 为 false → CONTINUE；预算有 → GOTO `coding`（无 coding 则 debug）；否则 HANDOFF
6. `result.success is False`：预算有 → GOTO `debug`（当前已是 debug 则 GOTO `coding`，都没有则 HANDOFF）；否则 HANDOFF
7. 否则 CONTINUE / NONE

HANDOFF 的 `target_node_id` = `first_human_node_id`（可能 None）。GOTO 目标必须存在于 `workflow.node_map()`，否则改 HANDOFF。

- [ ] **Step 4: 测试通过**

```
python -m pytest tests/unit/test_self_heal_policy.py -q
```

Expected: PASS

- [ ] **Step 5: 导出** 在 `backend/src/mawp/runtime/__init__.py` 增加 `SelfHealPolicy`（可选）。Commit 跳过。

---

### Task 2: AgentRuntime 收尾回合 + chat_with_retry（TDD）

**Files:**
- Modify: `backend/src/mawp/runtime/agent_runtime.py`
- Test: `backend/tests/unit/test_agent_runtime.py`

- [ ] **Step 1: 追加测试**

保留 `test_agent_runtime_respects_max_steps`：max_steps=2、两轮工具、第三响若被收尾消耗且仍是 tool_call → 仍 `success=False` 且 error 含 max_steps，`len(tool_calls)==2`。

新增：

```python
def test_agent_runtime_finalize_round_emits_json(config: AgentConfig) -> None:
    llm = MockLLMAdapter(
        [
            MockLLMAdapter.tool_call_response("c1", "echo", {"text": "a"}),
            MockLLMAdapter.tool_call_response("c2", "echo", {"text": "b"}),
            MockLLMAdapter.json_response({"status": "ok", "from": "finalize"}),
        ]
    )
    runtime = AgentRuntime(config, llm=llm, registry=ToolRegistry(config))
    runtime.register(AgentSpec(name="review", system_prompt="Keep calling tools.", model="mock", tools=["echo"], max_steps=2))
    result = runtime.run("review", {"text": "loop"}, RuntimeContext(session_id="s4"))
    assert result.success
    assert result.output.get("from") == "finalize"
    assert len(result.tool_calls) == 2
    assert llm.calls[-1]["tools"] in (None, [])


def test_agent_runtime_maps_llm_error(config: AgentConfig) -> None:
    from mawp.llm.exceptions import LLMRequestError

    class Boom(MockLLMAdapter):
        def chat(self, *a, **k):
            raise LLMRequestError("OpenAI 请求失败: Server disconnected without sending a response.")

    runtime = AgentRuntime(config, llm=Boom([]), registry=ToolRegistry(config))
    runtime.register(AgentSpec(name="coding", system_prompt="x", model="mock", tools=[], max_steps=2))
    result = runtime.run("coding", {"text": "go"}, RuntimeContext(session_id="s5"))
    assert not result.success
    assert "disconnected" in (result.error or "").lower()
```

`Boom.chat_with_retry` 会重试 3 次再抛出；`AgentRuntime` 必须 catch `LLMError` 转为 `AgentRunResult`。

- [ ] **Step 2: 跑测试确认失败** — finalize 用例当前会在第二轮 tool_call 直接 fail，拿不到 JSON。

- [ ] **Step 3: 改 `agent_runtime.py`**

1. `from mawp.llm.exceptions import LLMError`
2. 循环内 `self.llm.chat(...)` 改为 `self.llm.chat_with_retry(...)`
3. 整个 `run()` 的 chat 循环包在 `try/except LLMError`，返回 `AgentRunResult(success=False, error=str(exc), tool_calls=tool_records)`
4. 当 `step == spec.max_steps - 1` 且仍 `has_tool_calls`：不要立刻 fail。追加 user 消息：`禁止再调用工具。根据已完成的工具结果，只输出最终 JSON。` 再 `chat_with_retry(..., tools=None, response_format={"type":"json_object"} if spec.output_schema else None)`。若有文本/JSON 则成功返回；若仍 tool_calls 或空 → `success=False, error=超过 max_steps=N`，`output` 可含 `{"tool_summary": tool_records[-8:]}`。

- [ ] **Step 4: pytest** `tests/unit/test_agent_runtime.py -q` 全绿。

---

### Task 3: RunRecord.heal

**Files:**
- Modify: `backend/src/mawp/storage/store.py`

- [ ] 给 `RunRecord` 增加 `heal: dict[str, Any] | None = None`。`to_dict` 已用 `asdict` 会带上。`from_dict` 增加 `heal=data.get("heal")`。缺省 None，旧 run JSON 仍可加载。
- [ ] 无单独测试也可；`test_engine_self_heal` 会覆盖 round-trip。Commit 跳过。

---

### Task 4: WorkflowEngine 接入（TDD）

**Files:**
- Modify: `backend/src/mawp/core/engine.py`
- Test: `backend/tests/unit/test_engine_self_heal.py`

用可控 `AgentRunner`，不要真 LLM。

```python
from __future__ import annotations

from pathlib import Path

from mawp.config.loader import AgentConfig
from mawp.core.engine import WorkflowEngine
from mawp.core.models import Workflow, WorkflowEdge, WorkflowNode
from mawp.runtime.agents import AgentResult, AgentRunContext, AgentRunner
from mawp.tools.registry import ToolRegistry


class ScriptedRunner:
    def __init__(self, script: dict[str, list[AgentResult]]):
        self.script = {k: list(v) for k, v in script.items()}
        self.calls: list[str] = []

    def run(self, agent: str, input_data: dict, ctx: AgentRunContext) -> AgentResult:
        self.calls.append(agent)
        q = self.script.setdefault(agent, [])
        if q:
            return q.pop(0)
        return AgentResult(success=True, output={"status": "ok", "agent": agent, "passed": True})


def _wf() -> Workflow:
    # 与 Task 1 deliver 图相同，另加 planner 可省略；coding→testing→review→check_review→human|end
    ...
```

用例：

1. **断线后第 2 次成功**：coding 先 `success=False error=Server disconnected...` 再 `success=True`。run DONE。events 含 `node_retry`。`run.heal["round"]==0`。
2. **review blocking 跳 coding**：review 返回 blocking，随后 coding/testing/review pass。events 含 `heal_attempt`，reason=`review_blocking`。不经过 WAITING_USER。
3. **heal_max_rounds=1 且一直 blocking**：第一次 GOTO coding；coding 后再 review blocking → HANDOFF WAITING_USER，`heal_handoff` 事件。`status==WAITING_USER`。
4. **self_heal false + max_steps**：review 失败 `超过 max_steps=6` → FAILED。
5. **hello-workflow 回归** 已有 `test_hello_engine_done`，本 Task 结束时再跑一遍。

- [ ] **Step 1: 写测试并确认失败**（Policy 已存在但引擎未接入，blocking 会走 YAML 到 human，或 agent 失败直接 FAILED）。

- [ ] **Step 2: 改引擎**

`WorkflowEngine.__init__` 保存 `self._heal = SelfHealPolicy()`。

`_run_agent_node` 改为返回 `AgentResult`（从 `agent_runner.run`），**仅当** `SelfHealPolicy` 判定 TRANSIENT 时按 `node_max_retries` 循环并 `node_retry` 事件；非瞬时失败返回该次 `AgentResult`，不在此 raise。成功直接返回。若瞬时用尽仍失败，返回最后一次失败 result。

Agent 分支伪代码：

```python
if node.type == "agent":
    result = self._run_agent_node(...)
    out = dict(result.output or {})
    if result.error:
        out["_error"] = result.error
        out["_success"] = bool(result.success)
    nodes_outputs[node.id] = out
    run.node_outputs = nodes_outputs
    decision = self._heal.decide(workflow, run, node, result)

    if decision.consume_heal_round:
        self._bump_heal(run, node, decision)

    if decision.context.get("repair_instruction"):
        out["repair_instruction"] = decision.context["repair_instruction"]
        nodes_outputs[node.id] = out

    if decision.action == HealAction.RERUN_WITH_SUMMARY:
        # 把 tool/error 摘要写入 input 再跑一次同一节点（_run_agent_node）
        # 成功则当作普通成功往下走
        ...
    if decision.action == HealAction.GOTO and decision.target_node_id:
        self.store.append_event(..., type=heal_attempt, from=node.id, to=target, reason, round, max_rounds)
        current_id = decision.target_node_id  # 不 _take_edge
        continue
    if decision.action == HealAction.HANDOFF:
        self.store.append_event(..., type=heal_handoff, ...)
        hid = decision.target_node_id
        if hid and workflow.node_map()[hid].type == "human_checkpoint":
            return self._pause_human(...)
        raise RuntimeError(result.error or f"自愈耗尽: {decision.reason}")

    if not result.success:
        raise RuntimeError(result.error or f"agent 执行失败: {node.agent}")

    # CONTINUE：node_end ok + YAML 出边
```

`_bump_heal`：初始化 `run.heal`（enabled/round/max_rounds），`round += 1`，写入 last_reason/from/to，`save_run`。

RERUN_WITH_SUMMARY：构造 `AgentRunContext` 不变，把 `node.input` 渲染后并入 `{"heal_summary": result.error, "tool_summary": result.tool_calls[-8:]}`，再调 `agent_runner.run`。成功则覆盖 outputs；失败则按预算 HANDOFF 或再 GOTO（本轮只重开一次，避免死循环）。

瞬时机已经在 `_run_agent_node` 内部消化，Policy 的 RETRY_NODE 不会在 schedule 层再套一层。即：`_run_agent_node` 内部对 transient 重试；schedule 层 `decide` 看到的是重试之后的最终 result。若最终仍 transient 且 success=False，decide 会再给 RETRY_NODE——**schedule 层若收到 RETRY_NODE 视为已在 _run_agent_node 用尽，改走 AGENT_FAILED 路径（GOTO 或 HANDOFF）**。在 Policy 增加参数 `transient_retries_exhausted: bool` 太绕。更简单：**decide 的 RETRY_NODE 只给 _run_agent_node 用**；schedule 层若 `action==RETRY_NODE` 则当作 AGENT_FAILED 再 decide 一次，或 Policy.decide 增加 `phase="after_node_retries"`。

实现约定（锁死）：

- `_classify_for_retry(error) -> bool` 小函数与 Policy 共用 `is_transient_error`
- `_run_agent_node` 只用 `is_transient_error` 做重试，不调用完整 decide
- schedule 层 `decide` 看到的已是最终 result；此时 transient 失败走步骤 6 AGENT_FAILED（GOTO debug/coding），不再 RETRY_NODE

因此 Task 1 的 `test_transient_retry_node` 仍对：**Policy 在看到 transient 失败时返回 RETRY_NODE**；引擎 `_run_agent_node` 用同一函数重试。schedule **忽略** RETRY_NODE（不应再出现，因为瞬时已重试完；若仍出现则转步骤 6）。在 `decide` 增加可选参数 `allow_transient_retry: bool = True`。schedule 调用 `decide(..., allow_transient_retry=False)`，此时 transient 落入 AGENT_FAILED。

更新 Task 1 测试：默认 allow_transient_retry=True。引擎测试覆盖用尽后 GOTO。

- [ ] **Step 3: pytest** `tests/unit/test_engine_self_heal.py tests/unit/test_workflow_engine.py tests/unit/test_w3_branch_human.py -q`

- [ ] **Step 4:** resume 路径不调用 decide（已满足）。人工 reject 不自愈。Commit 跳过。

---

### Task 5: YAML 默认参数

**Files:**
- Modify: `backend/apps/demo-code-agent/workflows/deliver.yaml`
- Modify: `backend/examples/deliver/workflow.yaml`

在 `params` 增加（不改 edges）：

```yaml
  self_heal: true
  heal_max_rounds: 3
  heal_on_review_blocking: true
```

文件头注释补一句：审查 blocking 与节点失败由引擎 SelfHealPolicy 自动回 coding/debug，满轮次后再 human_review。

---

### Task 6: 前端展示

**Files:**
- Modify: `src/components/RunMonitor.tsx`
- Modify: `src/pages/StudioPage/StudioPage.tsx`

RunMonitor：

- `onEvent`：`heal_attempt` 时把对应 `from` 节点标为 `retry`；可选读取 `round/max_rounds` 存入 state `healLabel`
- 顶栏 `runStatus` 旁：若有 heal 则显示「自愈 {round}/{max_rounds}」琥珀色 Badge
- 事件流 className：`heal_attempt` 与 `heal_handoff` 使用 `text-amber-600`；handoff 可用 `text-orange-700`
- 事件文本：`heal_attempt` 显示 `{reason} {from}→{to} {round}/{max_rounds}`

Studio `onProgress`：

```typescript
} else if (evtType === 'heal_attempt') {
  tip = `↻ 自愈 ${event.round}/${event.max_rounds}：${event.reason} ${event.from}→${event.to}`
} else if (evtType === 'heal_handoff') {
  tip = `⚑ 自愈轮次用尽，等待确认：${event.reason || ''}`
}
```

无前端单测则对照 `node_retry` 样式手工看。Commit 跳过。

---

### Task 7: 回归

```
cd backend
python -m pytest tests/unit/test_self_heal_policy.py tests/unit/test_agent_runtime.py tests/unit/test_engine_self_heal.py tests/unit/test_workflow_engine.py tests/unit/test_w3_branch_human.py tests/unit/test_app_deliver_ac08.py -q
```

Expected: PASS。`self_heal: false` 与 hello-workflow 行为与改前一致。

---

## Spec coverage

| Spec 节 | Task |
|---------|------|
| AgentRuntime chat_with_retry / 收尾 / 摘要重开 | 2, 4 |
| SelfHealPolicy 分流 | 1, 4 |
| heal_max_rounds / HANDOFF | 1, 4 |
| testing → YAML debug + classifier | 1, 4 |
| review blocking → coding | 1, 4 |
| 瞬时不计 heal | 1, 4 |
| RunRecord.heal + 事件 | 3, 4, 6 |
| YAML 不改边 | 5 |
| 前端 | 6 |
| self_heal false / hello | 1, 4, 7 |
| 不做 Supervisor / 跨 run 记忆 | 全计划未包含 |
