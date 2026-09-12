# demo-code-agent

官方 demo App（W4）：**8 Agent + 生成页 / AC-08**。

```text
planner → requirement → coding → frontend → testing ↔ debug → review → ship
                                         └─ Review blocking → human → ship
```

契约：`docs/w4-ad-deliver-yaml-align.md`（与 A 冻结；**勿改 outputs 键名**）。  
引擎对照样例：`examples/deliver/workflow.yaml`。

## 目录

```text
apps/demo-code-agent/
  app.yaml
  agents/{requirement,planner,frontend}.yaml
  workflows/deliver.yaml
  frontend/index.html          # mock 生成页
  samples/uc08-mini-requirement.md
  plugins/hello_plugin.py
  README.md
```

八 Agent：`planner` · `requirement` · `coding` · `frontend` · `testing` · `debug` · `review` · `ship`

## 安装

```bash
pip install -e ".[dev]"
copy mawp.config.yaml.example mawp.config.yaml
```

## 新人复制即跑（到 Ship → approve 骨架）

```bash
# 1) 校验 App 交付流
platform validate apps/demo-code-agent/workflows/deliver.yaml

# 2) 快乐路径：首测通过 + Review pass → DONE（含 Frontend mock）
platform run apps/demo-code-agent/workflows/deliver.yaml

# 3) Testing fail → Debug → Retest
platform run apps/demo-code-agent/workflows/deliver.yaml --params pass_on_attempt=2

# 4) Review blocking → WAITING_USER → approve → Ship
platform run apps/demo-code-agent/workflows/deliver.yaml --params review_status=blocking
platform status <run_id>
platform approve <run_id>
platform status <run_id>
```

期望：步骤 2/3 → `DONE`；步骤 4 先 `WAITING_USER`（`human_review`），approve 后 `DONE` 且 `ship.auto_push=false`。

生成页 mock：`apps/demo-code-agent/frontend/index.html`（Frontend Agent 会在 outputs 里引用）。

## SDK 最小样例

```bash
python examples/sdk-min/register_example.py
```

## 本周完成定义

- App `deliver.yaml` 与 A 契约一致，并含 Frontend  
- 新人只看本 README 能跑到 Ship / approve 骨架  

演示口述稿：`docs/w4-demo-script-ac08.md`  
字段对齐：`docs/w4-ad-deliver-yaml-align.md`  
C 的 CLI 命令表（可复用）：`docs/handoff-c-to-d-w3.md`  
