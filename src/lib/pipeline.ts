import {
  DEFAULT_KERNEL_MODELS,
  KERNEL_PIPELINE_ORDER,
  NODE_META,
  type IWorkflowEdge,
  type IWorkflowNode,
  type NodeType,
  type NodeStatus,
} from '@/lib/workflow-types';
import type { IResult } from '@/data/results';

export function applyAgentModels(
  nodes: IWorkflowNode[],
  models?: Record<string, string> | null,
): IWorkflowNode[] {
  const map = { ...DEFAULT_KERNEL_MODELS, ...(models || {}) };
  return nodes.map((n) => ({
    ...n,
    config: {
      ...n.config,
      model: map[n.type] || n.config.model || '—',
    },
  }));
}

export function buildFullPipeline(
  startX = 48,
  startY = 72,
  gapX = 210,
  gapY = 150,
  models?: Record<string, string> | null,
): {
  nodes: IWorkflowNode[];
  edges: IWorkflowEdge[];
} {
  const nodes: IWorkflowNode[] = KERNEL_PIPELINE_ORDER.map((type, i) => {
    const meta = NODE_META[type];
    const col = i % 4;
    const row = Math.floor(i / 4);
    const prev =
      i > 0 ? NODE_META[KERNEL_PIPELINE_ORDER[i - 1]].label : '用户目标';
    const next =
      i < KERNEL_PIPELINE_ORDER.length - 1
        ? NODE_META[KERNEL_PIPELINE_ORDER[i + 1]].label
        : '交付归档';
    return {
      id: type,
      agentId: type,
      type,
      label: `${meta.label} · ${type}`,
      icon: meta.icon,
      position: { x: startX + col * gapX, y: startY + row * gapY },
      config: {
        model: DEFAULT_KERNEL_MODELS[type] || '—',
        prompt: meta.defaultPrompt,
        inputSource: prev,
        outputTarget: next,
      },
      status: 'waiting' as NodeStatus,
    };
  });

  const edges: IWorkflowEdge[] = nodes.slice(0, -1).map((n, i) => ({
    id: `e-${n.id}-${nodes[i + 1].id}`,
    source: n.id,
    target: nodes[i + 1].id,
  }));

  return { nodes: applyAgentModels(nodes, models), edges };
}

/** @deprecated 编排页不再提供裁剪流水线；保留以免旧调用报错 */
export function buildAgilePipeline(models?: Record<string, string> | null) {
  return buildFullPipeline(48, 72, 210, 150, models);
}

/** WorkWings 节点 → 画布 9 Agent。审批节点落到对应 Agent 卡片。 */
const KERNEL_TO_CANVAS: Record<string, string> = {
  start: '',
  human_confirmation: 'project_analysis',
  requirement_approval: 'requirement_baseline',
  prototype_approval: 'prototype_generation',
  architecture_approval: 'architecture',
  implementation_apply: 'development',
  test: 'testing',
  security_exception_approval: 'security',
  deployment_approval: 'delivery',
  deployment_verification: 'delivery',
  end: '',
}

export function canvasNodeKey(kernelId?: string | null): string {
  const raw = String(kernelId || '').trim()
  if (!raw || raw === 'start' || raw === 'end') return ''
  return KERNEL_TO_CANVAS[raw] || raw
}

const DELIVER_AGENT_SET = new Set<string>(KERNEL_PIPELINE_ORDER)

function addDeliverKey(bag: Set<string>, raw?: string | null) {
  const key = canvasNodeKey(raw)
  if (key && DELIVER_AGENT_SET.has(key)) bag.add(key)
}

