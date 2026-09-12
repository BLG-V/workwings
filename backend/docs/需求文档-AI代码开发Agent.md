# AI 代码开发 Agent — 需求文档

| 文档属性 | 说明 |
|---------|------|
| 项目名称 | AI 代码开发 Agent（智能编程 Copilot） |
| 方法论 | Goal Workflow + gstack + autoresearch |
| 文档编号 | SRS-AI-AGENT-001 |
| 文档版本 | v4.0 |
| 编写日期 | 2026-06-25 |
| 最后修订 | 2026-07-08 |
| 文档状态 | 评审稿 |
| 密级 | 内部公开 |
| 目标读者 | 产品经理、架构师、开发工程师、测试工程师、运维工程师 |
| 文档负责人 | 产品负责人（TBD） |
| 技术负责人 | 架构师（TBD） |

---

## 文档控制

### 修订记录

| 版本 | 日期 | 修订人 | 说明 |
|------|------|--------|------|
| v1.0 | 2026-06-25 | — | 基于项目需求初稿创建 |
| v2.0 | 2026-06-27 | — | 对标企业级标准：补充治理、合规、运维、SLA |
| v3.0 | 2026-07-08 | — | OpenSpec + Superpowers + gstack 三层架构（已废弃） |
| v4.0 | 2026-07-08 | — | 重构为 Goal Workflow（流程骨架）+ gstack（质量审查）+ autoresearch（自动化加速） |

### 关联文档

| 文档 | 说明 | 状态 |
|------|------|------|
| 架构设计文档 | 系统详细设计与组件边界 | 待更新（对齐 v4.0） |
| ADR-001-MVP技术决策 | Phase 1 技术选型 | 已编写 |
| ADR-002-方法论选型 | Goal Workflow + gstack + autoresearch | 待编写 |
| `.goal/prd/` | 产品需求文档 | 按功能生成 |
| `.goal/spec/` | 技术规格文档 | 按功能生成 |
| `.goal/issues/` | Issue 卡片（原子任务） | 按功能生成 |
| `.autoresearch/program.md` | 自主迭代目标与验证指标 | 按 Session 生成 |

---

## 1. 项目概述

### 1.1 项目背景

传统「Vibe Coding」在长对话中容易出现 **上下文腐烂（Context Rot）**：需求边界模糊、质量无门禁、实现迭代靠人工催促。本项目构建 **AI 代码开发 Agent**，采用三层协作体系，从「对话写代码」升级为 **Agentic Engineering**：

| 组件 | 定位 | 角色隐喻 | 核心职责 |
|------|------|---------|---------|
| **Goal Workflow** | 流程骨架 | 项目经理 | 定义从 PRD 到交付的标准化六步流程 |
| **gstack** | 质量审查 | 质量门禁 | 在规划、实现、交付各阶段插入专业审查 |
| **autoresearch** | 自动化加速 | 迭代引擎 | 修改→验证→保留/回滚的自主循环，加速实现与修复 |

三者关系：

```
Goal Workflow 定义「走哪几步」
gstack 定义「每步过不过得去」
autoresearch 定义「怎么快速跑到过线」
```

### 1.2 项目目标

| 目标维度 | 描述 | 可量化指标（首年） |
|---------|------|-------------------|
| 流程目标 | 100% 功能变更走 Goal Workflow 六步闭环 | Issue 卡片覆盖率 100% |
| 质量目标 | 关键节点经 gstack 审查，blocking 清零方可推进 | Review blocking 率 < 10% |
| 加速目标 | 实现阶段 autoresearch 自主迭代，减少人工催促 | 单 Issue 人工介入 ≤ 2 次 |
| 业务目标 | 标准场景端到端自动化交付 | E2E 成功率 ≥ 70% |
| 验证目标 | 所有完成项具备二元验证命令（exit 0 = 通过） | 验证命令覆盖率 100% |

### 1.3 项目范围

**范围内（In Scope）：**

- Goal Workflow 六步闭环：规划 → 设计 → 拆解 → 实现 → 审查 → 交付
- gstack 质量审查：计划评审、代码审查、QA 测试
- autoresearch 自主迭代：modify → verify → keep/discard 循环
- 多 Agent 协作（需求理解 / 编码 / 测试 / 审查）
- 代码仓库工具调用、RAG、Session 记忆、企业治理

**范围外（Out of Scope，初版）：**

- Goal Workflow 全部 15+ Skill（初版实现核心 6 步 + `/loop-it`）
- gstack 全部 23 Skill（初版实现 review / qa / plan-eng-review）
- autoresearch 全部 14 子命令（初版实现 core loop + plan + fix + debug）
- IDE 插件深度集成、生产自动部署

### 1.4 术语定义

