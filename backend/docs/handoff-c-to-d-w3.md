# C → D · W3 命令清单（李铭宇）

> 分支工作目录：`multi-agent-workflow-platform-feat-a-w3-condition-human`（基于 A 的 condition/human）  
> 日期：2026-08-13  
> **约束：** 仅改 CLI/展示层，未改引擎。

## 1. W3 人工确认相关命令（请写进样例 README / 演示稿）

| 命令 | 作用 | 成功 exit | 失败 exit |
|------|------|-----------|-----------|
| `platform validate <yaml>` | 校验 workflow（含 condition/human） | 0 | ≠0 |
| `platform run <yaml>` | 执行；高危停在 `WAITING_USER` | 0（含合法暂停） | ≠0 |
| `platform run <yaml> --params key=value` | 覆盖参数（可重复） | 同上 | ≠0 |
| `platform run <yaml> --param key=value` | 同 `--params`（兼容旧写法） | 同上 | ≠0 |
| `platform status <run_id>` | Run 摘要（耗时 / 等待原因 / 失败原因 / 下一步） | 0 | ≠0（未找到） |
| `platform approve <run_id>` | 人工批准并恢复 | 0 | ≠0（非 WAITING） |
| `platform reject <run_id>` | 人工拒绝并沿出边继续 | 0 | ≠0 |
| `platform input <run_id> --text "..."` | 写入 `outputs.input` 并恢复 | 0 | ≠0 |

## 2. UC-06 复制即跑

```bash
pip install -e ".[dev]"
copy mawp.config.yaml.example mawp.config.yaml

platform validate examples/branch-human/workflow.yaml
platform run examples/branch-human/workflow.yaml
# 终端会打出黄色 WAITING_USER 面板：run_id / reason / allowed / 下一步命令

platform status <run_id>
platform approve <run_id>
platform status <run_id>
# 期望：DONE
```

低危直通：

```bash
platform run examples/branch-human/workflow.yaml --params risk=low
```

可选：

```bash
platform reject <run_id>
platform input <run_id> --text "改用灰度发布"
```

## 3. C 已打磨的交互行为（D 文档可点一句）

1. `run` 停在人工确认时：rich 面板展示 `run_id`、`reason`、`allowed`、可复制的下一步命令；**exit 0**。  
2. `status`：统一「Run 摘要」（duration / wait_reason / error / events）+ WAITING 时高亮建议命令。  
3. `approve`：若 `run_id` 存在则走 human resume；否则回落 legacy Issue 授权（与 Goal `GW-*` 共存，无重复命令注册）。

## 4. 请 D 同步的文档位置

- `examples/branch-human/README.md`（命令表可直接引用 §1）  
- `docs/w3-demo-script.md` UC-06 口述段  
- `README.md` 快速开始（已有骨架，确认与上表一致即可）  
- 接口一页纸 §4 exit 约定：WAITING_USER → **0**（已与 A 对齐）

## 5. 联系人

- C CLI / 提示：李铭宇  
- D 样例文档：孙浩铭  
- A 引擎：王振同  