/** 9 Agent 进度：SSE 往往没有完整 node_outputs，需用当前节点/观测节点兜底。 */
export function deliverProgress(run: {
  status?: string
  current_node_id?: string | null
  failed_node_id?: string | null
  node_outputs?: Record<string, unknown> | null
  observe?: { nodes?: Array<{ node_id?: string; status?: string }> } | null
  extraKeys?: string[] | null
}): { completed: number; total: number; percent: number; current: string } {
  const total = KERNEL_PIPELINE_ORDER.length
  const statusU = (run.status || '').toUpperCase()
  const doneKeys = new Set<string>()
  for (const key of Object.keys(run.node_outputs || {})) {
    addDeliverKey(doneKeys, key)
  }
  for (const key of run.extraKeys || []) {
    addDeliverKey(doneKeys, key)
  }
  for (const node of run.observe?.nodes || []) {
    const s = String(node.status || '').toLowerCase()
    if (
      s === 'done' ||
      s === 'completed' ||
      s === 'success' ||
      s === 'ok' ||
      s === 'pass'
    ) {
      addDeliverKey(doneKeys, node.node_id)
    }
  }
  const current = canvasNodeKey(run.current_node_id || run.failed_node_id)
  const currentIdx = current
    ? KERNEL_PIPELINE_ORDER.indexOf(current as (typeof KERNEL_PIPELINE_ORDER)[number])
    : -1
  const inferred = currentIdx > 0 ? currentIdx : 0
  let completed = Math.max(doneKeys.size, inferred)
  if (statusU === 'DONE') completed = total
  completed = Math.min(Math.max(completed, 0), total)
  const running =
    statusU === 'DONE' || statusU === 'FAILED' || statusU === 'CANCELLED'
      ? false
      : Boolean(current) && completed < total
  const percent =
    statusU === 'DONE'
      ? 100
      : Math.round(((completed + (running ? 0.5 : 0)) / total) * 100)
  return { completed, total, percent, current }
}

/** 把内核 Run 写成项目管理卡片用的状态/进度 */
export function projectPatchFromRun(run: {
  status?: string
  current_node_id?: string | null
  failed_node_id?: string | null
  node_outputs?: Record<string, unknown> | null
  observe?: { nodes?: Array<{ node_id?: string; status?: string }> } | null
}): { status: 'running' | 'completed' | 'failed'; progress: number } {
  const p = deliverProgress(run)
  const s = (run.status || '').toUpperCase()
  if (s === 'DONE') return { status: 'completed', progress: 100 }
  if (s === 'FAILED' || s === 'CANCELLED') {
    return { status: 'failed', progress: p.percent }
  }
  return { status: 'running', progress: Math.min(95, p.percent) }
}

export function focusCanvasNodeFromRun(run: {
  status?: string
  current_node_id?: string | null
  failed_node_id?: string | null
  observe?: { nodes?: Array<{ node_id?: string; status?: string }> } | null
}): string {
  const failed = canvasNodeKey(run.failed_node_id)
  if (failed) return failed
  const obsFailed = [...(run.observe?.nodes || [])]
    .reverse()
    .find((n) => {
      const s = String(n.status || '').toLowerCase()
      return s === 'failed' || s === 'fail' || s === 'error'
    })
  const fromObs = canvasNodeKey(obsFailed?.node_id)
  if (fromObs) return fromObs
  return canvasNodeKey(run.current_node_id)
}

/** 把 WorkWings Run 状态映射到画布 9 Agent 节点 */
export function applyRunStatusToNodes(
  nodes: IWorkflowNode[],
  run: {
    status?: string
    current_node_id?: string | null
    failed_node_id?: string | null
    node_outputs?: Record<string, Record<string, unknown>>
  },
): IWorkflowNode[] {
  const outputs = run.node_outputs || {}
  const current = canvasNodeKey(run.current_node_id)
  const statusU = (run.status || '').toUpperCase()
  const currentIdx = current
    ? KERNEL_PIPELINE_ORDER.indexOf(current as (typeof KERNEL_PIPELINE_ORDER)[number])
    : -1
  const failedId =
    canvasNodeKey(run.failed_node_id) ||
    (statusU === 'FAILED' || statusU === 'CANCELLED' ? current : '')
  return nodes.map((n) => {
    const out =
      outputs[n.type] ||
      outputs[n.id] ||
      (n.type === 'review' ? outputs.human_review : undefined)
    const nodeIdx = KERNEL_PIPELINE_ORDER.indexOf(
      n.type as (typeof KERNEL_PIPELINE_ORDER)[number],
    )
    let status: NodeStatus = 'waiting'
    if (failedId && (n.type === failedId || n.id === failedId)) {
      status = 'failed'
    } else if (statusU === 'DONE') {
      status = 'completed'
    } else if (out) {
      const bad =
        out._success === false ||
        Boolean(out._error) ||
        String(out.status || '').toLowerCase() === 'fail'
      status = bad ? 'failed' : 'completed'
    } else if (n.type === current || n.id === current) {
      status =
        statusU === 'FAILED' || statusU === 'CANCELLED' ? 'failed' : 'running'
    } else if (currentIdx > 0 && nodeIdx >= 0 && nodeIdx < currentIdx) {
      status = 'completed'
    }
    return { ...n, status }
  })
}