| 术语 | 定义 |
|------|------|
| Goal Workflow | 基于 Issue 卡片的标准化研发流程（PRD → SPEC → Issues → Goal → Review → Ship） |
| Issue 卡片 | 原子工作任务，含验收标准、依赖关系、状态 |
| gstack | Garry Tan 开源的 AI 工程技能栈，本项目用于质量审查门禁 |
| autoresearch | Karpathy 式自主迭代框架：约束范围 + 二元指标 + Git 回滚 |
| program.md | autoresearch 目标配置文件：目标、指标、范围、迭代上限 |
| 二元验证 | 可执行命令，exit 0 = 通过，非 0 = 失败（如 `pytest`、`mypy`） |
| Keep/Discard | autoresearch 迭代结果判定：指标改善则保留（Git commit），否则回滚 |
| Agent | 具备特定角色与工具权限的 AI 执行单元 |
| Session | 一次完整开发任务的多轮交互上下文 |

### 1.5 假设与约束

**假设：**

- 目标仓库已有可运行的测试套件
- 每个 Issue 可定义明确的二元验证命令
- LLM API 在部署环境可达

**约束：**

- 未经 Goal Workflow 拆解为 Issue 的需求不得直接进入实现
- 未经 gstack 审查通过的变更不得进入交付
- autoresearch 迭代必须有界（max_iterations、token_budget）
- 生产 merge 需用户显式 `agent approve`（继承 ADR-001）

---

## 2. 核心工作流：Goal Workflow 六步闭环

本节定义项目 **唯一官方开发流程**。所有功能开发、Bug 修复、重构均须遵循。

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                     Goal Workflow 六步闭环                                     │
├──────────┬──────────┬──────────┬──────────┬──────────┬────────────────────┤
│ ① 规划   │ ② 设计   │ ③ 拆解   │ ④ 实现   │ ⑤ 审查   │ ⑥ 交付              │
│  /prd    │/prd-to-  │/to-issues│  /goal   │/review-it│  /ship-it          │
│          │  spec    │          │          │          │                    │
│ PRD 文档 │ 技术 SPEC│ Issue 卡 │ 可运行   │ 审查通过 │ PR + 关闭 Issue    │
│          │          │ 片       │ 代码     │ 代码     │                    │
├──────────┴──────────┴──────────┴──────────┴──────────┴────────────────────┤
│  gstack 质量审查插入点：  ↑plan-review    ↑/review+/qa        ↑ship 前 QA  │
│  autoresearch 加速区间：              ↑goal 实现循环                          │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 2.1 第一步：规划（/prd）

**目标：** 将功能想法结构化为 PRD，澄清歧义，明确验收标准。

| 需求 ID | 需求描述 | 优先级 | 验收标准 |
|--------|---------|--------|---------|
| GW-001 | 提供 `agent prd "<功能描述>"` 命令，生成结构化 PRD | P0 | 产出 `.goal/prd/<slug>.md` |
| GW-002 | PRD 须含：背景、用户故事、功能需求、非功能需求、验收标准、开放问题 | P0 | 模板字段完整率 100% |
| GW-003 | 主动澄清歧义（可配置最大轮数） | P0 | 开放问题清零或显式接受 |
| GW-004 | PRD 可关联外部 Issue 系统（GitHub Issues，Phase 2） | P2 | Webhook 双向同步 |

### 2.2 第二步：设计（/prd-to-spec）

**目标：** 将 PRD 转化为可实施的技术规格。

| 需求 ID | 需求描述 | 优先级 | 验收标准 |
|--------|---------|--------|---------|
| GW-010 | 提供 `agent spec <prd-slug>` 命令，生成技术 SPEC | P0 | 产出 `.goal/spec/<slug>.md` |
| GW-011 | SPEC 须含：架构设计、API 契约、数据模型、错误处理、安全策略 | P0 | 涉及 API 时含接口草案 |
| GW-012 | SPEC 映射到 PRD 需求 ID，确保可追溯 | P0 | 每条 PRD 需求有 SPEC 章节对应 |
| GW-013 | **gstack 门禁**：SPEC 生成后自动触发 `/plan-eng-review` | P0 | blocking 问题清零方可拆解 |

### 2.3 第三步：拆解（/to-issues）

**目标：** 将 PRD/SPEC 拆解为可独立实现的原子 Issue 卡片。

| 需求 ID | 需求描述 | 优先级 | 验收标准 |
|--------|---------|--------|---------|
| GW-020 | 提供 `agent issues <spec-slug>` 命令，生成 Issue 卡片 | P0 | 产出 `.goal/issues/<id>.md` |
| GW-021 | 每张 Issue 含：ID、标题、描述、验收标准、二元验证命令、依赖、优先级 | P0 | 验收标准可测试 |
| GW-022 | Issue 依赖关系无环，支持拓扑排序 | P0 | DAG 校验通过 |
| GW-023 | Issue 状态：`open` / `in_progress` / `done` / `blocked` | P0 | 状态机 enforced |
| GW-024 | **gstack 门禁**：拆解后可选 `/plan-ceo-review` 审查范围是否过度 | P1 | 过度设计时建议削减 |

