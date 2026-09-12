# branch-human

W3 样例：`condition` 分支 + `human_checkpoint` 人工确认（UC-06）。

```text
start → prep(echo) → check_risk
                       ├─ risk=high → approve_deploy(human) → after_human → end
                       └─ default   → auto_ok → end
```

> **依赖：** W3 已合入 `main`（condition/human/resume + CLI approve）。  
> C 交互说明见 `docs/handoff-c-to-d-w3.md`；YAML 字段见 `docs/interfaces/w1-api-onepager.md` §5。

## 安装

```bash
pip install -e ".[dev]"
copy mawp.config.yaml.example mawp.config.yaml
```

## UC-06：高危路径（默认 `params.risk=high`）

```bash
platform validate examples/branch-human/workflow.yaml

platform run examples/branch-human/workflow.yaml
# 期望：打印 run_id，状态 WAITING_USER，提示 reason 与下一步命令（exit 0）

platform status <run_id>
# 期望：WAITING_USER，当前节点 approve_deploy

platform approve <run_id>
# 期望：恢复执行 → DONE

platform status <run_id>
# 期望：DONE
```

可选：拒绝 / 带输入恢复

```bash
platform reject <run_id>
platform input <run_id> --text "改用灰度发布"
```

## 低危自动路径（无人工暂停）

```bash
platform run examples/branch-human/workflow.yaml --params risk=low
# 期望：不进入 WAITING_USER，直接 DONE
```

> CLI 使用可重复的 `--params key=value`（A 已落地）。若看到旧文档写 `--param`，请改用 `--params`。

## 与 hello 对照

| 样例 | 路径 | 验收点 |
|------|------|--------|
| hello-workflow | `examples/hello-workflow/` | AC-01：validate + run → DONE |
| branch-human | `examples/branch-human/` | UC-06：WAITING_USER → approve → DONE |

## 字段对齐（给 A）

见仓库根目录任务卡 `docs/W3-四人任务卡.md` 与接口一页纸 §5。变更字段请先改文档再改引擎。
