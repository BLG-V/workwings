# W3 周五演示剧本草稿（AC-01 + UC-06）

> 口述约 5～8 分钟。演示人前确认：`pip install -e ".[dev]"` 已完成，且 A/C 相关 PR 已合入 `main`。

---

## 0. 开场（30 秒）

「本周目标只有一件事：通用工作流能做**条件分支**，并在高危路径上**停下来等人确认**，确认后再继续跑完。」

指一下：`examples/branch-human/workflow.yaml` 图结构（可投屏 README 里的 ASCII 图）。

---

## 1. AC-01 回归 · hello（约 1 分钟）

```bash
platform validate examples/hello-workflow/workflow.yaml
platform run examples/hello-workflow/workflow.yaml
platform status <run_id>
```

**口述要点：**

- W2 最小闭环仍然绿：不依赖真 LLM，echo 走 ToolRegistry。
- 状态：`INIT → RUNNING → DONE`。

**失败兜底：** 若 hello 挂了，先修环境/`mawp.config.yaml`，不要继续 UC-06。

---

## 2. UC-06 · 人工确认（约 3 分钟）

```bash
platform validate examples/branch-human/workflow.yaml
platform run examples/branch-human/workflow.yaml
```

**口述要点（run 停住时）：**

1. `params.risk=high` → condition 选中人工边。  
2. Run 进入 `WAITING_USER`，checkpoint 含 `run_id / node_id / reason / allowed`。  
3. 终端应打印下一步：`platform approve <run_id>`（C 的提示）。

```bash
platform status <run_id>
platform approve <run_id>
platform status <run_id>
```

**口述要点（approve 后）：**

- 状态回到 `RUNNING`，经 `after_human` 到 `end` → `DONE`。  
- 强调：这是**通用** Human 协议，不是旧 Goal 的 `agent approve`。

**可选加戏（30 秒）：** 再开一次 run，演示 `reject` 或 `input`（若已实现）。

---

## 3. AC-03 · 高危策略（约 1 分钟，B 主讲可接）

```bash
pytest tests/unit/test_policy_hazard.py -q
```

**口述要点：** 高危默认拒绝（或转 Human），有审计、无密钥明文。

---

## 4. 收尾（30 秒）

「验收命令全组一致，写在 `docs/W3-四人任务卡.md`。新人只看 `examples/branch-human/README.md` 应能独立复现 UC-06。」

---

## 演示检查清单

- [x] hello validate/run 绿（A 回归单测覆盖）  
- [x] branch-human validate 绿  
- [x] run 停在 WAITING_USER 且有 reason（引擎 + CLI 已实现）  
- [x] approve 后 DONE  
- [ ] （可选）policy 单测绿（B）  
- [ ] 投屏准备好 YAML / README / 本剧本（D/全组周五）  

## A 收尾状态（2026-08-13）

- 分支：`feat/a-w3-condition-human` 已推送  
- 对齐纪要：`docs/w3-ad-yaml-align.md` 四个问题已拍板  
- C 交接：`docs/handoff-a-to-c-w3.md`  
- PR 说明：`docs/pr-a-w3-condition-human.md`  
