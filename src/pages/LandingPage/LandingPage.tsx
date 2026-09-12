import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import {
  ArrowRight,
  Bot,
  Boxes,
  Check,
  CheckCircle2,
  Cloud,
  Code2,
  Cpu,
  Database,
  FileCode2,
  FileText,
  GitBranch,
  HardDrive,
  Layers,
  LayoutDashboard,
  LockKeyhole,
  MessageSquare,
  Network,
  PackageCheck,
  PauseCircle,
  PlayCircle,
  Plug,
  Server,
  Shield,
  Sparkles,
  Workflow,
  type LucideIcon,
} from 'lucide-react'
import BrandLogo from '@/components/BrandLogo'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { applyThemePalette, getStoredPalette } from '@/lib/theme'
import { isAuthenticated } from '@/lib/auth'

type FeatureTabId = 'orchestration' | 'approval' | 'artifacts' | 'runtime'

type FeatureHighlight = {
  title: string
  desc: string
  bullets: string[]
  icon: LucideIcon
  accent: string
  mock: ReactNode
}

type FeatureTab = {
  id: FeatureTabId
  label: string
  icon: LucideIcon
  title: string
  subtitle: string
  highlights: FeatureHighlight[]
}

const featureTabs: FeatureTab[] = [
  {
    id: 'orchestration',
    label: '受控编排',
    icon: Workflow,
    title: 'WorkflowEngine 接管工作流内核',
    subtitle: '状态推进由后端确定性引擎负责，Agent 只产出结构化结果。',
    highlights: [
      {
        title: '可恢复的状态机',
        desc: 'WorkWings 让开始、分析、审批、生成、测试和交付都沿着可审计节点推进。',
        bullets: ['统一状态转移入口', '检查点支持恢复', '失败节点可重试'],
        icon: GitBranch,
        accent: 'from-primary/20 to-primary/5',
        mock: <OrchestrationMock />,
      },
      {
        title: 'Agent 不直接改业务状态',
        desc: '多智能体协作通过 ArtifactRef 和校验后的 schema 传递，避免自然语言串改流程。',
        bullets: ['产物引用作为契约', '节点注册集中管理', '流程边界清晰'],
        icon: Bot,
        accent: 'from-intel/20 to-intel/5',
        mock: <AgentBoundaryMock />,
      },
    ],
  },
  {
    id: 'approval',
    label: '人工审批',
    icon: PauseCircle,
    title: '关键节点先暂停再恢复',
    subtitle: '需求、原型、架构、安全例外和部署节点都可以进入人工确认。',
    highlights: [
      {
        title: '审批卡片就在执行流里',
        desc: '审批不再藏在弹窗或日志里，用户可以在会话流中看到证据、风险和恢复动作。',
        bullets: ['暂停状态可见', '审批动作留痕', '恢复后继续同一工作流'],
        icon: PauseCircle,
        accent: 'from-amber-500/20 to-amber-500/5',
        mock: <ApprovalMock />,
      },
      {
        title: '安全边界默认收紧',
        desc: '高风险工具、目录写入和部署步骤必须经过权限判断、沙箱边界与审计记录。',
        bullets: ['工具调用可追踪', '项目目录边界校验', '拒绝越权写入'],
        icon: Shield,
        accent: 'from-primary/20 to-primary/5',
        mock: <GuardrailMock />,
      },
    ],
  },
  {
    id: 'artifacts',
    label: '产物沉淀',
    icon: PackageCheck,
    title: '文档、原型和代码都有来源',
    subtitle: '每个阶段的输出都落入平台存储，再以卡片形式回到工作台。',
    highlights: [
      {
        title: '需求和原型可浏览',
        desc: '需求分析、基线确认、原型图和架构草案以 Artifact 卡片展示，方便复核。',
        bullets: ['Markdown 与文档并存', '原型图可预览', '产物挂接到项目'],
        icon: FileText,
        accent: 'from-emerald-500/20 to-emerald-500/5',
        mock: <ArtifactMock />,
      },
      {
        title: '落盘与事件同时发生',
        desc: '工作流事件、审计记录、检查点和产物引用一起持久化，不靠前端临时状态兜底。',
        bullets: ['事件可回放', 'ArtifactRef 可追溯', '存储作为事实来源'],
        icon: Database,
        accent: 'from-intel/20 to-intel/5',
        mock: <PersistenceMock />,
      },
    ],
  },
  {
    id: 'runtime',
    label: '事件流',
    icon: MessageSquare,
    title: '像 Codex 一样看见执行过程',
    subtitle: '右侧会话流展示模型消息、工具命令、审批暂停和工作流事件。',
    highlights: [
      {
        title: 'SSE 实时事件流',
        desc: '执行时把节点状态、命令、模型摘要和产物卡片连续推送到前端。',
        bullets: ['无需长时间空转', '运行状态逐步更新', '失败原因直接暴露'],
        icon: Network,
        accent: 'from-sky-500/20 to-sky-500/5',
        mock: <RuntimeMock />,
      },
      {
        title: '模型路由按 Agent 配置',
        desc: '会话可选择 Auto，让当前 Agent 使用自身默认模型，前端只展示路由结果。',
        bullets: ['前端不暴露密钥', 'Agent 默认模型可审计', '成本与耗时可记录'],
        icon: Cpu,
        accent: 'from-primary/20 to-primary/5',
        mock: <ModelRouteMock />,
      },
    ],
  },
]