**Issue 卡片模板：**

```markdown
# Issue GW-001: 实现邮箱验证码发送

## 元信息
- 状态: open
- 优先级: P0
- 依赖: []
- 关联: PRD-001 §3.2, SPEC-001 §2.1

## 描述
在 auth 模块实现 send_verification_code(email) 函数...

## 验收标准
- [ ] 函数接受 email 参数并发送 6 位验证码
- [ ] 验证码 5 分钟过期
- [ ] 无效 email 格式返回 400

## 验证命令
```bash
pytest tests/test_auth.py::test_send_verification_code -q
```

## 影响文件（预估）
- src/auth/verification.py
- tests/test_auth.py
```

### 2.4 第四步：实现（/goal + autoresearch）

**目标：** 选取 Issue 卡片，通过 autoresearch 自主迭代循环完成端到端实现。

| 需求 ID | 需求描述 | 优先级 | 验收标准 |
|--------|---------|--------|---------|
| GW-030 | 提供 `agent goal <issue-id>` 命令，读取 Issue 并启动实现 | P0 | 自动加载 Issue 上下文 + RAG |
| GW-031 | 实现前生成 `program.md`：目标、验证命令、允许修改范围、max_iterations | P0 | program.md schema 校验 |
| GW-032 | 集成 autoresearch 核心循环：modify → verify → keep/discard | P0 | 见 §3.3 |
| GW-033 | 验证通过（exit 0）后标记 Issue `done`，记录迭代次数与最终 commit | P0 | 状态自动同步 |
| GW-034 | 达 max_iterations 仍未通过时标记 `blocked`，生成失败报告 | P0 | 报告含每次迭代指标 |
| GW-035 | 支持 `agent loop <spec-slug>` 批量按依赖顺序实现所有 Issue | P1 | 含 Checkpoint 恢复 |

**实现阶段状态机：**

```
选取 Issue (open, 依赖已满足)
  → 生成 program.md
  → [autoresearch 循环]
      → Coding Agent 修改代码
      → 运行验证命令 (pytest 等)
      → 通过: Git commit (keep) → Issue done
      → 失败: Git reset (discard) → 下一迭代
  → 达 max_iterations → blocked
```

### 2.5 第五步：审查（/review-it + gstack）

**目标：** 对实现结果进行专业质量审查，迭代修复直至通过。

| 需求 ID | 需求描述 | 优先级 | 验收标准 |
|--------|---------|--------|---------|
| GW-040 | 提供 `agent review <issue-id>` 命令，触发 gstack 审查流水线 | P0 | 调用 /review + /qa |
| GW-041 | `/review`：代码质量、安全性、复杂度、与 Issue 一致性 | P0 | 输出 blocking/suggestion/nit |
| GW-042 | `/qa`：运行测试套件 + 浏览器/UI 测试（若适用） | P1 | 测试全绿 |
| GW-043 | blocking 问题自动触发 autoresearch `:fix` 循环修复 | P0 | 修复后重新审查 |
| GW-044 | 审查通过后标记 Issue 审查状态 `reviewed` | P0 | 未 reviewed 不可 ship |

### 2.6 第六步：交付（/ship-it）

**目标：** 提交代码、创建 PR、关闭 Issue。

| 需求 ID | 需求描述 | 优先级 | 验收标准 |
|--------|---------|--------|---------|
| GW-050 | 提供 `agent ship <issue-id>` 命令，执行交付流程 | P0 | commit message 含 Issue ID |
| GW-051 | 生成 PR 描述：变更摘要、测试结果、审查意见 | P0 | 符合 Conventional Commits |
| GW-052 | Git commit 需用户显式 `agent approve`（继承 ADR-001） | P0 | 无授权不执行 push |
| GW-053 | 关闭 Issue，归档到 `.goal/archive/` | P0 | 归档含完整 artifacts |
| GW-054 | 可选：合并 PR 描述草稿对接 GitHub API | P2 | PR 模板可配置 |

---

## 3. 三层组件需求

### 3.1 架构总览

