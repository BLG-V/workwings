# 智流 MAWP / AgentFlow

前端 UI（本仓库根目录）+ Python 多 Agent 工作流内核（`backend/`，来自 Gitee 第一版）。

## 架构

```
浏览器 React UI  ──/api/mawp/*──►  Vite 代理  ──►  FastAPI :8787  ──►  mawp 内核
                     │
                     └──/api/deepseek/*──► DeepSeek（对话页）
```

- **页面**：继续用现在的智流界面（对话、Studio、项目、运行、设置…）
- **技术内核**：`backend/src/mawp`（YAML 编排、八 Agent、Tool、Run 文件存储）
- **暂不强制数据库**：后端 `.mawp/` 文件 + 前端 localStorage

## 快速开始

```bash
# 1) 前端依赖
npm install

# 2) 后端内核（Python 3.11+）
npm run backend:install
copy backend\mawp.config.yaml.example backend\mawp.config.yaml
# 在 backend\.env 或根目录 .env.local 填写 DEEPSEEK_API_KEY

# 3) 两个终端
npm run backend:serve   # http://127.0.0.1:8787
npm run dev             # Vite 前端
```

## 按 Agent 分模型

配置见 `backend/mawp.config.yaml` → `agents.models`：

| Agent | 默认模型 |
|-------|----------|
| coding / debug / frontend / requirement | deepseek-v4-pro |
| planner / testing / review / ship | deepseek-v4-flash |

## 目录

```
agentflow/
├── src/                 # React 前端（保留）
├── backend/             # Gitee MAWP 内核
│   ├── src/mawp/
│   ├── examples/
│   ├── apps/demo-code-agent/
│   └── README.md
├── package.json
└── vite.config.ts       # 代理 /api/mawp → :8787
```

前端 API 封装：`src/lib/mawp-api.ts`。

## 下一阶段（计划接线）

1. Studio 五步流程 → 调用 deliver 八 Agent 链  
2. 工作流编排页 → validate / run / approve  
3. 运行记录页 ↔ 平台 Run 完全打通  

当前运行记录页已能探测内核是否在线，并列出 `backend/.mawp` 中的平台 Run。
