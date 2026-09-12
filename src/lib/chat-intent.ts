export type StudioKind =
  | 'requirement'
  | 'architecture'
  | 'code'
  | 'test'
  | 'deploy'
  | 'workflow'
  | 'projects'
  | 'agents'
  | 'runs'

export interface ChatIntent {
  kind: StudioKind | 'chat'
  path: string
  title: string
  reply: string
  topic?: string
}

const RULES: {
  kind: StudioKind
  path: string
  title: string
  /** 仅在「明确要进工作台」时匹配；短词单独出现不再跳转 */
  keywords: string[]
  reply: (topic: string) => string
}[] = [
  {
    kind: 'requirement',
    path: '/studio/requirement',
    title: '需求分析生成',
    keywords: ['需求文档', 'prd', '用户故事', '功能清单', '需求分析'],
    reply: (topic) =>
      `好的，我可以帮你生成「${topic || '产品'}」需求文档。需要进入工作台时，点回复下方的按钮即可。`,
  },
  {
    kind: 'architecture',
    path: '/studio/architecture',
    title: '架构与流程图',
    keywords: ['架构图', '流程图', '技术方案', '技术选型', '系统图', '拓扑'],
    reply: (topic) =>
      `收到。可为「${topic || '当前项目'}」设计架构与流程图。需要进入工作台时再点下方按钮。`,
  },
  {
    kind: 'code',
    path: '/studio/code',
    title: '代码编写',
    keywords: ['写代码', '生成代码', '代码编写', '写个组件', '写个接口'],
    reply: (topic) =>
      `明白，可围绕「${topic || '功能'}」生成代码。需要进入代码工作台时再点下方按钮。`,
  },
  {
    kind: 'test',
    path: '/studio/test',
    title: '测试验证',
    keywords: ['跑一遍测', '测试用例', '回归测试', '质量报告'],
    reply: (topic) =>
      `好的，可针对「${topic || '当前模块'}」做测试验证。需要进入测试台时再点下方按钮。`,
  },
  {
    kind: 'deploy',
    path: '/studio/deploy',
    title: '部署上线',
    keywords: ['部署上线', '发布上线', 'ci/cd', 'docker 部署'],
    reply: (topic) =>
      `了解。可为「${topic || '应用'}」准备部署。需要进入部署台时再点下方按钮。`,
  },
  {
    kind: 'workflow',
    path: '/projects',
    title: '工作流编排',
    keywords: ['工作流编排', '流水线编排', '打开工作流'],
    reply: () => '可打开项目管理进入工作流编排画布。点下方按钮前往。',
  },
  {
    kind: 'projects',
    path: '/projects',
    title: '项目管理',
    keywords: ['我的项目', '项目列表', '打开项目'],
    reply: () => '可打开项目管理页。点下方按钮前往。',
  },
  {
    kind: 'agents',
    path: '/agents',
    title: 'WorkWings Agent',
    keywords: ['agent 市场', '智能体市场', '打开 agent', '内核 agent'],
    reply: () => '可查看 WorkWings 9 个 Agent 的职责、上下游和模型配置。点下方按钮前往。',
  },
  {
    kind: 'runs',
    path: '/runs',
    title: '运行记录',
    keywords: ['运行记录', '执行历史', '打开运行'],
    reply: () => '可打开运行记录查看历史。点下方按钮前往。',
  },
]

/** 用户明确要进工作台 / 做交付物，而不是在对话里先聊 */
function wantsWorkbenchNavigation(message: string): boolean {
  const t = message.trim()
  if (!t) return false

  // 明确打开 / 进入 / 跳转某工作台
  if (
    /(打开|进入|去|跳转|前往)\s*(需求|架构|代码|测试|部署|工作流|项目|agent|运行|工作台)/i.test(
      t,
    )
  ) {
    return true
  }

  // 明确要「生成/写/画」交付物（热门卡片里的开放式提问不算）
  if (
    /(给我|帮我|请)?(写|做|生成|画)(一个|一份|个)?[^。！？\n]{0,24}(需求文档|prd|架构图|流程图|代码|测试用例|部署)/i.test(
      t,
    )
  ) {
    return true
  }

  if (/(跑一遍测|部署上线|发布上线)/i.test(t)) return true

  return false
}