export const MOCK_LOG_SEQUENCES: Record<
  string,
  { level: 'info' | 'success' | 'warn' | 'error'; message: string }[]
> = {
  planner: [
    { level: 'info', message: '解析 goal，拆分可编码子任务...' },
    { level: 'success', message: '规划完成 · 输出任务列表' },
  ],
  requirement: [
    { level: 'info', message: '结构化需求与验收标准...' },
    { level: 'success', message: '需求分析完成' },
  ],
  coding: [
    { level: 'info', message: '按子任务写入 project_root...' },
    { level: 'success', message: '编码完成' },
  ],
  frontend: [
    { level: 'info', message: '生成页面并挂入口...' },
    { level: 'success', message: '前端完成' },
  ],
  testing: [
    { level: 'info', message: '执行冒烟 / metric...' },
    { level: 'success', message: '验收通过' },
  ],
  debug: [
    { level: 'info', message: '按失败分类修复...' },
    { level: 'success', message: '调试完成' },
  ],
  review: [
    { level: 'info', message: '审查产物与阻断项...' },
    { level: 'success', message: '审查完成' },
  ],
  ship: [
    { level: 'info', message: '归档交付说明...' },
    { level: 'success', message: '交付完成' },
  ],
  analysis: [
    { level: 'info', message: '接收自然语言需求，启动语义拆解引擎...' },
    { level: 'info', message: '识别干系人、业务场景与约束条件...' },
    { level: 'info', message: '生成用户故事与功能清单，评估优先级 P0–P2' },
    { level: 'success', message: '需求分析完成 · 输出 14 个功能点与验收标准' },
  ],
  architecture: [
    { level: 'info', message: '解析需求边界，绘制系统上下文图...' },
    { level: 'info', message: '技术选型：React 19 + Node.js + PostgreSQL + Redis' },
    { level: 'info', message: '生成架构流程图与模块依赖关系...' },
    { level: 'info', message: '定义 28 个 RESTful API 与数据表结构' },
    { level: 'success', message: '架构设计完成 · 流程图与技术方案已就绪' },
  ],
  development: [
    { level: 'info', message: '按架构脚手架初始化 monorepo...' },
    { level: 'info', message: '生成前端页面、状态管理与权限守卫...' },
    { level: 'info', message: '生成后端服务、DTO 校验与仓储层...' },
    { level: 'info', message: '静态检查：ESLint / TypeScript 全部通过' },
    { level: 'success', message: '代码生成完成 · 48 个文件 / 15,620 行' },
  ],
  deployment: [
    { level: 'info', message: '构建多阶段 Docker 镜像并扫描漏洞...' },
    { level: 'info', message: '写入 GitHub Actions CI/CD 流水线...' },
    { level: 'info', message: '滚动发布至 staging，执行健康检查...' },
    { level: 'info', message: '同步生产流量，开启监控告警规则...' },
    { level: 'success', message: '部署成功 · 生产环境已上线可访问' },
  ],
  document: [
    { level: 'info', message: '汇总需求/架构/接口/运维产物...' },
    { level: 'info', message: '生成 OpenAPI 文档与运维手册...' },
    { level: 'success', message: '交付文档包生成完毕' },
  ],
};