```
┌──────────────────────────────────────────────────────────────────────┐
│                         用户交互层                                      │
│              CLI (agent *) / Web UI (Phase 2) / IDE 扩展              │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────────┐
│  Goal Workflow（流程骨架）          六步闭环 + Issue 卡片驱动            │
│  prd → spec → issues → goal → review → ship                          │
│  产出：PRD / SPEC / Issue 卡片 / 归档                                  │
└────────────────────────────┬─────────────────────────────────────────┘
                             │ 各阶段触发
┌────────────────────────────▼─────────────────────────────────────────┐
│  gstack（质量审查）                  质量门禁                            │
│  plan-eng-review │ review │ qa │ plan-ceo-review                     │
│  产出：Review Report（blocking 须清零）                                 │
└────────────────────────────┬─────────────────────────────────────────┘
                             │ goal/review 阶段嵌入
┌────────────────────────────▼─────────────────────────────────────────┐
│  autoresearch（自动化加速）          自主迭代引擎                         │
│  modify → verify → keep/discard │ plan │ fix │ debug                 │
│  产出：经验证代码 + 迭代日志 results.jsonl                             │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────────┐
│  Agent Runtime（已有）            执行层                                │
│  Orchestrator │ Requirement/Coding/Testing/Review Agent │ Tools │ RAG │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────────┐
│  基础设施                                                              │
│  Git │ Chroma │ SQLite │ LLM Adapter │ Audit                           │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.2 gstack 质量审查需求

gstack 在本项目中 **仅承担质量审查**，不作为决策层。在 Goal Workflow 关键节点插入审查门禁。

| 需求 ID | 需求描述 | 优先级 | 插入点 | 验收标准 |
|--------|---------|--------|--------|---------|
| GST-001 | `/plan-eng-review`：审查 SPEC 的技术方案、边界、测试策略 | P0 | ②设计后 | 输出 eng-review.md |
| GST-002 | `/plan-ceo-review`：审查 PRD 的产品价值与范围（可选） | P1 | ①规划后 | 输出 ceo-review.md |
| GST-003 | `/review`：代码质量审查，含复杂度、安全、一致性 | P0 | ⑤审查 | blocking/suggestion/nit 分级 |
| GST-004 | `/qa`：运行测试 + 回归验证 | P0 | ⑤审查 | 测试全绿 |
| GST-005 | `/autoplan`：串联 CEO → 设计 → 工程评审（一键审查） | P1 | ①②之间 | 仅暴露 taste 决策给用户 |
| GST-006 | 审查产出存入 `.agent/reviews/<issue-id>/` | P0 | 全局 | 可追溯、可回放 |
| GST-007 | blocking 项自动触发 autoresearch `:fix` 修复循环 | P0 | ⑤审查 | 修复后自动 re-review |
| GST-008 | 密钥/PII 检测（继承 RA-004） | P0 | ⑤审查 | 标准模式库检出率 100% |

**gstack 审查报告模板：**

```yaml
review_id: REV-2026-001
issue_id: GW-001
reviewer: gstack/review
status: PASS  # PASS | BLOCKED
findings:
  - severity: blocking
    file: src/auth/verification.py
    line: 42
    message: "验证码未设置过期时间"
  - severity: suggestion
    file: src/auth/verification.py
    line: 15
    message: "建议使用 secrets 模块生成验证码"
blocking_count: 0
```

### 3.3 autoresearch 自动化加速需求

autoresearch 在 **实现（/goal）** 和 **修复（审查 blocking）** 阶段提供自主迭代加速。

| 需求 ID | 需求描述 | 优先级 | 验收标准 |
|--------|---------|--------|---------|
| AR-001 | 核心循环 `agent research <issue-id>`：modify → verify → keep/discard | P0 | 见下方循环定义 |
| AR-002 | `program.md` 配置：goal、metric_command、scope_files、max_iterations、token_budget | P0 | schema 校验 |
| AR-003 | 验证通过：Git commit 保留变更，记录到 `results.jsonl` | P0 | commit message 含 iteration 编号 |
| AR-004 | 验证失败：Git reset 回滚，进入下一迭代 | P0 | 工作区恢复干净 |
| AR-005 | `agent research:plan`：将 Issue 转化为 program.md | P0 | 自动生成验证命令 |
| AR-006 | `agent research:fix`：针对 blocking 审查意见逐项修复 | P0 | 每项 blocking 对应一次 fix 循环 |
| AR-007 | `agent research:debug`：测试失败时假设-验证式调试 | P1 | 默认 15 轮 |
| AR-008 | 迭代日志 `results.jsonl`：每轮含 metric、pass/fail、diff 摘要、耗时 | P0 | 可导出分析 |
| AR-009 | 安全护栏：max_iterations 默认 25，token_budget 可配置 | P0 | 超限强制停止 |
| AR-010 | `agent research:regression`：候选变更 vs baseline 稳定性对比 | P1 | 输出 STABLE/UNSTABLE |

**autoresearch 核心循环：**

```
LOOP (i = 1 .. max_iterations):
  1. 读取 program.md + 当前 Git 状态 + results.jsonl 历史
  2. Coding Agent 提出修改（scope_files 范围内）
  3. 运行 metric_command（如 pytest）
  4. 若 exit 0:
       → git commit -m "autoresearch: iter {i} PASS"
       → 写入 results.jsonl {iteration: i, status: "keep", metric: ...}
       → BREAK（目标达成）
  5. 若 exit != 0:
       → git reset --hard HEAD
       → 写入 results.jsonl {iteration: i, status: "discard", error: ...}
       → CONTINUE
  6. 若 i == max_iterations:
       → 标记 Issue blocked
       → 生成失败报告