export function extractTopic(message: string): string {
  const patterns = [
    /(?:给我|帮我|请)?(?:写|做|生成)(?:一个|一份|个)?(.+?)(?:的)?(?:需求文档|需求|文档|架构|代码|测试|部署)/,
    /生成(?:一个|一份|个)?(.+?)(?:需求|文档|架构|代码|测试|部署)/,
    /帮我(?:做|写|生成)(.+)/,
    /关于(.+)/,
  ]
  for (const p of patterns) {
    const m = message.match(p)
    if (m?.[1]) {
      return m[1]
        .replace(/[的了吧呢啊]/g, '')
        .replace(/^(一个|一份|个)/, '')
        .trim()
        .slice(0, 32)
    }
  }
  return ''
}

export function resolveChatIntent(message: string): ChatIntent {
  const chatFallback: ChatIntent = {
    kind: 'chat',
    path: '/chat',
    title: '智能对话',
    reply:
      '我是 WorkWings Agent 编排助手。你可以这样说：\n· 「给我生成一个电商后台需求文档」\n· 「画一个系统架构流程图」\n· 「帮我写登录模块代码」\n· 「跑一遍测试并部署上线」\n\n也可以从左侧进入「工作台」，查看 WorkWings Agent 的阶段产物。',
  }

  // 开放式提问（含热门方向卡）默认留在对话页，禁止仅凭「需求/代码」等短词挂跳转
  if (!wantsWorkbenchNavigation(message)) {
    return chatFallback
  }

  const lower = message.toLowerCase()
  const topic = extractTopic(message)

  let best:
    | {
        rule: (typeof RULES)[number]
        score: number
      }
    | null = null

  for (const rule of RULES) {
    for (const keyword of rule.keywords) {
      if (!lower.includes(keyword.toLowerCase())) continue
      const score = keyword.length
      if (!best || score > best.score) {
        best = { rule, score }
      }
    }
  }

  // 部署优先于“测试环境”里的“测试”
  if (/(部署|上线|发布)/.test(lower) && best?.rule.kind === 'test') {
    const deployRule = RULES.find((r) => r.kind === 'deploy')
    if (deployRule) best = { rule: deployRule, score: 99 }
  }

  // 工作流编排优先于“内核 Agent”说明页
  if (
    /(工作流|流水线|编排|全流程)/.test(lower) &&
    best?.rule.kind === 'agents'
  ) {
    const workflowRule = RULES.find((r) => r.kind === 'workflow')
    if (workflowRule) best = { rule: workflowRule, score: 99 }
  }

  // 明确要进工作台但关键词未命中时，用生成物措辞兜底映射
  if (!best) {
    if (/(需求文档|prd|用户故事|功能清单|需求分析)/i.test(lower)) {
      best = { rule: RULES.find((r) => r.kind === 'requirement')!, score: 50 }
    } else if (/(架构图|流程图|技术方案)/i.test(lower)) {
      best = { rule: RULES.find((r) => r.kind === 'architecture')!, score: 50 }
    } else if (/(代码|组件|接口)/i.test(lower)) {
      best = { rule: RULES.find((r) => r.kind === 'code')!, score: 50 }
    } else if (/(测试|用例)/i.test(lower)) {
      best = { rule: RULES.find((r) => r.kind === 'test')!, score: 50 }
    } else if (/(部署|上线|发布)/i.test(lower)) {
      best = { rule: RULES.find((r) => r.kind === 'deploy')!, score: 50 }
    } else if (/(工作流|流水线|编排)/i.test(lower)) {
      best = { rule: RULES.find((r) => r.kind === 'workflow')!, score: 50 }
    } else if (/(项目)/i.test(lower)) {
      best = { rule: RULES.find((r) => r.kind === 'projects')!, score: 50 }
    } else if (/(agent|智能体)/i.test(lower)) {
      best = { rule: RULES.find((r) => r.kind === 'agents')!, score: 50 }
    } else if (/(运行|记录|日志)/i.test(lower)) {
      best = { rule: RULES.find((r) => r.kind === 'runs')!, score: 50 }
    }
  }

  if (best) {
    return {
      kind: best.rule.kind,
      path: best.rule.path,
      title: best.rule.title,
      topic: topic || undefined,
      reply: best.rule.reply(topic || '你的想法'),
    }
  }

  return chatFallback
}