export function generateSmartReply(
  userMsg: string,
  stage?: NodeType | null,
): string {
  const lower = userMsg.toLowerCase();
  if (lower.includes('部署') || stage === 'deployment') {
    return '部署链路建议：\n\n1. 先在 staging 验证健康检查与回滚脚本\n2. 使用蓝绿/滚动发布降低风险\n3. 上线后盯紧错误率、延迟与资源水位\n\n需要我直接生成 Dockerfile + CI 配置吗？';
  }
  if (lower.includes('测试') || stage === 'testing') {
    return '测试策略建议：\n\n1. 核心交易路径优先做端到端覆盖\n2. 对权限与边界输入做负向用例\n3. 失败用例自动回流到代码修复节点\n\n我可以按当前代码结构生成用例清单。';
  }
  if (lower.includes('架构') || stage === 'architecture') {
    return '架构侧我会输出：\n\n1. 系统上下文与模块依赖流程图\n2. 数据模型与 API 契约\n3. 扩展点与技术风险清单\n\n如果你有性能/合规约束，告诉我，我会调整选型。';
  }
  if (lower.includes('代码') || stage === 'development') {
    return '代码生成会遵循：\n\n1. 分层清晰（UI / Domain / Infra）\n2. TypeScript 严格模式与可测性\n3. 关键鉴权与输入校验默认开启\n\n请指出优先模块，我先产出可运行骨架。';
  }
  if (lower.includes('需求') || stage === 'analysis') {
    return '我会把需求整理成：\n\n1. 产品概述与目标用户\n2. 功能清单（含优先级）\n3. 验收标准与非功能指标\n\n可以直接描述业务场景，我来结构化输出 PRD。';
  }
  return '已理解。建议按「需求 → 架构 → 代码 → 测试 → 部署」推进：\n\n1. 先锁定 P0 范围\n2. 再落架构与接口契约\n3. 最后自动化测试并上线\n\n也可以一键生成完整流水线后直接运行。';
}

