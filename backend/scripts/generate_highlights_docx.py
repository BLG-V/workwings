"""生成《AI 代码开发 Agent — 技术亮点说明》Word 文档。"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "项目技术亮点说明.docx"


def set_run_font(run, name: str = "微软雅黑", size: int = 11, bold: bool = False) -> None:
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    run.font.bold = bold


def add_title(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    set_run_font(run, size=22, bold=True)
    run.font.color.rgb = RGBColor(0x1A, 0x36, 0x5D)


def add_subtitle(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    set_run_font(run, size=12)
    run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)


def add_heading(doc: Document, text: str, level: int = 1) -> None:
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        set_run_font(run, size=16 if level == 1 else 13, bold=True)


def add_para(doc: Document, text: str, bold: bool = False) -> None:
    p = doc.add_paragraph()
    run = p.add_run(text)
    set_run_font(run, bold=bold)


def add_bullets(doc: Document, items: list[str]) -> None:
    for item in items:
        p = doc.add_paragraph(style="List Bullet")
        run = p.add_run(item)
        set_run_font(run)


def add_code_block(doc: Document, lines: list[str]) -> None:
    for line in lines:
        p = doc.add_paragraph()
        run = p.add_run(line)
        run.font.name = "Consolas"
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "Consolas")
        run.font.size = Pt(10)


def add_table(doc: Document, headers: list[str], rows: list[list[str]]) -> None:
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Table Grid"
    hdr_cells = table.rows[0].cells
    for i, header in enumerate(headers):
        hdr_cells[i].text = header
        for p in hdr_cells[i].paragraphs:
            for run in p.runs:
                set_run_font(run, bold=True)
    for r_idx, row in enumerate(rows):
        row_cells = table.rows[r_idx + 1].cells
        for c_idx, cell_text in enumerate(row):
            row_cells[c_idx].text = cell_text
            for p in row_cells[c_idx].paragraphs:
                for run in p.runs:
                    set_run_font(run)


def build_document() -> Document:
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.5)
    section.left_margin = Cm(2.8)
    section.right_margin = Cm(2.8)

    # ── 封面信息 ──
    add_title(doc, "AI 代码开发 Agent")
    add_subtitle(doc, "项目技术亮点说明")
    add_subtitle(doc, "智能编程 Copilot · Goal Workflow + gstack + autoresearch")
    doc.add_paragraph()

    add_table(
        doc,
        ["文档属性", "说明"],
        [
            ["项目名称", "AI 代码开发 Agent（智能编程 Copilot）"],
            ["文档版本", "v2.0"],
            ["编写日期", "2026-07-09"],
            ["适用场景", "答辩演示、技术面试、项目汇报、README 补充"],
            ["关联文档", "需求文档 v4.0 · 架构设计 · ADR-001 · ADR-002"],
        ],
    )
    doc.add_paragraph()

    # ── 摘要 ──
    add_heading(doc, "摘要")
    add_para(
        doc,
        "本项目构建面向真实代码仓库的多 Agent 智能编程 Copilot，解决传统 AI 辅助编程中的"
        "「上下文腐烂（Context Rot）」问题——需求边界模糊、质量无门禁、实现迭代靠人工催促。"
        "核心创新在于将「对话写代码」升级为 Agentic Engineering："
        "用 Goal Workflow 定义标准化研发流程，用 gstack 做质量门禁，"
        "用 autoresearch 做自主迭代加速，底层以多 Agent 编排引擎 + RAG + 工具调用支撑，"
        "实现从 PRD 到 PR 交付的端到端闭环。",
    )
    doc.add_paragraph()

    # ── 一、核心问题与解决方案 ──
    add_heading(doc, "一、核心问题与解决方案")
    add_para(doc, "1.1 行业痛点", bold=True)
    add_bullets(
        doc,
        [
            "长对话中需求边界逐渐模糊，Agent 容易「跑偏」或重复劳动。",
            "生成代码缺乏质量门禁，测试、审查、安全检测常被跳过。",
            "迭代修复依赖人工催促，无法自主收敛到可交付状态。",
            "企业场景对数据安全、操作审计、人工审批有刚性要求。",
        ],
    )
    add_para(doc, "1.2 本项目方案", bold=True)
    add_para(
        doc,
        "采用 Goal Workflow（流程骨架）+ gstack（质量审查）+ autoresearch（自动化加速）"
        "三层协作体系，职责边界清晰、可独立演进：",
    )
    add_table(
        doc,
        ["组件", "角色隐喻", "核心职责"],
        [
            ["Goal Workflow", "项目经理", "PRD → SPEC → Issue → 实现 → 审查 → 交付，六步闭环"],
            ["gstack", "质量门禁", "规划评审、代码审查、QA 测试，blocking 清零方可推进"],
            ["autoresearch", "迭代引擎", "modify → verify → keep/discard 自主循环"],
        ],
    )
    add_para(
        doc,
        "三者关系：Goal Workflow 定义「走哪几步」，gstack 定义「每步过不过得去」，"
        "autoresearch 定义「怎么快速跑到过线」。",
    )

    # ── 二、技术亮点详解 ──
    add_heading(doc, "二、技术亮点详解")

    # 亮点 1
    add_heading(doc, "亮点 1：三层协作方法论 —— 不是「又一个 ChatGPT 写代码」", level=2)
    add_para(doc, "问题：市面 Copilot 多为单轮对话或简单 Agent，缺少工程化流程。")
    add_para(doc, "方案：Goal Workflow 六步闭环", bold=True)
    add_code_block(
        doc,
        [
            "① 规划 (/prd)      → 结构化 PRD，澄清歧义",
            "② 设计 (/spec)     → 技术 SPEC + gstack 工程评审",
            "③ 拆解 (/issues)   → 原子 Issue 卡片 + DAG 依赖校验",
            "④ 实现 (/goal)     → autoresearch 自主迭代循环",
            "⑤ 审查 (/review)   → gstack 代码审查 + QA 测试",
            "⑥ 交付 (/ship)     → PR 生成 + Issue 归档",
        ],
    )
    add_para(doc, "差异化价值：", bold=True)
    add_bullets(
        doc,
        [
            "流程、质量、加速三层解耦，每层可独立升级，避免单体 Agent 黑盒。",
            "借鉴 Karpathy autoresearch 的 ratchet 机制：验证通过 Git commit 保留，失败 reset 回滚。",
            "支持 --quick 快速通道，小 Bug 修复可跳过 prd/spec，避免流程过重。",
            "方法论经 ADR-002 正式选型，从 v3.0（OpenSpec + Superpowers）演进至 v4.0，有完整决策记录。",
        ],
    )

    # 亮点 2
    add_heading(doc, "亮点 2：Issue 卡片 + 二元验证 —— 让 AI 迭代可机械判定", level=2)
    add_para(
        doc,
        "每个原子任务（Issue 卡片）绑定可执行的验证命令（如 pytest），"
        "exit 0 = 通过，非 0 = 失败，使 autoresearch 循环有客观终止条件。",
    )
    add_para(doc, "Issue 卡片核心字段：", bold=True)
    add_bullets(
        doc,
        [
            "ID、标题、描述、验收标准（可测试 checklist）",
            "验证命令（metric_command）：二元判定，不依赖 LLM 自评",
            "依赖关系：DAG 拓扑排序，支持批量按序实现",
            "状态机：open / in_progress / done / blocked，enforced 流转",
            "关联追溯：PRD 需求 ID → SPEC 章节 → Issue → commit → Review 报告",
        ],
    )
    add_para(doc, "量化目标：", bold=True)
    add_table(
        doc,
        ["指标", "目标值"],
        [
            ["Issue 卡片覆盖率", "100%"],
            ["验证命令覆盖率", "100%"],
            ["单 Issue 人工介入次数", "≤ 2 次"],
            ["E2E 端到端成功率", "≥ 70%"],
        ],
    )

    # 亮点 3
    add_heading(doc, "亮点 3：多 Agent 编排 + 显式状态机", level=2)
    add_para(doc, "架构分层：", bold=True)
    add_code_block(
        doc,
        [
            "Orchestrator（状态机驱动）",
            "  ├── Requirement Agent  → 需求理解 + RAG 检索",
            "  ├── Coding Agent       → 读写文件、编辑代码",
            "  ├── Testing Agent      → 执行测试、解析结果",
            "  └── Review Agent       → 规则引擎 + LLM 审查",
            "",
            "Tool Layer（统一工具层）",
            "  ├── file_tools / terminal_tools / test_tools / lint_tools",
            "  └── 返回 {success, data, error, duration_ms}",
        ],
    )
    add_para(doc, "关键设计：", bold=True)
    add_bullets(
        doc,
        [
            "Agent 不直接访问 OS，一切通过 Tool Layer，分层隔离、安全可控。",
            "Session 状态机：INIT → RUNNING → WAITING_USER → DONE / FAILED / CANCELLED。",
            "工作流阶段：REQUIREMENT → DESIGN → CODING → TESTING → REVIEW → SUBMIT。",
            "测试失败自动回退 CODING 重试；Review blocking 触发 autoresearch fix 循环。",
            "关键节点设人机检查点：设计确认、最终提交需 agent approve。",
        ],
    )

    # 亮点 4
    add_heading(doc, "亮点 4：混合 RAG —— 让 Agent 真正「读懂」代码库", level=2)
    add_bullets(
        doc,
        [
            "Chroma 向量检索 + BM25 关键词检索混合排序，兼顾语义与精确符号召回。",
            "AST 感知分块：按函数/类边界切分，避免粗暴按行数截断。",
            "本地轻量 Embedding，无需额外 API Key 也可建索引。",
            "Requirement / Coding 阶段自动注入检索片段，降低「改漏文件」风险。",
            "支持 agent index 对任意目标仓库建索引，面向真实项目而非玩具代码。",
        ],
    )
    add_para(doc, "使用示例：", bold=True)
    add_code_block(
        doc,
        [
            "agent -w examples/sample-repo index",
            'agent -w examples/sample-repo run "为用户模块增加邮箱验证码登录"',
        ],
    )

    # 亮点 5
    add_heading(doc, "亮点 5：autoresearch 自主迭代引擎", level=2)
    add_para(doc, "核心循环（modify → verify → keep/discard）：", bold=True)
    add_code_block(
        doc,
        [
            "LOOP (i = 1 .. max_iterations):",
            "  1. 读取 program.md + Git 状态 + results.jsonl 历史",
            "  2. Coding Agent 在 scope_files 范围内修改代码",
            "  3. 运行 metric_command（如 pytest）",
            "  4. exit 0 → git commit 保留（keep）→ 目标达成",
            "  5. exit != 0 → git reset 回滚（discard）→ 下一迭代",
            "  6. 达 max_iterations → Issue 标记 blocked，生成失败报告",
        ],
    )
    add_para(doc, "四重安全护栏：", bold=True)
    add_table(
        doc,
        ["护栏", "说明"],
        [
            ["max_iterations", "默认 25 轮，超限强制停止"],
            ["token_budget", "可配置 Token 预算，超限终止"],
            ["scope_files", "限制可修改文件范围，防止 Agent 改乱无关代码"],
            ["Git reset", "每轮失败立即回滚，工作区始终干净"],
        ],
    )
    add_para(
        doc,
        "每轮结果写入 results.jsonl，包含 metric、pass/fail、diff 摘要、耗时，"
        "全程可追溯、可回放、可分析。",
    )

    # 亮点 6
    add_heading(doc, "亮点 6：gstack 质量门禁", level=2)
    add_bullets(
        doc,
        [
            "/plan-eng-review：SPEC 生成后审查技术方案、边界、测试策略。",
            "/review：代码质量审查，含复杂度、安全、与 Issue 一致性，blocking/suggestion/nit 分级。",
            "/qa：运行测试套件 + 回归验证，测试全绿方可推进。",
            "blocking 项自动触发 autoresearch :fix 修复循环，修复后自动 re-review。",
            "审查产出存入 .agent/reviews/<issue-id>/，可追溯、可回放。",
            "密钥/PII 检测：标准模式库检出率 100%。",
        ],
    )

    # 亮点 7
    add_heading(doc, "亮点 7：企业级安全与合规设计", level=2)
    add_table(
        doc,
        ["安全策略", "实现方式"],
        [
            ["禁止自动 merge/push", "Agent 只生成 diff 和建议，Git 操作需 agent approve（ADR-001）"],
            ["本地/私有化部署", "Session、RAG 索引、审计日志存 .agent/ 目录，不上传 SaaS"],
            ["Policy Engine", "路径黑名单、命令黑名单、Agent 工具白名单，默认拒绝"],
            ["审计日志", "append-only JSONL，全链路记录 Agent 调用与决策"],
            ["密钥检测", "Review 阶段 100% 检出标准模式库中的密钥/PII"],
            ["Session 回滚", "cancel 可回滚变更，diff 可查看，避免半写入损坏"],
        ],
    )

    # 亮点 8
    add_heading(doc, "亮点 8：LLM Adapter 抽象 —— 厂商无关、可 Failover", level=2)
    add_bullets(
        doc,
        [
            "统一 LLMAdapter 接口（chat + function calling），核心逻辑与 LLM 解耦。",
            "支持 Anthropic 兼容 / OpenAI 兼容双端点，不绑定单一厂商 API 形态。",
            "默认 DeepSeek V4（1M 上下文，适合代码库 RAG + 多轮 Session）。",
            "备选 Failover：OpenAI GPT-4o 或本地 Ollama。",
            "未配置 API Key 时自动降级为启发式分析 + Mock LLM，测试不依赖网络。",
        ],
    )

    # 亮点 9
    add_heading(doc, "亮点 9：完整可追溯的研发 Artifacts", level=2)
    add_code_block(
        doc,
        [
            "<workspace>/",
            "├── .goal/prd/           # 产品需求文档",
            "├── .goal/spec/          # 技术规格",
            "├── .goal/issues/        # 原子 Issue 卡片",
            "├── .goal/archive/       # 已交付归档",
            "├── .autoresearch/       # program.md + results.jsonl",
            "├── .agent/reviews/      # gstack 审查报告",
            "├── .agent/sessions/     # Session 持久化（SQLite）",
            "├── .agent/index/        # RAG 向量索引（Chroma）",
            "└── .agent/audit/        # 审计日志（JSONL）",
        ],
    )
    add_para(
        doc,
        "PRD 需求 ID → SPEC 章节 → Issue 卡片 → 代码 commit → Review 报告，"
        "全链路可追溯，支持 Session 导出回放（agent export）。",
    )

    # ── 三、技术栈与架构 ──
    add_heading(doc, "三、技术栈与架构")
    add_table(
        doc,
        ["层次", "技术选型"],
        [
            ["主语言", "Python 3.11+"],
            ["CLI 框架", "Typer + Rich"],
            ["HTTP API", "FastAPI（与 CLI 共用 Orchestrator 核心）"],
            ["状态持久化", "SQLite（Phase 2 迁移 PostgreSQL）"],
            ["向量库", "Chroma（嵌入式，本地 .agent/index）"],
            ["LLM", "DeepSeek V4 Pro / Flash，Adapter 抽象层"],
            ["嵌入模型", "本地轻量模型 / OpenAI text-embedding-3-small"],
            ["目标栈", "TypeScript/JavaScript + Python 优先"],
        ],
    )
    doc.add_paragraph()
    add_para(doc, "架构原则：", bold=True)
    add_bullets(
        doc,
        [
            "分层隔离：Agent 不直接访问 OS，一切通过 Tool Layer。",
            "状态机驱动：Session 生命周期由 Orchestrator 显式管理。",
            "可测试：核心逻辑与 LLM 调用可 Mock，Tool 可单元测试。",
            "配置外置：agent.config.yaml + 环境变量控制行为。",
            "安全默认拒绝：路径/命令黑名单，write 需策略允许。",
            "本地优先：数据默认存 .agent/，不上云。",
        ],
    )

    # ── 四、与竞品对比 ──
    add_heading(doc, "四、与常见项目对比")
    add_table(
        doc,
        ["维度", "常见做法", "本项目"],
        [
            ["交互模式", "单次对话生成代码", "多 Agent + 状态机流水线"],
            ["质量保障", "不跑测试、不审查", "测试失败自动回退 + gstack 质量门禁"],
            ["迭代方式", "人工催促修复", "autoresearch 自主迭代 + Git keep/discard"],
            ["流程规范", "自由对话", "Goal Workflow 六步闭环 + Issue 卡片"],
            ["验证标准", "LLM 自评「感觉对了」", "二元验证命令（exit 0 = 通过）"],
            ["代码提交", "直接改文件", "设计/提交双检查点 + 可回滚"],
            ["部署形态", "云端 SaaS", "本地 CLI + 私有化存储"],
            ["文档体系", "仅有代码", "企业级 SRS + 架构 + ADR 决策记录"],
        ],
    )

    # ── 五、演示与落地 ──
    add_heading(doc, "五、可演示、可落地")
    add_para(doc, "Goal Workflow 完整 Demo：", bold=True)
    add_code_block(
        doc,
        [
            "# 初始化 + 规划 → 设计 → 拆解",
            "agent init",
            'agent prd "为用户模块增加邮箱验证码登录"',
            "agent spec email-login",
            "agent issues email-login",
            "",
            "# 实现 + 审查 + 交付",
            "agent goal GW-001",
            "agent approve -s <session_id>",
            "agent review GW-001",
            "agent ship GW-001",
        ],
    )
    add_para(doc, "快速通道（Bug 修复）：", bold=True)
    add_code_block(
        doc,
        [
            'agent issues --quick "修复 JWT 过期未刷新"',
            "agent goal GW-001",
        ],
    )
    add_bullets(
        doc,
        [
            "自带 examples/sample-repo 示例仓库（auth 模块 + pytest 测试套件）。",
            "无 API Key 也能跑（启发式降级 + Mock LLM），有 Key 则走真实 LLM。",
            "CLI 命令齐全：run / approve / cancel / status / diff / continue / export。",
            "100+ 项自动化测试（单元 + E2E），核心流程不依赖真实 API。",
        ],
    )

    # ── 六、面试话术参考 ──
    add_heading(doc, "六、面试话术参考")

    add_heading(doc, "6.1 30 秒项目介绍", level=2)
    add_para(
        doc,
        "我做的是一个面向真实代码仓库的多 Agent 智能编程 Copilot。"
        "它要解决的核心问题是传统 AI 辅助编程里的「上下文腐烂」——"
        "长对话里需求边界模糊、质量没有门禁、迭代全靠人工催促。"
        "我的方案是把「对话写代码」升级为 Agentic Engineering："
        "用 Goal Workflow 定义标准化研发流程，用 gstack 做质量门禁，"
        "用 autoresearch 做自主迭代加速，底层是多 Agent 编排引擎 + RAG + 工具调用，"
        "实现从 PRD 到 PR 交付的端到端闭环。",
        bold=True,
    )

    add_heading(doc, "6.2 常见追问与回答", level=2)

    add_para(doc, "Q：和 Cursor / Copilot / Devin 有什么区别？", bold=True)
    add_para(
        doc,
        "A：Cursor/Copilot 偏 IDE 内联补全和对话，Devin 偏端到端自主执行但流程黑盒。"
        "我的项目定位是工程化 Agent 平台：有标准化六步工作流、有质量门禁、"
        "有自主迭代引擎、面向企业私有化部署。"
        "更像是「把 AI 编程流程产品化」，而不是「做一个更强的补全工具」。",
    )

    add_para(doc, "Q：autoresearch 怎么保证不陷入死循环？", bold=True)
    add_para(
        doc,
        "A：四重护栏——max_iterations 默认 25 轮、token_budget 可配置、"
        "scope_files 限制修改范围、每轮失败 Git reset 立即回滚。"
        "每轮结果写入 results.jsonl，方便事后分析为什么没收敛。",
    )

    add_para(doc, "Q：你负责什么？遇到的最大挑战？", bold=True)
    add_para(
        doc,
        "A：负责整体架构设计、Orchestrator 状态机、Goal Workflow CLI、RAG 混合检索、E2E 测试。"
        "最大挑战是三层体系的层间契约设计——autoresearch 的 keep/discard 如何同步 Issue 状态、"
        "gstack blocking 如何触发 fix 循环。"
        "最终用 Issue 卡片 + 二元验证命令作为层间统一契约，解决了状态同步问题。",
    )

    add_para(doc, "Q：下一步迭代计划？", bold=True)
    add_para(
        doc,
        "A：Phase 2 计划——完整 autoresearch 循环接入 agent goal、"
        "LLM Review Agent 替代纯规则引擎、Checkpoint 恢复、Web UI + GitHub Issues 同步、"
        "PostgreSQL 替代 SQLite 支持多租户。",
    )

    # ── 七、一句话总结 ──
    add_heading(doc, "七、一句话总结")
    p = doc.add_paragraph()
    run = p.add_run(
        "本项目将 AI 编程从「聊天生成代码」升级为「有流程、有门禁、有自主迭代能力的工程化 Agent 平台」："
        "用 Issue 卡片 + 二元验证让 AI 迭代可机械判定，"
        "用 Goal Workflow + gstack + autoresearch 三层协作解决上下文腐烂和质量不可控，"
        "同时兼顾企业级安全与私有化部署需求。"
    )
    set_run_font(run, bold=True)

    # ── 附录 ──
    add_heading(doc, "附录：实现状态与文档索引")
    add_table(
        doc,
        ["分期", "状态", "主要内容"],
        [
            ["Phase 1 MVP", "主体完成", "Goal Workflow 骨架、多 Agent 编排、基础 RAG、规则 Review、CLI 全流程"],
            ["Phase 2", "部分实现", "LLM Review、Checkpoint 恢复、混合 RAG、AST 分块"],
            ["Phase 3", "规划中", "Web UI、多租户、IDE 集成、GitHub Issues 同步"],
        ],
    )
    doc.add_paragraph()
    add_para(doc, "关联文档索引：", bold=True)
    add_bullets(
        doc,
        [
            "docs/需求文档-AI代码开发Agent.md（v4.0）",
            "docs/架构设计文档-AI代码开发Agent.md",
            "docs/ADR-001-MVP技术决策.md",
            "docs/ADR-002-方法论选型.md",
            "README.md",
        ],
    )
    doc.add_paragraph()
    add_para(doc, "文档生成日期：2026-07-09")

    return doc


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = build_document()
    doc.save(OUTPUT)
    print(f"已生成: {OUTPUT}")


if __name__ == "__main__":
    main()