```

**program.md 模板：**

```markdown
# Autoresearch Program

## Goal
实现 Issue GW-001: 邮箱验证码发送功能

## Metric（二元验证）
```bash
pytest tests/test_auth.py::test_send_verification_code -q
```
通过条件: exit code == 0

## Scope（允许修改的文件）
- src/auth/verification.py
- tests/test_auth.py

## Constraints
- max_iterations: 25
- token_budget: 500000
- 禁止修改: src/auth/login.py（已有功能）

## Issue
- ID: GW-001
- 验收标准: 见 .goal/issues/GW-001.md
```

### 3.4 层间契约

| 从 → 到 | 传递物 | 门禁条件 |
|---------|--------|---------|
| 用户 → Goal Workflow | 功能描述 | — |
| Goal Workflow → gstack | PRD / SPEC / diff | 各阶段审查节点 |
| Goal Workflow → autoresearch | Issue 卡片 | Issue 状态 = open，依赖满足 |
| autoresearch → Goal Workflow | 代码 + results.jsonl | metric_command exit 0 |
| gstack → autoresearch | blocking findings | 审查未通过 |
| Goal Workflow → 用户 | PR + 归档 | reviewed + approve |

### 3.5 目录结构规范

```
<workspace>/
├── .goal/
│   ├── prd/                 # 产品需求文档
│   │   └── email-login.md
│   ├── spec/                # 技术规格
│   │   └── email-login.md
│   ├── issues/              # Issue 卡片
│   │   ├── GW-001.md
│   │   └── GW-002.md
│   └── archive/             # 已交付归档
│       └── 2026-07-08-email-login/
├── .autoresearch/
│   ├── program.md           # 当前活跃迭代配置
│   ├── results.jsonl        # 迭代日志
│   └── state.json           # 当前最优状态
├── .agent/
│   ├── reviews/             # gstack 审查报告
│   │   └── GW-001/
│   │       ├── eng-review.md
│   │       ├── review.md
│   │       └── qa.md
│   ├── sessions/            # Session 持久化
│   ├── index/               # RAG 索引
│   └── audit/               # 审计日志
└── src/ ...                 # 项目代码
```

---

## 4. 功能需求（Agent Runtime 详细）

> 继承 v2.0 执行层能力，重新定位为三层架构的底层引擎。

### 4.1 多 Agent 协作

| 需求 ID | 需求描述 | 优先级 | 验收标准 |
|--------|---------|--------|---------|
| RUA-001 | 从 `.goal/` 目录加载 PRD/SPEC/Issue 作为首要上下文 | P0 | 有 Issue 时不重复询问 |
| CA-001 | 按 Issue 描述和 program.md scope 修改代码 | P0 | 不超出 scope_files |
| TA-001 | 执行 Issue 定义的 metric_command 作为验证 | P0 | exit code 判定 pass/fail |
| RA-001 | 实现 gstack /review 的审查逻辑（Phase 1 规则引擎，Phase 2 LLM） | P0 | blocking 分级 |
| MAC-001 | 工作流状态：`PRD → SPEC → ISSUES → GOAL → REVIEW → SHIP → DONE` | P0 | 状态机 enforced |
| MAC-002 | autoresearch 子状态：`MODIFY → VERIFY → KEEP/DISCARD` | P0 | Git 状态一致 |
| MAC-003 | 用户可暂停、注入指令、终止 Session | P0 | 安全停止 |
| MAC-004 | 全量审计日志，支持回放 | P1 | export 可用 |

### 4.2 工具调用

| 需求 ID | 需求描述 | 优先级 | 验收标准 |
|--------|---------|--------|---------|
| TC-001 | read/write/edit_file、list_dir、grep | P0 | 遵循 .gitignore |
| TC-002 | run_terminal_cmd：超时、沙箱 | P0 | 默认 120s |
| TC-003 | run_tests：pytest 适配 | P0 | 作为 metric_command 执行 |
| TC-004 | Git 操作：status、diff、commit、reset | P0 | autoresearch keep/discard |
| TC-005 | 危险命令与敏感路径拦截 | P0 | E2E-05 通过 |
| TC-006 | 按 Agent 角色分配工具白名单 | P0 | Review Agent 无 write |

### 4.3 代码库 RAG

| 需求 ID | 需求描述 | 优先级 | 验收标准 |
|--------|---------|--------|---------|
| RAG-001 | 索引代码 + `.goal/` 文档 + README | P0 | 文档命中率 ≥ 85% |
| RAG-002 | 混合检索：向量 + BM25 | P0 | 优于单向量 |
| RAG-003 | Token 预算管理 | P0 | 不超上下文限制 |

### 4.4 上下文记忆

| 需求 ID | 需求描述 | 优先级 | 验收标准 |
|--------|---------|--------|---------|
| CM-001 | Session 管理：创建、恢复、列表、归档 | P0 | UUID 标识 |
| CM-002 | 保存对话、工具调用、迭代日志 | P0 | 无丢失 |
| CM-003 | Checkpoint：autoresearch 中断可恢复 | P1 | E2E-07 通过 |
| CM-004 | 多轮迭代：continue 追加 Issue 或修改 | P0 | E2E-03 通过 |

### 4.5 企业治理

| 需求 ID | 需求描述 | 优先级 | 验收标准 |
|--------|---------|--------|---------|
| ENT-001 | API Key 认证 | P0 | Key 可轮换 |
| ENT-002 | RBAC：Admin、Developer、Viewer | P0 | 权限 enforced |
| ENT-003 | 审计日志保留 ≥ 90 天 | P0 | 可导出 |
| ENT-004 | 路径/命令黑名单 | P0 | E2E-05 通过 |

---

## 5. 用户与场景

### 5.1 目标用户

| 用户角色 | 核心诉求 | 主要使用组件 |
|---------|---------|-------------|
| 产品经理 | 结构化需求、Issue 追踪 | Goal Workflow `/prd` |
| 架构师 | 技术方案、审查门禁 | Goal Workflow `/spec` + gstack |
| 开发工程师 | 高效实现、少催促 | `/goal` + autoresearch |
| 技术负责人 | 质量可控、可追溯 | gstack `/review` + 审计 |

### 5.2 典型场景

#### 场景 A：新功能开发（完整六步）

```bash
# ① 规划
agent prd "为用户模块增加邮箱验证码登录"