export function buildResultForNode(
  projectId: string,
  type: NodeType,
  projectName: string,
  userPrompt?: string,
): IResult | null {
  const id = `gen-${type}-${Date.now()}`;
  const brief = (userPrompt || '').trim();
  switch (type) {
    case 'analysis':
      return {
        id,
        projectId,
        type: 'requirement',
        title: `${projectName} · 智能需求文档`,
        summary: '由需求分析 Agent 自动拆解生成的结构化 PRD',
        content: `# ${projectName} 需求文档

${brief ? `> 来源需求：${brief}
` : ''}
## 1. 产品概述
围绕「${projectName}」识别核心目标与使用场景，形成可落地的产品范围与里程碑。${
          brief
            ? '本文档严格依据用户输入撰写，不套用无关行业模板。'
            : '基于自然语言输入形成产品范围。'
        }

## 2. 功能需求（智能排序）
| 功能 | 优先级 | 验收标准 |
|------|--------|----------|
| ${projectName}核心玩法 / 主流程 | P0 | 主路径可完成端到端闭环 |
| 基础交互与状态反馈 | P0 | 关键操作有明确反馈与边界处理 |
| 进度 / 记录能力 | P1 | 关键数据可保存与回看 |
| 扩展与设置项 | P2 | 不影响主流程稳定性 |

## 3. 非功能需求
- 交互流畅，主路径无明显卡顿
- 关键异常可恢复，不丢关键状态
- 代码结构清晰，便于后续迭代

## 4. 下一步
移交架构设计 Agent，针对「${projectName}」生成技术方案与流程图。
`,
      };
    case 'architecture':
      return {
        id,
        projectId,
        type: 'architecture',
        title: `${projectName} · 架构方案与流程图`,
        summary: '含系统架构图、模块依赖与部署拓扑',
        content: `# 系统架构设计

## 技术选型
- 前端：React 19 + TypeScript + Vite
- 后端：Node.js + NestJS
- 数据：PostgreSQL + Redis
- 部署：Docker + K8s / 云托管

## 架构流程图

\`\`\`
┌────────────┐    ┌────────────┐    ┌────────────┐
│  Web / App │───▶│  API Gateway│───▶│  业务服务   │
└────────────┘    └────────────┘    └─────┬──────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    ▼                     ▼                     ▼
              ┌──────────┐         ┌──────────┐         ┌──────────┐
              │ 用户服务  │         │ 业务服务  │         │ 分析服务  │
              └────┬─────┘         └────┬─────┘         └────┬─────┘
                   │                    │                    │
                   └──────────┬─────────┴──────────┬─────────┘
                              ▼                    ▼
                        ┌──────────┐         ┌──────────┐
                        │ PostgreSQL│         │  Redis   │
                        └──────────┘         └──────────┘
\`\`\`

## 部署拓扑
开发 → CI 构建 → Staging 验证 → 生产滚动发布
`,
      };
    case 'development':
      return {
        id,
        projectId,
        type: 'code',
        title: `${projectName} · 核心代码`,
        summary: '按架构自动生成的可运行代码骨架',
        content: `// src/services/OrderService.ts
export class OrderService {
  async create(input: CreateOrderDto) {
    await this.auth.assertPermission(input.userId, 'order:create')
    const order = await this.repo.insert({
      ...input,
      status: 'pending',
      createdAt: new Date(),
    })
    await this.events.publish('order.created', order.id)
    return order
  }
}

// src/api/orders.controller.ts
@Post()
async create(@Body() dto: CreateOrderDto) {
  return this.orders.create(dto)
}
`,
        fileTree: [
          {
            name: 'src',
            children: [
              { name: 'OrderService.ts' },
              { name: 'orders.controller.ts' },
              { name: 'AuthGuard.ts' },
              { name: 'Dashboard.tsx' },
            ],
          },
          {
            name: 'infra',
            children: [{ name: 'Dockerfile' }, { name: 'ci.yml' }],
          },
        ],
      };
    case 'testing':
      return {
        id,
        projectId,
        type: 'test',
        title: `${projectName} · 测试报告`,
        summary: '自动化用例执行与缺陷回流建议',
        content: `# 测试报告

## 概览
- 用例总数：58
- 通过：55
- 失败：3
- 通过率：95%

## 失败用例
1. 部分退款状态机未同步
2. 大数据导出超时
3. 并发下库存扣减竞态

## 建议
优先修复 P0 状态机与库存锁，然后重新触发回归流水线。
`,
        stats: { total: 58, passed: 55, failed: 3 },
      };
    case 'deployment':
      return {
        id,
        projectId,
        type: 'deployment',
        title: `${projectName} · 部署上线记录`,
        summary: '镜像构建、环境发布与健康检查结果',
        content: `# 部署上线报告

## 流水线
1. ✅ 单元/集成测试通过
2. ✅ 镜像构建 agentflow:1.0.0
3. ✅ 漏洞扫描无高危
4. ✅ Staging 健康检查通过
5. ✅ 生产滚动发布完成

## 环境地址
- Staging: https://staging.example.com
- Production: https://app.example.com

## 监控
- 错误率：0.02%
- P95 延迟：148ms
- CPU / 内存：正常
`,
        deployMeta: {
          version: '1.0.0',
          env: 'production',
          url: 'https://app.example.com',
          health: 'healthy',
        },
      };
    case 'document':
      return {
        id,
        projectId,
        type: 'document',
        title: `${projectName} · 交付文档`,
        summary: 'API、运维与使用说明打包',
        content: `# 项目交付文档

## 包含内容
- OpenAPI 接口说明
- 部署与回滚手册
- 权限模型说明
- 版本变更记录

## 快速开始
\`\`\`bash
npm install
npm run dev
\`\`\`
`,
      };
    default:
      return null;
  }
}