const coreModules = [
  { icon: Workflow, title: '项目工作流', desc: '从上传材料到交付验收的确定性节点链' },
  { icon: Bot, title: '多模态分析', desc: '文本和图片材料进入统一分析入口' },
  { icon: FileText, title: '需求基线', desc: '需求分析结果沉淀为可审批文档' },
  { icon: Layers, title: '原型生成', desc: '原型图和设计说明绑定项目产物' },
  { icon: PauseCircle, title: '审批恢复', desc: '人工确认后从检查点继续执行' },
  { icon: PackageCheck, title: 'Artifact 持久化', desc: '事件、审计、产物和文件引用可追踪' },
]

type TechItem = {
  name: string
  icon: LucideIcon
}

type TechCategory = {
  label: string
  icon: LucideIcon
  items: TechItem[]
}

const techCategories: TechCategory[] = [
  {
    label: 'AgentFlow 前端',
    icon: LayoutDashboard,
    items: [
      { name: 'React 19', icon: Code2 },
      { name: 'Vite 6', icon: Sparkles },
      { name: 'TypeScript', icon: FileCode2 },
      { name: 'Tailwind CSS', icon: LayoutDashboard },
      { name: 'Framer Motion', icon: PlayCircle },
      { name: 'Radix UI', icon: Boxes },
      { name: 'React Flow', icon: GitBranch },
    ],
  },
  {
    label: 'WorkWings 后端',
    icon: Server,
    items: [
      { name: 'FastAPI', icon: Server },
      { name: 'Python 3.12', icon: Code2 },
      { name: 'WorkflowEngine', icon: Workflow },
      { name: 'Agent Runtime', icon: Bot },
      { name: 'Alembic', icon: Database },
      { name: 'SSE Events', icon: Network },
    ],
  },
  {
    label: '数据与检索',
    icon: Database,
    items: [
      { name: 'MySQL', icon: Database },
      { name: 'Redis', icon: Cpu },
      { name: 'Elasticsearch', icon: Network },
      { name: 'MinIO', icon: HardDrive },
      { name: 'ArtifactRef', icon: PackageCheck },
    ],
  },
  {
    label: '部署与安全',
    icon: Cloud,
    items: [
      { name: 'Docker Compose', icon: Boxes },
      { name: 'Nginx / Caddy', icon: Server },
      { name: 'HTTPS / Cookie', icon: LockKeyhole },
      { name: 'CORS Policy', icon: Shield },
      { name: 'Model Router', icon: Plug },
    ],
  },
]

const scenarios = [
  {
    icon: FileText,
    title: '软件交付',
    desc: '从需求分析、原型生成到代码项目落盘，适合需要审计链路的团队。',
    tags: ['需求文档', '原型卡片', '代码目录'],
  },
  {
    icon: PauseCircle,
    title: '需求评审',
    desc: '在人类确认前暂停工作流，把证据、风险和下一步操作放在同一界面。',
    tags: ['人工审批', '确认恢复', '记录留痕'],
  },
  {
    icon: GitBranch,
    title: '原型与架构',
    desc: '在同一个项目上下文里串联原型、架构、实现、测试和安全检查。',
    tags: ['架构草案', '节点推进', '检查点'],
  },
  {
    icon: Shield,
    title: '审批型自动化',
    desc: '保留 WorkWings 的受控编排，把执行命令和模型消息变成可复核流。',
    tags: ['事件流', '权限边界', '审计记录'],
  },
]

