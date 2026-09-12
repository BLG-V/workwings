# W4 · `app.yaml` 字段说明（随 demo-code-agent 落地）

> 作者：D（孙浩铭）  
> 状态：**已实例化 AC-08** → `apps/demo-code-agent/`（装卸逻辑仍待评审）

## 目标

把「可装卸业务包」与平台内核解耦：一个 App = 清单 + 工作流 +（可选）Agent/Tool 插件。

## 官方实例

| 路径 | 说明 |
|------|------|
| `apps/demo-code-agent/` | 8 Agent + 生成页 / AC-08 |
| `apps/demo-code-agent/app.yaml` | 完整字段 + 八 Agent |
| `apps/demo-code-agent/workflows/deliver.yaml` | 对齐 A 契约并含 Frontend |
| `examples/sdk-min/` | `register_tool` / `register_agent` 最小样例 |
| `docs/w4-ad-deliver-yaml-align.md` | A↔D outputs / 拓扑冻结 |

## 最小字段

```yaml
id: demo-code-agent
name: Demo Code Agent
version: "0.2.0"
description: "8 Agent + generated page"
entry_workflow: workflows/deliver.yaml
workflows:
  - id: deliver
    path: workflows/deliver.yaml
agents:
  - name: requirement
    ref: agents/requirement.yaml   # 或内联 system_prompt/tools/output_schema
  - name: frontend
    ref: agents/frontend.yaml
plugins_dir: plugins/
policy:
  inherit: platform
authors: [mawp]
tags: [demo, w4, ac-08]
```

八 Agent：`planner` · `requirement` · `coding` · `frontend` · `testing` · `debug` · `review` · `ship`

`agents[]` 内联字段必须可映射到 `mawp.runtime.AgentSpec`：  
`name` / `system_prompt` / `model` / `tools` / `max_steps` / `output_schema`。

## 建议目录

```text
apps/<app-id>/
  app.yaml
  agents/
  workflows/
  frontend/         # 可选，生成页 mock
  plugins/
  samples/
  README.md
```

## 与现有样例关系

| 现有 | W4 去向 |
|------|---------|
| `examples/hello-workflow` | 内核冒烟，保留 |
| `examples/branch-human` | UC-06 |
| `examples/deliver` | A 引擎骨架；App 在此基础上加 Requirement/Frontend |
| Legacy Goal / gstack | 规格迁入 `apps/demo-code-agent` |

## 开放问题（评审用）

1. App 安装后工作流 ID 是否加命名空间（`demo-code-agent/deliver`）？  
2. `platform app install/uninstall` 与 Python entry point 谁先落地？  
3. policy 覆盖是 merge 还是 replace？  
4. `agents[].ref` 由谁在 run 前装入 AgentRuntime（A mock 已可跑；真装载器归 D）？