# ② 设计（自动触发 gstack plan-eng-review）
agent spec email-login

# ③ 拆解
agent issues email-login

# ④ 实现（autoresearch 自主迭代）
agent goal GW-001

# ⑤ 审查（gstack review + qa）
agent review GW-001

# ⑥ 交付
agent approve -s <session_id>
agent ship GW-001
```

#### 场景 B：Bug 修复（快速通道）

```bash
# 直接创建 Issue（跳过 prd/spec）
agent issues --quick "修复 login.py 中 JWT 过期未刷新"
agent goal GW-042          # autoresearch 修复循环
agent review GW-042
agent ship GW-042
```

#### 场景 C：批量实现（/loop-it）

```bash
agent loop email-login     # 按依赖顺序自动 goal → review
agent ship --all           # 批量交付
```

#### 场景 D：审查 blocking 自动修复

```bash
agent review GW-001        # gstack 发现 2 个 blocking
# 自动触发 autoresearch:fix
agent research:fix GW-001  # 逐项修复 blocking
agent review GW-001        # 重新审查 → PASS
```

---

## 6. 非功能需求

| 需求 ID | 描述 | 指标 |
|--------|------|------|
| NFR-P01 | 单次 Agent 回合 | P95 < 30s |
| NFR-P02 | RAG 检索 | P95 < 2s |
| NFR-P03 | autoresearch 单轮迭代（含测试） | P95 < 120s |
| NFR-R01 | LLM 失败重试 | 指数退避，最多 3 次 |
| NFR-R02 | autoresearch 中断可恢复 | Checkpoint |
| NFR-S01 | 密钥不出现在日志/Prompt | enforced |
| NFR-S02 | autoresearch scope 外文件不可修改 | 策略拦截 |
| NFR-E01 | LLM 提供商可插拔 | Adapter 层 |
| NFR-E02 | Goal Workflow 步骤可配置跳过 | YAML 配置 |

---

## 7. 接口与交互

### 7.1 CLI 命令总览

| 命令 | 组件 | 说明 |
|------|------|------|
| `agent prd "<描述>"` | Goal Workflow | ① 生成 PRD |
| `agent spec <slug>` | Goal Workflow | ② 生成 SPEC + gstack eng-review |
| `agent issues <slug>` | Goal Workflow | ③ 拆解 Issue 卡片 |
| `agent issues --quick "<描述>"` | Goal Workflow | 快速创建单个 Issue |
| `agent goal <issue-id>` | Goal Workflow + autoresearch | ④ 实现（含迭代循环） |
| `agent loop <slug>` | Goal Workflow | 批量实现所有 Issue |
| `agent review <issue-id>` | Goal Workflow + gstack | ⑤ 质量审查 |
| `agent ship <issue-id>` | Goal Workflow | ⑥ 交付 |
| `agent research <issue-id>` | autoresearch | 自主迭代循环 |
| `agent research:plan <issue-id>` | autoresearch | 生成 program.md |
| `agent research:fix <issue-id>` | autoresearch | 修复 blocking |
| `agent research:debug <issue-id>` | autoresearch | 假设式调试 |
| `agent status -s <id>` | 通用 | 查看进度 |
| `agent approve -s <id>` | 通用 | 确认提交 |
| `agent export -s <id>` | 通用 | 导出回放包 |
| `agent index` | RAG | 建立索引 |

### 7.2 配置项

```yaml
# agent.config.yaml
workspace: "."