const securityItems = [
  { icon: Workflow, title: '状态机唯一推进', desc: 'WorkflowEngine 是工作流状态转移的唯一入口' },
  { icon: PauseCircle, title: '审批动作留痕', desc: '暂停、确认、驳回和恢复都有事件记录' },
  { icon: LockKeyhole, title: '密钥只在服务端', desc: '模型 Key、Token 和连接串不进入前端 bundle' },
  { icon: Shield, title: '项目目录边界', desc: '文件写入必须限制在当前项目目录内' },
]

const steps = [
  { n: '01', title: '创建项目并上传材料', desc: '文本、图片和项目上下文进入 WorkWings 分析入口。' },
  { n: '02', title: '运行受控工作流', desc: '多模态分析、项目解析和需求基线按节点推进。' },
  { n: '03', title: '审批后沉淀产物', desc: '确认后继续生成原型、架构、代码和测试结果。' },
]

const LANDING_HEADER_H = 64

function ProductPanel({
  title,
  status,
  children,
}: {
  title: string
  status?: string
  children: ReactNode
}) {
  return (
    <div className="overflow-hidden rounded-2xl border border-border/50 bg-card/90 shadow-xl shadow-primary/10 transition duration-300 group-hover:border-primary/30 group-hover:shadow-primary/15">
      <div className="flex items-center justify-between gap-4 border-b border-border/40 px-4 py-3">
        <span className="truncate text-xs font-medium text-muted-foreground">{title}</span>
        {status && (
          <span className="shrink-0 rounded-full border border-primary/30 bg-primary/10 px-2.5 py-1 text-[10px] font-medium text-primary">
            {status}
          </span>
        )}
      </div>
      <div className="p-4">{children}</div>
    </div>
  )
}

function StatusLine({
  icon: Icon,
  title,
  meta,
  tone = 'default',
}: {
  icon: LucideIcon
  title: string
  meta: string
  tone?: 'default' | 'success' | 'waiting'
}) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-border/40 bg-background/45 px-3 py-2.5">
      <span
        className={cn(
          'mt-0.5 inline-flex size-6 shrink-0 items-center justify-center rounded-full border',
          tone === 'success' && 'border-emerald-400/40 bg-emerald-400/10 text-emerald-300',
          tone === 'waiting' && 'border-amber-300/40 bg-amber-300/10 text-amber-200',
          tone === 'default' && 'border-primary/35 bg-primary/10 text-primary',
        )}
      >
        <Icon className="size-3.5" />
      </span>
      <div className="min-w-0">
        <p className="truncate text-sm font-medium">{title}</p>
        <p className="mt-0.5 text-xs text-muted-foreground">{meta}</p>
      </div>
    </div>
  )
}

function WorkflowRunMock() {
  const events = [
    { icon: CheckCircle2, title: 'multimodal_analysis', meta: '材料解析完成', tone: 'success' as const },
    { icon: CheckCircle2, title: 'project_analysis', meta: '项目结构与目标已归档', tone: 'success' as const },
    { icon: PauseCircle, title: 'human_confirmation', meta: '等待确认需求基线', tone: 'waiting' as const },
    { icon: PackageCheck, title: 'requirement_baseline', meta: '确认后生成文档和原型卡片', tone: 'default' as const },
  ]

  return (
    <ProductPanel title="WorkWings run stream" status="waiting_approval">
      <div className="space-y-3">
        {events.map((event) => (
          <StatusLine key={event.title} {...event} />
        ))}
        <div className="rounded-xl border border-amber-300/30 bg-amber-300/10 p-3">
          <p className="text-sm font-medium text-amber-100">确认需求基线后继续</p>
          <p className="mt-1 text-xs text-muted-foreground">
            将继续执行原型生成、架构分析、代码实现和测试节点。
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {['approve', 'request_changes'].map((action) => (
              <span key={action} className="rounded-md bg-background/55 px-2 py-1 font-mono text-[10px]">
                {action}
              </span>
            ))}
          </div>
        </div>
      </div>
    </ProductPanel>
  )
}

function OrchestrationMock() {
  return (
    <ProductPanel title="WorkflowEngine" status="deterministic">
      <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
        {['start', 'analysis', 'approval', 'delivery'].map((node, index) => (
          <div key={node} className="rounded-xl border border-primary/25 bg-primary/10 p-3">
            <p className="font-mono text-[10px] text-primary">node {index + 1}</p>
            <p className="mt-1 font-medium">{node}</p>
          </div>
        ))}
      </div>
      <div className="mt-3 rounded-xl border border-border/40 bg-background/45 px-3 py-2 font-mono text-[11px] text-muted-foreground">
        state = waiting_approval
      </div>
    </ProductPanel>
  )
}

