# UC-08 / AC-08 · 最小需求样例（含前端页）

> 喂给 Planner → Requirement → … → Frontend。默认 `params.goal` 可与本文一致。

## 用户原话

做一条可演示的交付骨架：规划任务、收紧需求（含 UI 要点）、编码、生成状态页，测试可失败回环，Review blocking 需人工确认，Ship 禁止自动 push。

## Planner.tasks（期望键）

| id | title | depends_on |
|----|-------|------------|
| T1 | implement feature from goal | [] |
| T2 | generate status page (frontend) | [T1] |

## Requirement 收紧要点

- 继承 `planner.outputs.tasks`（勿改 id/title/depends_on 键名）
- `ui_key_points`：主页面展示交付状态；Ship 前人工确认入口
- `acceptance_criteria`：可打开 mock HTML；主链到 Ship；无自动 push

## Frontend 产物

- 目录：`apps/demo-code-agent/frontend/`
- 至少：`index.html`（可为 mock）
