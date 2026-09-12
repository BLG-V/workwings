# C · Testing + Ship / UC-07 交付说明（李铭宇）

> 工作目录：`multi-agent-workflow-platform-feat-a-w3-condition-human`  
> 基于：`feat/a-deliver-planner-review`（已 merge）+ C W3 CLI  
> 日期：2026-08-14

## 1. 已完成

| 项 | 说明 |
|----|------|
| Testing Agent | `src/mawp/runtime/testing_agent.py`：跑 `metric_command`，outputs 含 `passed`/`status`/`failures`/`log_summary`/`attempt` |
| Ship Agent | `src/mawp/runtime/ship_agent.py`：生成 `delivery_notes`，`auto_push=false` / `auto_merge=false`，写入 `.mawp/deliveries/<run_id>.md` |
| CLI `deliver` | 显示当前 Agent；WAITING 时提示 approve；完善 Run 摘要（testing/review/ship） |
| 可选 | `platform app list/enable/disable`（扫描 `apps/*/app.yaml`，与 D 联调） |

## 2. UC-07 演示（Ship → approve → DONE）

```bash
pip install -e ".[dev]"
copy mawp.config.yaml.example mawp.config.yaml

platform validate examples/deliver/workflow.yaml
platform deliver --params review_status=blocking
# 停在 human_review：打印 run_id 与下一步 platform approve <run_id>

platform approve <run_id>
# → Ship 生成交付说明 → DONE
```

## 3. 约束

- **不改** condition / human / loop 引擎语义（仅注入 `MockAgentRunner(workspace)`）。  
- Ship **永不**调用 git push / merge。  
- 无 `metric_command` 时 Testing 回退 A 的 `pass_on_attempt` 演示逻辑，保证原单测仍绿。

## 4. 给 D

- 命令表见上；App 装卸：`platform app list` / `platform app enable <id>`（需把 `apps/demo-code-agent` 放到 workspace）。  
- outputs 键名保持 `docs/w4-ad-deliver-yaml-align.md` 冻结契约。