function AgentBoundaryMock() {
  return (
    <ProductPanel title="Agent output contract" status="schema checked">
      <div className="space-y-2 font-mono text-[11px] text-muted-foreground">
        <p className="text-foreground">artifact_ref: requirement-baseline.md</p>
        <p>producer: project_analysis_agent</p>
        <p>schema: requirement_baseline.v1</p>
        <p className="text-primary">next_state controlled by WorkflowEngine</p>
      </div>
    </ProductPanel>
  )
}

function ApprovalMock() {
  return (
    <ProductPanel title="Human approval" status="paused">
      <div className="space-y-3">
        <div className="rounded-xl border border-amber-300/30 bg-amber-300/10 p-3">
          <p className="text-sm font-medium">需求基线需要确认</p>
          <p className="mt-1 text-xs text-muted-foreground">
            审批后继续原型生成，驳回则回到需求修订节点。
          </p>
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <span className="rounded-lg bg-primary px-3 py-2 text-center font-medium text-primary-foreground">
            确认继续
          </span>
          <span className="rounded-lg border border-border/50 bg-background/45 px-3 py-2 text-center">
            要求修改
          </span>
        </div>
      </div>
    </ProductPanel>
  )
}

function GuardrailMock() {
  return (
    <ProductPanel title="Tool permission" status="guarded">
      <div className="space-y-2">
        <StatusLine icon={LockKeyhole} title="write_project_file" meta="/projects/aitest/docs/requirement.md" />
        <StatusLine icon={Shield} title="path boundary" meta="allowed inside project directory" tone="success" />
      </div>
    </ProductPanel>
  )
}

function ArtifactMock() {
  return (
    <ProductPanel title="Artifacts" status="persisted">
      <div className="grid gap-2 sm:grid-cols-2">
        {[
          { icon: FileText, name: '需求分析.md', meta: 'Project analysis' },
          { icon: FileText, name: '需求分析.docx', meta: 'Review copy' },
          { icon: Layers, name: 'prototype.png', meta: 'Preview card' },
          { icon: Code2, name: 'src/', meta: 'Code project' },
        ].map((item) => (
          <div key={item.name} className="rounded-xl border border-border/40 bg-background/45 p-3">
            <item.icon className="size-4 text-primary" />
            <p className="mt-2 truncate text-sm font-medium">{item.name}</p>
            <p className="text-xs text-muted-foreground">{item.meta}</p>
          </div>
        ))}
      </div>
    </ProductPanel>
  )
}

function PersistenceMock() {
  return (
    <ProductPanel title="Platform storage" status="source of truth">
      <div className="space-y-2">
        {['events', 'audit_records', 'checkpoints', 'artifact_refs'].map((item) => (
          <div key={item} className="flex items-center justify-between rounded-lg border border-border/35 bg-background/45 px-3 py-2">
            <span className="font-mono text-[11px] text-muted-foreground">{item}</span>
            <CheckCircle2 className="size-4 text-primary" />
          </div>
        ))}
      </div>
    </ProductPanel>
  )
}

function RuntimeMock() {
  return (
    <ProductPanel title="Conversation stream" status="live">
      <div className="space-y-2 text-xs">
        <StatusLine icon={MessageSquare} title="model.message" meta="已完成项目解析，等待用户确认" />
        <StatusLine icon={Code2} title="tool.command" meta="write artifact requirement-baseline.md" tone="success" />
        <StatusLine icon={PauseCircle} title="workflow.event" meta="paused at human_confirmation" tone="waiting" />
      </div>
    </ProductPanel>
  )
}

function ModelRouteMock() {
  return (
    <ProductPanel title="Model router" status="Auto">
      <div className="space-y-2 font-mono text-[11px] text-muted-foreground">
        <p>multimodal_agent: deepseek vision route</p>
        <p>requirement_agent: qwen strongest fit</p>
        <p>coding_agent: qwen code route</p>
        <p className="text-primary">frontend displays route result only</p>
      </div>
    </ProductPanel>
  )
}

