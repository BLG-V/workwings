# ADR-001：Phase 1 MVP 技术决策

| 属性 | 说明 |
|------|------|
| 状态 | 已采纳 |
| 日期 | 2026-06-27 |
| 关联 | 需求文档 §13.4 开放问题 OQ-001 ~ OQ-004 |

---

## 背景

需求文档 v2.0 处于评审稿阶段，存在 4 项开放问题需在架构设计与开发启动前定案。本文档记录 Phase 1 MVP 的默认决策；若后续评审有变更，以新 ADR  supersede 本文。

---

## 决策

### OQ-001：初版默认 LLM 厂商与模型

**决策：** 以 **DeepSeek V4** 为主模型；通过 LLM Adapter 抽象层接入，**不绑定单一厂商 API 形态**。

**推荐接入方式（二选一，与现有环境对齐即可）：**

| 方式 | 适用场景 | Provider 配置 | 模型 ID |
|------|---------|--------------|---------|
| **A. Anthropic 兼容**（你当前「Claude 连 DeepSeek」） | 已用 Claude SDK / `api.deepseek.com/anthropic` | `anthropic` + 自定义 `base_url` | `claude-sonnet-*`（自动路由至 V4-Flash）或显式 `deepseek-v4-pro` |
| **B. OpenAI 兼容** | 直接用 DeepSeek 官方 OpenAI 端点 | `openai` + `base_url=https://api.deepseek.com` | `deepseek-v4-pro` / `deepseek-v4-flash` |

**默认模型选择：**
- **编码 / Agent 主流程：** `deepseek-v4-pro`（长程任务、代码生成更强）
- **轻量 / 高并发：** `deepseek-v4-flash`（更快、更省）

**备选 failover：** OpenAI GPT-4o 或本地 Ollama（Phase 1 可选）

**理由：**
- DeepSeek V4 支持 1M 上下文，适合代码库 RAG + 多轮 Session
- 官方同时提供 OpenAI / Anthropic 双格式，Adapter 层可复用现有接入习惯
- Agent 依赖 **Tool Use / Function Calling**，接入后需在 S4 阶段做一次连通性验证

**环境变量（方式 A — Anthropic 兼容，推荐给你）：**
```
LLM_PROVIDER=anthropic
LLM_BASE_URL=https://api.deepseek.com/anthropic
LLM_MODEL=deepseek-v4-pro
DEEPSEEK_API_KEY=...              # 或 ANTHROPIC_API_KEY=...（按你现有配置）
```

**环境变量（方式 B — OpenAI 兼容）：**
```
LLM_PROVIDER=openai
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-pro
DEEPSEEK_API_KEY=...
OPENAI_API_KEY=...                # 备选 failover / RAG 嵌入
```

---

### OQ-002：Review Agent 是否允许自动 merge

**决策：** **禁止自动 merge / push**。Agent 仅生成 diff、测试报告、Review 摘要与 commit message 建议；Git commit 与 PR 创建需用户显式 `agent approve` 授权。

**理由：**
- 对齐需求 §1.3 范围外说明与 ADP-031
- 降低 R-001（LLM 幻觉）、R-004（终端安全）风险
- Phase 2 可引入「受策略控制的 auto-commit」（ENT-005）

---

### OQ-003：Session 数据是否上传云端

**决策：** **默认本地/私有化部署**。Session、Memory、RAG 索引、审计日志均存储在用户 workspace 下的 `.agent/` 目录；不上传至第三方 SaaS。

**理由：**
- 满足企业合规与 NFR-S01（密钥不出现在 Prompt/日志）
- Phase 1 单机/Docker 部署形态足够
- Phase 3 若需多租户 SaaS，再引入 org 级云端存储（OQ-004）

**存储路径（默认）：**
```
<workspace>/.agent/
├── sessions/       # Session + Memory（SQLite）
├── index/          # RAG 向量索引（Chroma）
├── audit/          # 审计日志（JSONL）
└── checkpoints/    # Checkpoint 快照元数据
```

---

### OQ-004：多租户隔离粒度

**决策：** Phase 1 **单租户**，Session 按 `user_id`（API Key 映射）区分；**不实现 org_id 级隔离**。Phase 3 采用 `org_id + 独立 DB schema`。

**理由：**
- Phase 1 范围明确为单机/团队内网
- 避免 MVP 过度设计
- 数据模型预留 `org_id` 字段（可为 null）

---

## 附加决策（架构相关）

| 项 | 决策 |
|----|------|
| 主语言 | Python 3.11+ |
| CLI 框架 | Typer |
| HTTP API | FastAPI（与 CLI 共用 Orchestrator 核心） |
| 状态持久化 | SQLite（Phase 2 迁移 PostgreSQL） |
| 向量库 | Chroma（嵌入式，本地 `.agent/index`） |
| 嵌入模型 | DeepSeek 不提供独立 embedding API；Phase 1 用 OpenAI `text-embedding-3-small` 或本地 embedding 模型（与对话 LLM 独立） |
| 目标栈（被 Agent 操作的仓库） | TypeScript/JavaScript + Python 优先 |
| Review（Phase 1） | 规则引擎：密钥检测 + Linter 结果 + 基础 diff 统计；完整 LLM Review 放 Phase 2 |

---

## 后果

- 正面：决策清晰，可立即进入架构细化与代码骨架搭建
- 负面：Phase 1 无 SSO、无完整 Review 循环——已在需求分期中明确，不构成范围蔓延
- 待办：产品/技术/安全负责人正式审批 ADR（审批前按本文实施）

---

## 审批

| 角色 | 姓名 | 意见 | 日期 |
|------|------|------|------|
| 产品负责人 | TBD | 待审批 | — |
| 技术负责人 | TBD | 待审批 | — |
| 安全负责人 | TBD | 待审批 | — |
