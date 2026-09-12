# deliver 样例（A · UC-07 骨架 + C Testing/Ship）

`platform validate/run/deliver` 可跑通 Planner → Coding → Testing（可回环 Debug）→ Review → Ship。  
- Testing：可跑真实 `metric_command`；未提供时兼容 `pass_on_attempt` 演示逻辑。  
- Ship：生成交付说明，**禁止**自动 push/merge。

## 命令

```bash
pip install -e ".[dev]"

platform validate examples/deliver/workflow.yaml

# 推荐：C 的 deliver（会打印当前 Agent + Run 摘要）
platform deliver examples/deliver/workflow.yaml

# 快乐路径：首测通过 + Review pass → DONE
platform run examples/deliver/workflow.yaml

# Testing fail → Debug → Retest（第二次通过）
platform deliver --params pass_on_attempt=2

# UC-07：Review blocking → WAITING_USER → approve → Ship → DONE
platform deliver --params review_status=blocking
platform status <run_id>
platform approve <run_id>

# 真实 metric_command（exit 0 = pass）
platform deliver --params metric_command="python -c \"import sys; sys.exit(0)\""
```

## 字段契约

见 `docs/w4-ad-deliver-yaml-align.md`（与 D 对齐冻结）。