goal_workflow:
  base_path: ".goal"
  steps:
    prd: true
    spec: true
    issues: true
    review: true
    ship: true
  quick_track_max_files: 3   # 快速通道最大影响文件数

gstack:
  enabled: true
  reviewers:
    - plan-eng-review    # SPEC 后必审
    - review             # 实现后必审
    - qa                 # 交付前必审
  auto_fix_blocking: true  # blocking 自动触发 research:fix

autoresearch:
  max_iterations: 25
  token_budget: 500000
  results_path: ".autoresearch/results.jsonl"
  auto_commit_on_keep: true

llm:
  provider: "deepseek"
  model: "deepseek-v4-pro"

agents:
  coding:
    max_retries: 3

rag:
  index_path: ".agent/index"
  include_paths: [".goal", "docs", "README.md"]

security:
  path_denylist: ["**/secrets/**", ".env"]
```

---

## 8. 数据模型

### 8.1 Issue 卡片

```
Issue {
  id: string                    // GW-001
  title: string
  description: markdown
  status: enum(open, in_progress, done, blocked, reviewed)
  priority: enum(P0, P1, P2)
  depends_on: string[]
  acceptance_criteria: string[]
  verify_command: string        // 二元验证 shell 命令
  scope_files: string[]
  prd_ref: string
  spec_ref: string
}
```

### 8.2 Autoresearch 迭代记录

```
ResearchIteration {
  iteration: int
  issue_id: string
  status: enum(keep, discard)
  metric_command: string
  metric_result: int            // exit code
  duration_ms: int
  diff_summary: string
  commit_sha: string            // keep 时有值
  timestamp: datetime
}
```

### 8.3 gstack 审查报告

```
ReviewReport {
  id: string
  issue_id: string
  reviewer: string              // plan-eng-review | review | qa
  status: enum(PASS, BLOCKED)
  findings: Finding[]
  created_at: datetime
}

