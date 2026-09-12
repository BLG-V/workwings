# A → C · W3 CLI 交接说明（王振同）

> 引擎分支：`feat/a-w3-condition-human`（已推送）  
> 文档分支参考：`feat/d-w3-branch-human-docs`  
> 日期：2026-08-13

## 1. A 已落地（C 可直接联调）

| 能力 | 说明 |
|------|------|
| `platform validate <yaml>` | 含 condition 出边 `when` / human `reason`+`allowed` 校验 |
| `platform run <yaml>` | 高危默认进 `WAITING_USER`；**exit code = 0**（合法暂停） |
| `platform run ... --params key=value` | 可重复传入，如 `--params risk=low` |
| `platform status <run_id>` | 读 `.mawp/runs/` |
| `platform approve\|reject\|input <run_id>` | 仅 `WAITING_USER`；非法状态 exit ≠ 0 |
| `platform input <run_id> --text "..."` | 写入 `nodes.<id>.outputs.input` |

Checkpoint 落盘：`.mawp/checkpoints/<run_id>.json`  
恢复后产出：`nodes.<human_id>.outputs = { decision, input }`

## 2. 请 C 主责打磨（避免和 A 抢同一大段逻辑）

1. **等待提示文案**：run 停住时的 rich 面板/颜色/「下一步」文案统一（A 已有基础打印）。  
2. **status 增强**：WAITING_USER 时高亮 `reason` / `allowed` / 建议命令。  
3. **（可选）** `--param` 单数别名，与 README 旧写法兼容。  
4. **不要改** edges.when / reason / decision 字段语义；有争议先改 `docs/interfaces/w1-api-onepager.md` §5。

## 3. 建议 C 分支合入顺序

1. 先 merge / rebase `feat/a-w3-condition-human`（或等其合入 `main`）  
2. 在 `feat/c-w3-approve-status` 上只改 CLI 展示层  
3. 用下方 UC-06 命令自测后再提 PR

## 4. UC-06 联调命令（验收）

```bash
pip install -e ".[dev]"
copy mawp.config.yaml.example mawp.config.yaml

platform validate examples/branch-human/workflow.yaml
platform run examples/branch-human/workflow.yaml
platform status <run_id>
platform approve <run_id>
platform status <run_id>
```

低危路径：

```bash
platform run examples/branch-human/workflow.yaml --params risk=low
```

## 5. 联系人

- A 引擎 / resume：王振同  
- C CLI / 提示：李铭宇  
- D 样例文档：孙浩铭  
