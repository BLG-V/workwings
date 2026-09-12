# UC-07 · 最小需求样例（Requirement v1.2 / AC-07）

> 用途：喂给 Requirement Agent → Planner，演示「小需求可规划 + 人工确认计划」。  
> 对应工作流：`workflows/deliver.yaml`（默认 `params.requirement_text` 与本文一致）。

## 用户原话

给 CLI 增加 `platform version` 命令，打印当前安装的 `mawp` 包版本号，并补一条单测。

## 期望 Requirement 输出要点

| 字段 | 期望 |
|------|------|
| summary | 增加 version 命令展示包版本 |
| goals | 用户可在终端查看版本；有单测覆盖 |
| non_goals | 不做在线升级检查；不改 Web UI |
| acceptance_criteria | `platform version` exit 0；输出含版本号；单测绿 |
| tasks（粗） | T1 实现命令；T2 补测试 |

## 期望 Planner 输出要点

| 字段 | 期望 |
|------|------|
| plan_id | PLAN-UC07-001 |
| tasks | ≥2 条，含 depends_on / priority=P0 / owner_hint |
| human_checkpoints | 至少 1 条：确认计划后再编码 |
| blockers | 通常为空 |

## 人工确认（AC-07）

Run 在 `approve_plan` 进入 `WAITING_USER` → `platform approve <run_id>` → 继续到 DONE。

## 口述一句话（演示用）

「UC-07：小需求先被 Requirement 结构化，再被 Planner 拆成任务清单，人点头后才允许编码。」