Finding {
  severity: enum(blocking, suggestion, nit)
  file: string
  line: int
  message: string
}
```

### 8.4 Session（继承 v2.0，扩展字段）

```
Session {
  id: string
  workflow_phase: enum(PRD, SPEC, ISSUES, GOAL, REVIEW, SHIP, DONE)
  research_phase: enum(MODIFY, VERIFY, KEEP, DISCARD)
  current_issue_id: string
  research_iteration: int
  status: enum(INIT, RUNNING, WAITING_USER, DONE, FAILED, CANCELLED)
  repo_path: string
}
```

---

## 9. 验收标准

### 9.1 方法论验收

| 验收项 | 通过标准 |
|--------|---------|
| 六步闭环 | 标准 Demo 走完 prd → spec → issues → goal → review → ship |
| gstack 门禁 | 未通过 review 的 Issue 无法 ship |
| autoresearch 循环 | goal 阶段自动迭代直至 verify 通过或达上限 |
| 二元验证 | 每个 Issue 有可执行 verify_command |
| Git 回滚 | discard 后工作区与最近 keep commit 一致 |
| 快速通道 | --quick 模式可跳过 prd/spec，但不跳过 review |

### 9.2 端到端验收用例

| 用例 ID | 描述 | 通过标准 | 优先级 |
|--------|------|---------|--------|
| E2E-01 | 完整六步：新功能开发 | 全流程通过；Issue 关闭 | P0 |
| E2E-02 | autoresearch 修复测试失败 | 先失败后通过；results.jsonl 有记录 | P0 |
| E2E-03 | 多轮迭代 continue | 增量 Issue 正确追加 | P0 |
| E2E-04 | gstack blocking 阻断 ship | review BLOCKED 时 ship 拒绝 | P0 |
| E2E-05 | 越权路径访问 | secrets 被拦截 | P0 |
| E2E-06 | 快速通道 Bug 修复 | --quick 流程通过 | P0 |
| E2E-07 | autoresearch 中断恢复 | 从 iteration N 继续 | P1 |
| E8E-08 | 批量 loop 实现 | 多 Issue 按依赖顺序完成 | P1 |

### 9.3 需求追踪矩阵

| 六步流程 | Goal Workflow | gstack | autoresearch | Agent Runtime | E2E |
|---------|--------------|--------|-------------|--------------|-----|
| ① prd | GW-001~004 | GST-002 | — | RUA-001 | E2E-01 |
| ② spec | GW-010~013 | GST-001 | — | RUA-001 | E2E-01 |
| ③ issues | GW-020~024 | GST-005 | AR-005 | MAC-001 | E2E-01 |
| ④ goal | GW-030~035 | — | AR-001~010 | CA-*, TA-* | E2E-02 |
| ⑤ review | GW-040~044 | GST-003~008 | AR-006 | RA-* | E2E-04 |
| ⑥ ship | GW-050~054 | GST-004 | — | ENT-* | E2E-01 |

---

## 10. 实施计划

### Phase 1：三层骨架 + 执行层 MVP（6–8 周）

**Goal Workflow：**
- `.goal/` 目录结构与 Issue 卡片模板
- `agent prd` / `agent spec` / `agent issues` / `agent goal` CLI
- Issue 状态机与依赖排序

**gstack：**
- 规则引擎实现 plan-eng-review、review（密钥检测 + Linter）
- 审查报告写入 `.agent/reviews/`
- blocking 阻断逻辑

**autoresearch：**
- `program.md` 生成与 schema 校验
- 核心循环：modify → verify → keep/discard
- `results.jsonl` 迭代日志
- Git commit/reset 集成

**Agent Runtime（复用已有）：**
- Orchestrator 六步状态机
- Coding / Testing Agent + RAG + Tools + Session

**里程碑：** E2E-01、E2E-02、E2E-04、E2E-05、E2E-06

### Phase 2：质量增强（4 周）

- gstack LLM Review（完整 /review + /qa）
- autoresearch `:fix` / `:debug` 子命令
- `agent loop` 批量实现 + Checkpoint
- `agent review` / `agent ship` 完整流程
- Web UI 展示六步进度

**里程碑：** E2E-03、E2E-07、E2E-08

### Phase 3：扩展（4 周）

- Goal Workflow 扩展 Skill（`/refactor`、`/code-to-spec`）
- gstack `/autoplan`、安全审查
- autoresearch `:security`、`:regression`
- GitHub Issues 集成、Helm 部署

---

## 11. 风险与依赖

| 风险 ID | 风险 | 缓解措施 |
|--------|------|---------|
| R-001 | 六步流程过重，小改动效率低 | `--quick` 快速通道；可配置跳过步骤 |
| R-002 | autoresearch 无限循环消耗 token | max_iterations + token_budget 硬限制 |
| R-003 | gstack 审查流于形式 | 结构化 finding 模板；blocking 强制修复 |
| R-004 | verify_command 难以定义 | `research:plan` 自动生成；人工可编辑 |
| R-005 | LLM 幻觉导致错误修改 | scope 限制 + review 门禁 + Git 回滚 |
| R-006 | 三层集成复杂度高 | Phase 1 先串联主路径，扩展 Skill 后置 |

### 外部依赖

| 依赖 | 用途 | 备选 |
|------|------|------|
| smallnest/goal-workflow | 流程 Skill 参考实现 | 自研 CLI 封装 |
| garrytan/gstack | 审查 Skill 参考实现 | 自研规则 + LLM Review |
| karpathy/autoresearch | 迭代模式参考 | uditgoenka/autoresearch Skill |
| DeepSeek V4 API | LLM 主模型 | OpenAI / 本地 Ollama |

---

## 12. 附录

### 12.1 方法论参考

- [Goal Workflow](https://github.com/smallnest/goal-workflow) — 六步闭环研发工作流
- [gstack](https://github.com/garrytan/gstack) — Think → Plan → Build → Review → Test → Ship
- [autoresearch (Karpathy)](https://github.com/karpathy/autoresearch) — Modify → Verify → Keep/Discard
- [autoresearch (Claude Skill)](https://github.com/uditgoenka/autoresearch) — 通用域自主迭代

### 12.2 与 v3.0 的关系

v4.0 废弃 v3.0 的 OpenSpec + Superpowers + gstack(决策层) 方案，改为：

| v3.0 | v4.0 | 说明 |
|------|------|------|
| OpenSpec（上下文层） | Goal Workflow（流程骨架） | PRD/SPEC/Issue 替代 spec.md/proposal.md |
| Superpowers（执行层） | autoresearch（自动化加速） | TDD 循环融入 modify→verify 迭代 |
| gstack（决策层） | gstack（质量审查） | 从「决定做什么」改为「审查过不过」 |
| `/opsx:propose` | `agent prd` + `agent issues` | 需求拆解方式变更 |
| `agent dev` | `agent goal` + `agent research` | 实现驱动方式变更 |

v2.0 的 Agent Runtime、Tool、RAG、Memory、企业治理需求继续有效。

### 12.3 开放问题

| ID | 问题 | 建议 | 决策人 |
|----|------|------|--------|
| OQ-001 | 是否引入 goal-workflow 官方 Skill 还是自研 CLI | Phase 1 自研 CLI，参考其模板 | 架构师 |
| OQ-002 | gstack Skill 安装方式 | `.cursor/skills/` 引入 + Python 封装调用 | 架构师 |
| OQ-003 | autoresearch 默认 max_iterations | 25（可 per-Issue 覆盖） | 产品 |
| OQ-004 | 已有仓库如何初始化 .goal/ | 提供 `agent goal init` 从代码反向生成 | 架构师 |

---

*本文档为 AI 代码开发 Agent 项目的正式需求规格说明（SRS），版本 v4.0。基于 Goal Workflow + gstack + autoresearch 方法论编写。*