export default function LandingPage() {
  const [activeTab, setActiveTab] = useState<FeatureTabId>('orchestration')
  const prefersReducedMotion = useReducedMotion()
  const loggedIn = isAuthenticated()

  useEffect(() => {
    applyThemePalette(getStoredPalette())
  }, [])

  const primaryHref = loggedIn ? '/chat' : '/login'
  const primaryLabel = loggedIn ? '进入工作台' : '立即使用'

  const scrollToSection = useCallback((id: string) => {
    const el = document.getElementById(id)
    if (!el) return
    const top = el.getBoundingClientRect().top + window.scrollY - LANDING_HEADER_H - 12
    window.scrollTo({ top: Math.max(0, top), behavior: 'smooth' })
  }, [])

  const switchFeatureTab = useCallback((id: FeatureTabId) => {
    setActiveTab(id)
  }, [])

  const currentTab = featureTabs.find((t) => t.id === activeTab)!

  return (
    <div className="relative min-h-svh">
      <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden" aria-hidden>
        <div className="tech-ambient h-full">
          <div className="tech-aurora" />
          <span className="tech-blob tech-blob-a" />
          <span className="tech-blob tech-blob-b" />
          <span className="tech-blob tech-blob-c" />
        </div>
      </div>

      <header className="fixed inset-x-0 top-0 z-50 border-b border-border/40 bg-background/80 backdrop-blur-xl supports-[backdrop-filter]:bg-background/70">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <button
            type="button"
            onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
            className="rounded-lg transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            aria-label="返回 WorkWings 首页顶部"
          >
            <BrandLogo size={56} />
          </button>
          <nav className="hidden items-center gap-8 text-sm text-muted-foreground md:flex">
            {(
              [
                ['capabilities', '产品能力'],
                ['tech', '融合技术栈'],
                ['scenarios', '适用场景'],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => scrollToSection(id)}
                className="transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                {label}
              </button>
            ))}
            <Link to="/terms" state={{ from: '/' }} className="transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background">
              服务协议
            </Link>
          </nav>
          <div className="flex items-center gap-3">
            {!loggedIn && (
              <Button variant="ghost" size="sm" asChild>
                <Link to="/login">登录</Link>
              </Button>
            )}
            <Button size="sm" className="rounded-full px-5 shadow-lg shadow-primary/20" asChild>
              <Link to={primaryHref}>
                {primaryLabel}
                <ArrowRight className="size-4" />
              </Link>
            </Button>
          </div>
        </div>
      </header>

      <main className="relative z-10 pt-16">
        <section className="relative mx-auto grid max-w-6xl gap-12 px-6 pb-16 pt-16 lg:grid-cols-2 lg:items-center lg:gap-16 lg:pt-20">
          <motion.div
            initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55 }}
          >
            <motion.div
              className="mb-6 inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-4 py-1.5 text-xs font-medium text-primary"
              animate={
                prefersReducedMotion
                  ? undefined
                  : {
                      boxShadow: [
                        '0 0 0 0 hsl(var(--primary) / 0)',
                        '0 0 20px 0 hsl(var(--primary) / 0.15)',
                        '0 0 0 0 hsl(var(--primary) / 0)',
                      ],
                    }
              }
              transition={{ duration: 3, repeat: Infinity }}
            >
              <Sparkles className="size-3.5" />
              WorkWings · Controlled Multi-Agent Workflow
            </motion.div>
            <h1 className="font-display text-4xl font-bold leading-[1.12] tracking-tight md:text-5xl lg:text-[3.2rem]">
              把多智能体交付变成可审批、可追踪、可落盘的工作流
            </h1>
            <p className="mt-6 max-w-lg text-base leading-relaxed text-muted-foreground md:text-lg">
              AgentFlow 前端承载工作台体验，WorkWings 后端负责状态机、审批、事件流与产物持久化。
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-4">
              <motion.div whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.98 }}>
                <Button size="lg" className="h-12 rounded-full px-8 text-base shadow-lg shadow-primary/25" asChild>
                  <Link to={primaryHref}>
                    {primaryLabel}
                    <ArrowRight className="size-5" />
                  </Link>
                </Button>
              </motion.div>
              {!loggedIn && (
                <motion.div whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.98 }}>
                  <Button variant="outline" size="lg" className="h-12 rounded-full px-8 text-base" asChild>
                    <Link to="/register">免费注册</Link>
                  </Button>
                </motion.div>
              )}
            </div>
            <div className="mt-10 grid max-w-xl grid-cols-3 gap-5">
              {[
                { value: '19', label: 'WorkWings 节点' },
                { value: 'SSE', label: '实时事件流' },
                { value: 'React + FastAPI', label: '融合栈' },
              ].map((s) => (
                <div key={s.label} className="min-w-0">
                  <p className="truncate font-display text-xl font-bold md:text-2xl">{s.value}</p>
                  <p className="mt-1 text-sm text-muted-foreground">{s.label}</p>
                </div>
              ))}
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: prefersReducedMotion ? 1 : 0.94, y: prefersReducedMotion ? 0 : 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.08 }}
            className="group relative mx-auto w-full max-w-lg lg:max-w-none"
          >
            <motion.div
              animate={prefersReducedMotion ? undefined : { y: [0, -8, 0] }}
              transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut' }}
            >
              <div className="rounded-2xl border border-border/60 bg-card/80 p-1 shadow-2xl shadow-primary/10 backdrop-blur-sm transition duration-500 group-hover:border-primary/40 group-hover:shadow-primary/20">
                <WorkflowRunMock />
              </div>
            </motion.div>
            <div className="pointer-events-none absolute -right-8 -top-8 size-36 rounded-full bg-primary/20 blur-3xl" />
            <div className="pointer-events-none absolute -bottom-6 -left-6 size-28 rounded-full bg-intel/15 blur-3xl" />
          </motion.div>
        </section>

        <section id="capabilities" className="relative scroll-mt-20 border-t border-border/40 bg-card/15 py-20">
          <div className="mx-auto max-w-6xl px-6">
            <div className="mx-auto max-w-2xl text-center">
              <h2 className="font-display text-3xl font-bold tracking-tight md:text-4xl">
                WorkWings 的交付控制面
              </h2>
              <p className="mt-4 text-muted-foreground">
                从工作流内核、人工审批到产物持久化，前端只呈现可确认的执行事实。
              </p>
            </div>

            <div className="mt-10 flex flex-wrap justify-center gap-2">
              {featureTabs.map((tab) => {
                const active = activeTab === tab.id
                return (
                  <motion.button
                    key={tab.id}
                    type="button"
                    onClick={() => switchFeatureTab(tab.id)}
                    whileHover={{ scale: 1.04 }}
                    whileTap={{ scale: 0.97 }}
                    className={cn(
                      'inline-flex items-center gap-2 rounded-full border px-4 py-2.5 text-sm font-medium transition-all duration-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background',
                      active
                        ? 'border-primary/50 bg-primary text-primary-foreground shadow-lg shadow-primary/25'
                        : 'border-border/50 bg-background/60 text-muted-foreground hover:border-primary/30 hover:bg-card/80 hover:text-foreground',
                    )}
                  >
                    <tab.icon className="size-4" />
                    {tab.label}
                  </motion.button>
                )
              })}
            </div>

            <AnimatePresence mode="wait">
              <motion.div
                key={activeTab}
                initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 14 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: prefersReducedMotion ? 0 : -6 }}
                transition={{ type: 'spring', stiffness: 320, damping: 32, mass: 0.8 }}
                className="mt-14"
              >
                <div className="mb-12 text-center">
                  <h3 className="font-display text-2xl font-bold md:text-3xl">{currentTab.title}</h3>
                  <p className="mx-auto mt-3 max-w-2xl text-muted-foreground">{currentTab.subtitle}</p>
                </div>

                <div className="space-y-16">
                  {currentTab.highlights.map((h, i) => (
                    <motion.div
                      key={h.title}
                      initial={{ opacity: 0, x: prefersReducedMotion ? 0 : i % 2 === 0 ? -20 : 20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.4, delay: i * 0.08 }}
                      className={cn(
                        'group grid items-center gap-10 lg:grid-cols-2',
                        i % 2 === 1 && 'lg:[&>*:first-child]:order-2',
                      )}
                    >
                      <div className="space-y-4">
                        <div
                          className={cn(
                            'inline-flex rounded-xl bg-gradient-to-br p-3 text-primary',
                            h.accent,
                          )}
                        >
                          <h.icon className="size-5" />
                        </div>
                        <h4 className="font-display text-xl font-semibold md:text-2xl">{h.title}</h4>
                        <p className="leading-relaxed text-muted-foreground">{h.desc}</p>
                        <ul className="space-y-2">
                          {h.bullets.map((b) => (
                            <li key={b} className="flex items-start gap-2 text-sm">
                              <Check className="mt-0.5 size-4 shrink-0 text-primary" />
                              <span>{b}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                      <motion.div
                        whileHover={{ y: prefersReducedMotion ? 0 : -6, scale: prefersReducedMotion ? 1 : 1.02 }}
                        transition={{ type: 'spring', stiffness: 300, damping: 22 }}
                        className="group"
                      >
                        {h.mock}
                      </motion.div>
                    </motion.div>
                  ))}
                </div>
              </motion.div>
            </AnimatePresence>
          </div>
        </section>

        <section className="relative z-10 py-16">
          <div className="mx-auto max-w-6xl px-6">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {coreModules.map((m, i) => (
                <motion.div
                  key={m.title}
                  initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 16 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.05 }}
                  whileHover={{ y: prefersReducedMotion ? 0 : -4, scale: prefersReducedMotion ? 1 : 1.02 }}
                  className="group rounded-2xl border border-border/50 bg-background/40 p-5 transition-colors hover:border-primary/35 hover:bg-card/60 hover:shadow-lg hover:shadow-primary/5"
                >
                  <div className="mb-3 inline-flex rounded-lg bg-primary/10 p-2.5 text-primary transition group-hover:bg-primary/20">
                    <m.icon className="size-4" />
                  </div>
                  <h3 className="font-semibold">{m.title}</h3>
                  <p className="mt-1 text-sm text-muted-foreground">{m.desc}</p>
                </motion.div>
              ))}
            </div>
          </div>
        </section>

        <section id="tech" className="relative scroll-mt-20 border-t border-border/40 bg-card/15 py-20">
          <div className="mx-auto max-w-6xl px-6">
            <div className="mx-auto max-w-2xl text-center">
              <h2 className="font-display text-3xl font-bold tracking-tight md:text-4xl">
                两套项目能力合并后的技术栈
              </h2>
              <p className="mt-4 text-muted-foreground">
                AgentFlow 前端负责可视化工作台，WorkWings 后端负责编排、审批、存储与模型路由。
              </p>
            </div>

            <div className="mt-12 grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
              {techCategories.flatMap((cat, ci) =>
                cat.items.map((item, i) => (
                  <motion.div
                    key={`${cat.label}-${item.name}`}
                    initial={{ opacity: 0, scale: prefersReducedMotion ? 1 : 0.92 }}
                    whileInView={{ opacity: 1, scale: 1 }}
                    viewport={{ once: true, margin: '-20px' }}
                    transition={{ duration: 0.25, delay: (ci * 0.04) + i * 0.02 }}
                    whileHover={{ y: prefersReducedMotion ? 0 : -6, scale: prefersReducedMotion ? 1 : 1.04 }}
                    className="group relative flex min-h-32 flex-col items-center justify-center rounded-2xl border border-border/50 bg-background/60 px-4 py-6 text-center shadow-sm transition-all hover:border-primary/40 hover:bg-card/80 hover:shadow-lg hover:shadow-primary/10"
                  >
                    <span className="absolute left-3 top-3 rounded-md bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                      {cat.label}
                    </span>
                    <item.icon className="size-8 text-primary transition-transform duration-300 group-hover:scale-110" />
                    <p className="mt-3 text-sm font-medium leading-snug text-foreground">{item.name}</p>
                  </motion.div>
                )),
              )}
            </div>

            <motion.div
              initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="mt-12 overflow-hidden rounded-2xl border border-primary/25 bg-gradient-to-r from-primary/15 via-primary/10 to-intel/10 p-8 text-center md:p-10"
            >
              <Cpu className="mx-auto size-8 text-primary" />
              <h3 className="mt-4 font-display text-xl font-semibold md:text-2xl">
                前端保留工作台体验，后端使用 WorkWings 受控编排
              </h3>
              <p className="mx-auto mt-2 max-w-lg text-sm text-muted-foreground">
                API、CORS、Cookie、SSE、Artifact 存储和模型路由都从服务端统一配置，避免密钥和状态散落到浏览器。
              </p>
            </motion.div>
          </div>
        </section>

        <section id="scenarios" className="relative scroll-mt-20 py-20">
          <div className="mx-auto max-w-6xl px-6">
            <div className="mx-auto max-w-2xl text-center">
              <h2 className="font-display text-3xl font-bold tracking-tight md:text-4xl">
                为可审计的软件交付打造
              </h2>
              <p className="mt-4 text-muted-foreground">
                适合既要大模型效率，也要审批、产物落盘和流程边界的团队。
              </p>
            </div>
            <div className="mt-12 grid gap-5 sm:grid-cols-2">
              {scenarios.map((s, i) => (
                <motion.div
                  key={s.title}
                  initial={{ opacity: 0, scale: prefersReducedMotion ? 1 : 0.96 }}
                  whileInView={{ opacity: 1, scale: 1 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.06 }}
                  whileHover={{ y: prefersReducedMotion ? 0 : -6, scale: prefersReducedMotion ? 1 : 1.015 }}
                  className="group cursor-default rounded-2xl border border-border/50 bg-card/30 p-6 transition-all hover:border-primary/35 hover:bg-card/50 hover:shadow-xl hover:shadow-primary/10"
                >
                  <s.icon className="size-8 text-primary" />
                  <h3 className="mt-3 font-display text-xl font-semibold">{s.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{s.desc}</p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {s.tags.map((t) => (
                      <span
                        key={t}
                        className="rounded-md bg-primary/10 px-2 py-0.5 text-xs text-primary transition group-hover:bg-primary/20"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </section>

        <section className="relative z-10 border-t border-border/40 bg-card/15 py-16">
          <div className="mx-auto max-w-6xl px-6">
            <div className="mx-auto max-w-2xl text-center">
              <h2 className="font-display text-2xl font-bold md:text-3xl">生产级控制边界</h2>
              <p className="mt-3 text-sm text-muted-foreground">
                WorkWings 的编排、权限与存储规则在前端被清晰呈现，不用模拟结果冒充真实执行。
              </p>
            </div>
            <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {securityItems.map((item, i) => (
                <motion.div
                  key={item.title}
                  initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 12 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.05 }}
                  whileHover={{ y: prefersReducedMotion ? 0 : -3 }}
                  className="rounded-xl border border-border/40 bg-background/40 p-5 text-center transition hover:border-primary/30"
                >
                  <item.icon className="mx-auto size-6 text-primary" />
                  <p className="mt-3 font-medium">{item.title}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{item.desc}</p>
                </motion.div>
              ))}
            </div>
          </div>
        </section>

        <section id="steps" className="relative z-10 py-20">
          <div className="mx-auto max-w-6xl px-6">
            <div className="mx-auto max-w-2xl text-center">
              <h2 className="font-display text-3xl font-bold tracking-tight md:text-4xl">
                三步启动交付流
              </h2>
            </div>
            <div className="mt-14 grid gap-8 md:grid-cols-3">
              {steps.map((s, i) => (
                <motion.div
                  key={s.n}
                  initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 16 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.1 }}
                  whileHover={{ y: prefersReducedMotion ? 0 : -4 }}
                  className="rounded-2xl border border-border/40 bg-background/30 p-6 transition hover:border-primary/30"
                >
                  <span className="font-display text-4xl font-bold text-primary/40">{s.n}</span>
                  <h3 className="mt-3 font-display text-xl font-semibold">{s.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{s.desc}</p>
                </motion.div>
              ))}
            </div>
          </div>
        </section>

        <section className="relative z-10 px-6 pb-20">
          <motion.div
            whileHover={{ scale: prefersReducedMotion ? 1 : 1.01 }}
            className="mx-auto max-w-4xl overflow-hidden rounded-3xl border border-primary/25 bg-gradient-to-br from-primary/20 via-card/80 to-intel/15 p-10 text-center md:p-14"
          >
            <h2 className="font-display text-2xl font-bold md:text-3xl">准备好启动 WorkWings 工作台了吗？</h2>
            <p className="mx-auto mt-4 max-w-md text-muted-foreground">
              登录后从项目创建开始，让分析、审批、原型和代码产物都进入同一条可追踪链路。
            </p>
            <motion.div whileHover={{ scale: prefersReducedMotion ? 1 : 1.05 }} whileTap={{ scale: 0.98 }} className="mt-8 inline-block">
              <Button size="lg" className="h-12 rounded-full px-10 text-base shadow-lg shadow-primary/30" asChild>
                <Link to={primaryHref}>
                  {primaryLabel}
                  <ArrowRight className="size-5" />
                </Link>
              </Button>
            </motion.div>
          </motion.div>
        </section>

        <footer className="relative border-t border-border/40 py-8">
          <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-6 text-sm text-muted-foreground md:flex-row">
            <BrandLogo size={36} />
            <div className="flex flex-wrap items-center justify-center gap-6">
              <Link to="/terms" state={{ from: '/' }} className="transition hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background">
                用户协议
              </Link>
              <Link to="/privacy" state={{ from: '/' }} className="transition hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background">
                隐私政策
              </Link>
              <Link to={loggedIn ? '/chat' : '/login'} className="transition hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background">
                {loggedIn ? '工作台' : '登录'}
              </Link>
            </div>
            <p className="text-xs">© {new Date().getFullYear()} WorkWings</p>
          </div>
        </footer>
      </main>
    </div>
  )
}