export const STUDIO_ORDER = [
  'requirement',
  'architecture',
  'code',
  'test',
  'deploy',
] as const

export type StudioPageKind = (typeof STUDIO_ORDER)[number]

export function getNextStudio(kind: string): StudioPageKind | null {
  const idx = STUDIO_ORDER.indexOf(kind as StudioPageKind)
  if (idx < 0 || idx >= STUDIO_ORDER.length - 1) return null
  return STUDIO_ORDER[idx + 1]
}

export function getPrevStudio(kind: string): StudioPageKind | null {
  const idx = STUDIO_ORDER.indexOf(kind as StudioPageKind)
  if (idx <= 0) return null
  return STUDIO_ORDER[idx - 1]
}

export const STUDIO_KERNEL_HINT: Record<
  StudioPageKind,
  { agents: string; note: string }
> = {
  requirement: {
    agents: 'requirement',
    note: 'WorkWings Agent 编排会按 planner → ship 推进，本页聚焦 Requirement 阶段',
  },
  architecture: {
    agents: 'planner',
    note: 'WorkWings Agent 编排没有独立架构 Agent，此页由 Planner + Requirement 共同提供',
  },
  code: {
    agents: 'coding + frontend',
    note: 'WorkWings Agent 编排中的 coding + frontend，共享同一条 Run 的产物',
  },
  test: {
    agents: 'testing / debug',
    note: 'WorkWings Agent 编排中的 testing / debug，共享同一条 Run 的验收记录',
  },
  deploy: {
    agents: 'review + ship',
    note: 'WorkWings Agent 编排中的 review + ship，负责审查与交付归档',
  },
}

export const STUDIO_META: Record<
  StudioPageKind,
  {
    title: string
    subtitle: string
    placeholder: string
    accent: string
    steps: string[]
    demoTitle: string
  }
> = {
  requirement: {
    title: '需求分析生成',
    subtitle: '本页展示 WorkWings Requirement Agent，启动后按 9 Agent 编排推进',
    placeholder: '输入产品目标后启动 WorkWings Agent 编排，本页展示需求阶段…',
    accent: 'from-sky-500 to-blue-500',
    steps: ['理解目标用户', '拆解功能模块', '标注优先级', '输出验收标准'],
    demoTitle: '本地样例 · 非本次 Run',
  },
  architecture: {
    title: '架构与流程图',
    subtitle: '对应 WorkWings Planner，默认读取本次 Agent 编排结果',
    placeholder: '与需求分析共用同一目标；请先启动 WorkWings Agent 编排…',
    accent: 'from-cyan-500 to-teal-500',
    steps: ['划定系统边界', '技术选型', '绘制流程图', '定义接口契约'],
    demoTitle: '本地样例 · 非本次 Run',
  },
  code: {
    title: '代码编写',
    subtitle: '对应 WorkWings Coding + Frontend，默认读取本次 Agent 编排结果',
    placeholder: '与需求分析共用同一目标；请先启动 WorkWings Agent 编排…',
    accent: 'from-emerald-500 to-green-500',
    steps: ['解析接口契约', '生成分层代码', '规范检查', '输出可运行骨架'],
    demoTitle: '本地样例 · 非本次 Run',
  },
  test: {
    title: '测试验证',
    subtitle: '对应 WorkWings Testing / Debug，默认读取本次 Agent 编排结果',
    placeholder: '与需求分析共用同一目标；请先启动 WorkWings Agent 编排…',
    accent: 'from-amber-500 to-orange-500',
    steps: ['构建覆盖矩阵', '生成用例', '执行回归', '缺陷回流建议'],
    demoTitle: '本地样例 · 非本次 Run',
  },
  deploy: {
    title: '部署上线',
    subtitle: '对应 WorkWings Review + Ship，默认读取本次 Agent 编排结果',
    placeholder: '与需求分析共用同一目标；请先启动 WorkWings Agent 编排…',
    accent: 'from-rose-500 to-orange-500',
    steps: ['构建镜像', '流水线校验', '环境发布', '健康监控'],
    demoTitle: '本地样例 · 非本次 Run',
  },
}
