# B · W4 Coding/Debug 交接说明

> 分支：`feat/b-w4-coding-debug`  
> 负责人：李子玉（B）

## 已完成

1. **`HybridAgentRunner`**（`src/mawp/runtime/hybrid.py`）  
   - Coding / Debug 经 `ToolRegistry` 真实写文件  
   - 其余 Agent 回退 `MockAgentRunner`（保持 A/D 契约键名）  
   - `AgentRuntimeAsRunner`：兼容引擎传入 `agent_runtime=`

2. **引擎默认切换**（`WorkflowEngine`）  
   - 默认 `HybridAgentRunner`  
   - 仍支持 `agent_runner=` / `agent_runtime=`

3. **八 Agent 工具白名单**（`tools/registry.py`）  
   - 增补 planner / frontend / debug / ship  
   - Coding/Debug/Frontend 可 `write_file`/`edit_file`  
   - Debug 可有限 `run_terminal_cmd`（仍受高危策略拦截）

4. **策略**（`security/policy.py`）  
   - `WRITE_AGENTS = {coding, debug, frontend}`  
   - Frontend 仅允许 `frontend/`、`apps/demo-code-agent/frontend/`

5. **测试**  
   - 新增 `tests/unit/test_coding_debug_runner.py`  
   - 相关单测已绿

## 契约（勿改键名）

- Coding outputs：`status` / `changed_files` / `tasks_done`（另可增 `api_contract`）  
- Debug outputs：`status` / `fixed` / `based_on_failures` / `note`  
- 对齐文档：`docs/w4-ad-deliver-yaml-align.md`

## 自测

```bash
pytest tests/unit/test_coding_debug_runner.py tests/unit/test_policy_hazard.py tests/unit/test_deliver_planner_review.py tests/unit/test_agent_runtime.py -q
platform validate examples/deliver/workflow.yaml
platform run examples/deliver/workflow.yaml
```

## 请 C / D 注意

- C：Testing/Ship 可继续 mock；Ship→approve 联调时 Coding 会在工作区写出 `src/mawp_coding_stub.py`  
- D：Frontend 写入路径需落在允许前缀内
