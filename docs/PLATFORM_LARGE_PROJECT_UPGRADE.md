# 平台升级：让多 Agent 自己写出高级大项目

目标不是再做一个旁路页面，而是**升级智流 MAWP 这套多 Agent 编排本身**，使 Studio Deliver / 八链路能够在隔离工作区内分期生成可运行的多模块工程。

## 能力缺口（平台层）

| 缺口 | 后果 |
|------|------|
| Coding `max_steps` 过低 | 写不完多文件工程树 |
| 一次一文件、无批量写入 | 步数被工具往返吃光 |
| Frontend 路径白名单过窄 | 无法在 `workspaces/*/apps/web` 落盘 |
| Deliver 无 `project_mode` | 目标默认写成平台仓库里的小改动 |
| Advanced 用模板生成 | 与八 Agent 主链脱节，谈不上「平台自己写」 |

## 升级原则

1. **主链升级优先**：改 `HybridAgentRunner` / `deliver_specs` / tools / policy，而不是堆模板。
2. **隔离工作区**：大项目写入 `workspaces/<id>/`，不污染平台源码。
3. **分期 = 多次 Deliver**：每个里程碑一次八 Agent 跑，而不是一次幻想整仓。
4. **有 Key 走 LLM，无 Key 多文件骨架兜底**：保证链路可演示、可联调。

## 本轮落地（P0）

- [x] 路线图（本文）
- [x] Coding/Frontend 提高 `max_steps`；大项目专用 system prompt
- [x] 新增 `write_files` 批量写工具
- [x] Policy 放行 `workspaces/**` 前端目录
- [x] `POST /studio/deliver` 支持 `project_mode` / `project_root` / `srs_excerpt`
- [x] Advanced「生成当前期」默认走八 Agent Deliver（模板仅作无 LLM 回退）
- [x] Studio 增加「大项目工程模式」开关

## 下一轮（P1）

- [x] Coding 按 planner 任务循环（子运行，`coding_max_tasks` 默认 5）
- [x] 真实 `metric_command` 验收（`scripts/smoke_check.py` py_compile + web 入口）
- [x] Advanced/Studio 自动写入冒烟脚本与 `ACCEPTANCE_*.md`
- [x] Studio / 高级项目页展示 `changed_files`、`task_runs`、验收日志
- [x] ZIP 导出与复制工作区路径

## P2（下一阶段）

- [x] 失败任务自动回投 Coding（Debug 带 testing 失败上下文真修，最多 5 轮）
- [x] 冒烟加强：requirements / 入口框架标记检查
- [x] 工程树预览（高级项目工作区树 + Studio Deliver changed_files）
- [x] 工作区文件点击预览（`GET .../file`）
- [x] 冒烟 Live 探活：`TestClient` 打 `GET /health`（可用 `MAWP_SMOKE_LIVE=0` 关闭）
- [x] p2+ 分期模板加厚：缴费 / 后台 / 通用可运行增量（不再只写空 md）
- [x] 分期依赖图与进度条（高级项目页）
- [x] 文件基线对照 diff（生成前后行级对比）
- [x] 多期并行调度（依赖波次 + 沙箱并行合并，`parallel_workers`）
- [x] 前端 build 级冒烟（可选 auto-install：`MAWP_SMOKE_WEB_INSTALL`）
- [x] Deliver 轮询默认 40 分钟（`MAWP_DELIVER_POLL_SECONDS`）
- [x] project_mode 强制真实冒烟，禁止 LLM/演示首轮放行
- [x] 分期模板增量挂载（禁止后期覆盖前期 `main.py` 路由）；冒烟校验 `/api/repairs` 仍在

## 成功标准

上传邻智云级 SRS → 建高级项目 → **生成第 1 期触发 Deliver** → `workspaces/ap-*/` 内出现多文件 API+Web，且 `coding.changed_files` 来自 Agent 工具调用（有 API Key 时）；Testing 节点跑真实 `metric_command` 而非 `pass_on_attempt` 模拟；失败后 Debug 会回投修复再测。
