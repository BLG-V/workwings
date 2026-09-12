# 智流 MAWP · 后端（Gitee 第一版内核）

本目录来自 [multi-agent-workflow-platform](https://gitee.com/liziyu7/multi-agent-workflow-platform)，作为 **Python 工作流内核** 嵌入当前 React 前端项目。

## 职责划分

| 层 | 位置 | 说明 |
|----|------|------|
| UI | 仓库根目录 `src/` | 保留现有智流页面与交互 |
| 内核 | `backend/src/mawp/` | YAML 编排、八 Agent、Tool、LLM、Run 存储 |
| HTTP | `backend` → `:8787` | `/api/health`、`/api/platform/*` 供前端代理调用 |

数据默认仍用本机文件（`.mawp/`）+ 前端 localStorage，**不强制数据库**。

## 安装

```bash
# 在仓库根目录
npm run backend:install
# 或
pip install -e "./backend[dev,web]"
```

复制配置：

```bash
copy backend\mawp.config.yaml.example backend\mawp.config.yaml
copy backend\.env.example backend\.env
# 填写 DEEPSEEK_API_KEY
```

## 启动

```bash
# 终端 1：API（默认 127.0.0.1:8787）
npm run backend:serve

# 终端 2：前端
npm run dev
```

前端通过 Vite 代理访问：`/api/mawp/*` → `http://127.0.0.1:8787/api/*`。

## 按 Agent 分模型

见 `mawp.config.yaml` 中 `agents.models`：

- Coding / Frontend / Debug → `deepseek-v4-pro`
- Planner / Requirement / Testing / Review / Ship → `deepseek-v4-flash`

## CLI（可选）

```bash
platform validate backend/examples/hello-workflow/workflow.yaml
platform run backend/examples/hello-workflow/workflow.yaml
platform status <run_id>
```

注意：CLI 的工作目录需能解析到 `mawp.config.yaml`（建议在 `backend/` 下执行，或设置 `workspace`）。
