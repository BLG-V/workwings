import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Search,
  Play,
  CheckCircle,
  Clock,
  AlertCircle,
  Calendar,
  ChevronRight,
  ChevronDown,
  Server,
  Check,
  X,
  Workflow,
} from 'lucide-react'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/components/ui/select'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { format } from 'date-fns'
import { zhCN } from 'date-fns/locale'
import { toast } from 'sonner'
import { listRuns, type IRun } from '@/lib/runs-store'
import { listProjects, setLastProjectId, resolveWorkflowPath } from '@/lib/projects-store'
import {
  getPlatformRun,
  listModels,
  listPlatformRuns,
  probeMawp,
  resumeRun,
  updateModels,
  type MawpRun,
} from '@/lib/mawp-api'
import { ERROR_CATEGORY_LABEL } from '@/lib/run-labels'
import { deliverProgress, focusCanvasNodeFromRun } from '@/lib/pipeline'
import { mirrorPlatformRunToLocal } from '@/lib/studio-mawp'

const DEMO_SAVE_MODEL = 'deepseek-v4-flash'

const statusConfig = {
  running: {
    label: '运行中',
    icon: Play,
    color: 'text-blue-500',
    bg: 'bg-blue-500/10 border-blue-500/30',
  },
  completed: {
    label: '已完成',
    icon: CheckCircle,
    color: 'text-emerald-600',
    bg: 'bg-emerald-500/10 border-emerald-500/30',
  },
  failed: {
    label: '失败',
    icon: AlertCircle,
    color: 'text-red-500',
    bg: 'bg-red-500/10 border-red-500/30',
  },
  waiting: {
    label: '待审批',
    icon: Clock,
    color: 'text-amber-700',
    bg: 'bg-amber-500/10 border-amber-500/30',
  },
}

function platformErrorCategory(run: MawpRun): string {
  return String(run.observe?.error_category || run.heal?.error_category || '').trim()
}

const NODE_LABELS: Record<string, string> = {
  start: '启动',
  planner: '规划',
  requirement: '需求',
  coding: '编码',
  frontend: '前端',
  testing: '测试',
  debug: '调试',
  review: '审查',
  human_review: '人工审批',
  ship: '交付',
  end: '结束',
}

function formatMs(ms?: number | null) {
  if (ms == null || !Number.isFinite(ms)) return '—'
  if (ms < 1000) return `${Math.round(ms)}ms`
  const s = Math.round(ms / 1000)
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}m ${s % 60}s`
}

function formatTokens(n?: number | null) {
  if (n == null || !Number.isFinite(n) || n <= 0) return '—'
  if (n >= 10_000) return `${Math.round(n / 1000)}k`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}

function formatCny(n?: number | null) {
  if (n == null || !Number.isFinite(n)) return '—'
  if (n === 0) return '¥0'
  if (n < 0.01) return `¥${n.toFixed(4)}`
  return `¥${n.toFixed(2)}`
}

function mapPlatformStatus(status: string): keyof typeof statusConfig {
  const s = status.toUpperCase()
  if (s === 'DONE') return 'completed'
  if (s === 'FAILED' || s === 'CANCELLED') return 'failed'
  if (s === 'WAITING_USER') return 'waiting'
  return 'running'
}

export default function RunsPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const focusRun = searchParams.get('run')
  const [runs, setRuns] = useState<IRun[]>(() => listRuns())
  const [platformRuns, setPlatformRuns] = useState<MawpRun[]>([])
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null)
  const [keyword, setKeyword] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [categoryFilter, setCategoryFilter] = useState('all')
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [actingId, setActingId] = useState<string | null>(null)
  const [savingDemo, setSavingDemo] = useState(false)

  useEffect(() => {
    const refresh = () => setRuns(listRuns())
    refresh()
    window.addEventListener('mawp-runs-change', refresh)
    window.addEventListener('mawp-auth-change', refresh)
    return () => {
      window.removeEventListener('mawp-runs-change', refresh)
      window.removeEventListener('mawp-auth-change', refresh)
    }
  }, [])

  const loadPlatform = async () => {
    const health = await probeMawp()
    setBackendOnline(Boolean(health))
    if (!health) {
      setPlatformRuns([])
      return
    }
    try {
      const { runs: list } = await listPlatformRuns(40)
      setPlatformRuns(list)
      for (const run of list) {
        mirrorPlatformRunToLocal(run)
      }
      setRuns(listRuns())
    } catch {
      setPlatformRuns([])
    }
  }

  useEffect(() => {
    let cancelled = false
    void (async () => {
      await loadPlatform()
      if (cancelled || !focusRun) return
      try {
        const { run } = await getPlatformRun(focusRun)
        if (cancelled || !run?.run_id) return
        setPlatformRuns((prev) => {
          const idx = prev.findIndex((r) => r.run_id === run.run_id)
          if (idx === -1) return [run, ...prev]
          const next = [...prev]
          next[idx] = { ...prev[idx], ...run }
          return next
        })
      } catch {
        /* 列表里可能已有该 run */
      }
    })()
    return () => {
      cancelled = true
    }
  }, [focusRun])

  const hasLiveKernel = platformRuns.some((r) => {
    const s = (r.status || '').toUpperCase()
    return s === 'RUNNING' || s === 'WAITING_USER' || s === 'PENDING'
  })
  const hasLiveLocal = runs.some((r) => r.status === 'running')

  useEffect(() => {
    if (!hasLiveKernel && !hasLiveLocal) return
    const t = window.setInterval(() => {
      setRuns(listRuns())
      void loadPlatform()
    }, 3000)
    return () => window.clearInterval(t)
  }, [hasLiveKernel, hasLiveLocal])

  useEffect(() => {
    if (!focusRun) return
    setStatusFilter('all')
    setCategoryFilter('all')
    setExpandedId(focusRun)
  }, [focusRun])

  useEffect(() => {
    if (!focusRun) return
    const t = window.setTimeout(() => {
      document
        .getElementById(`kernel-run-${focusRun}`)
        ?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }, 80)
    return () => window.clearTimeout(t)
  }, [focusRun, platformRuns])

  const applyDemoSave = async () => {
    setSavingDemo(true)
    try {
      const { current } = await listModels()
      const next = Object.fromEntries(
        Object.keys(current || {}).map((name) => [name, DEMO_SAVE_MODEL]),
      )
      if (!Object.keys(next).length) {
        toast.error('没有可切换的 Agent 模型')
        return
      }
      await updateModels(next)
      toast.success('已切到 Flash，后续 Run 更省（粗估，非账单）')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '切换失败')
    } finally {
      setSavingDemo(false)
    }
  }

  const actOnRun = async (runId: string, action: 'approve' | 'reject') => {
    setActingId(runId)
    try {
      await resumeRun(runId, action)
      toast.success(action === 'approve' ? '已通过，内核继续跑' : '已驳回')
      await loadPlatform()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '操作失败')
    } finally {
      setActingId(null)
    }
  }

  const filtered = useMemo(() => {
    const kernelIds = new Set(platformRuns.map((r) => r.run_id))
    const projects = listProjects()
    return runs.filter((r) => {
      const matchKeyword =
        !keyword ||
        r.projectName.toLowerCase().includes(keyword.toLowerCase())
      const matchStatus = statusFilter === 'all' || r.status === statusFilter
      if (!matchKeyword || !matchStatus) return false
      if (r.id.startsWith('platform:')) {
        const rid = r.id.slice('platform:'.length)
        if (kernelIds.has(rid)) return false
      }
      if (r.status === 'running') {
        const proj =
          projects.find((p) => p.id === r.projectId) ||
          projects.find((p) => p.name === r.projectName)
        if (proj?.kernelRunId && kernelIds.has(proj.kernelRunId)) return false
      }
      return true
    })
  }, [runs, keyword, statusFilter, platformRuns])

  const filteredPlatform = useMemo(() => {
    const q = keyword.trim().toLowerCase()
    return platformRuns.filter((r) => {
      const mapped = mapPlatformStatus(r.status)
      const matchStatus = statusFilter === 'all' || mapped === statusFilter
      if (!matchStatus) return false
      const cat = platformErrorCategory(r)
      if (categoryFilter === '__none__') {
        if (cat) return false
      } else if (categoryFilter !== 'all' && cat !== categoryFilter) {
        return false
      }
      if (!q) return true
      const hay = [
        r.workflow_id,
        r.run_id,
        r.error,
        r.current_node_id,
        cat,
        ERROR_CATEGORY_LABEL[cat],
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
      return hay.includes(q)
    })
  }, [platformRuns, keyword, statusFilter, categoryFilter])

  const openOrchestration = (run?: MawpRun) => {
    const path = resolveWorkflowPath()
    if (!path) {
      toast.error('还没有编排项目，请先到「工作流编排」新建')
      return
    }
    if (!run) {
      navigate(path)
      return
    }
    navigate(path, {
      state: {
        kernelRunId: run.run_id,
        selectAgent: focusCanvasNodeFromRun(run) || undefined,
      },
    })
  }

  const stats = useMemo(() => {
    const source = backendOnline && platformRuns.length ? platformRuns : null
    if (source) {
      const mapped = source.map((r) => mapPlatformStatus(r.status))
      return {
        total: source.length,
        completed: mapped.filter((s) => s === 'completed').length,
        running: mapped.filter((s) => s === 'running').length,
        failed: mapped.filter((s) => s === 'failed').length,
        waiting: mapped.filter((s) => s === 'waiting').length,
      }
    }
    return {
      total: runs.length,
      completed: runs.filter((r) => r.status === 'completed').length,
      running: runs.filter((r) => r.status === 'running').length,
      failed: runs.filter((r) => r.status === 'failed').length,
      waiting: 0,
    }
  }, [runs, platformRuns, backendOnline])

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-display font-bold tracking-tight">运行记录</h1>
          <p className="text-sm text-muted-foreground mt-1">
            内核 Run 的耗时、Token 粗估与自愈；待审批可在此通过或驳回
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {backendOnline ? (
            <Button
              variant="outline"
              size="sm"
              className="h-8"
              disabled={savingDemo}
              onClick={() => void applyDemoSave()}
            >
              演示省钱
            </Button>
          ) : null}
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground">
            <Server className="size-3.5" />
            {backendOnline === null
              ? '检测 WorkWings…'
              : backendOnline
                ? `WorkWings 在线 · 平台 Run ${platformRuns.length}`
                : '内核离线（npm run backend:serve）'}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {(
          [
            { key: 'all', value: stats.total, label: '总运行次数', className: '' },
            {
              key: 'completed',
              value: stats.completed,
              label: '成功完成',
              className: 'text-emerald-600',
            },
            {
              key: 'running',
              value: stats.running,
              label: '运行中',
              className: 'text-blue-500',
            },
            {
              key: 'failed',
              value: stats.failed,
              label: '失败',
              className: 'text-red-500',
            },
            {
              key: 'waiting',
              value: stats.waiting,
              label: '待审批',
              className: 'text-amber-700',
            },
          ] as const
        ).map((item) => (
          <Card
            key={item.key}
            className={`cursor-pointer transition-colors ${
              statusFilter === item.key ? 'border-primary' : 'hover:border-primary/40'
            }`}
            onClick={() => setStatusFilter(item.key)}
          >
            <CardContent className="p-4">
              <div className={`text-2xl font-bold ${item.className}`}>{item.value}</div>
              <div className="text-xs text-muted-foreground mt-1">{item.label}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1 max-w-md">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="搜索项目、Run ID、失败分类"
            className="pl-9"
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="状态筛选" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部状态</SelectItem>
            <SelectItem value="running">运行中</SelectItem>
            <SelectItem value="completed">已完成</SelectItem>
            <SelectItem value="failed">失败</SelectItem>
            <SelectItem value="waiting">待审批</SelectItem>
          </SelectContent>
        </Select>
        <Select value={categoryFilter} onValueChange={setCategoryFilter}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="失败分类" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部分类</SelectItem>
            <SelectItem value="__none__">未分类</SelectItem>
            {Object.entries(ERROR_CATEGORY_LABEL).map(([value, label]) => (
              <SelectItem key={value} value={value}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          variant="outline"
          size="sm"
          className="h-9"
          onClick={() => openOrchestration()}
        >
          <Workflow className="size-3.5 mr-1.5" />
          打开编排
        </Button>
      </div>

      {filtered.length > 0 ? (
      <div className="space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground">本机模拟记录</h2>
        {filtered.map((run) => {
          const sc = statusConfig[run.status]
          const StatusIcon = sc.icon
          const progress =
            run.status === 'completed'
              ? 100
              : run.nodesTotal > 0
                ? Math.round(
                    ((run.nodesCompleted +
                      (run.status === 'running' && run.nodesCompleted < run.nodesTotal
                        ? 0.5
                        : 0)) /
                      run.nodesTotal) *
                      100,
                  )
                : run.status === 'running'
                  ? 6
                  : 0
          return (
            <Card
              key={run.id}
              className="cursor-pointer hover:border-primary/50 transition-colors pressable"
              onClick={() => {
                setLastProjectId(run.projectId)
                toast.info(`打开「${run.projectName}」`)
                navigate(`/workflow/${run.projectId}`)
              }}
            >
              <CardContent className="p-4">
                <div className="flex items-center gap-4">
                  <div
                    className={`size-10 rounded-lg flex items-center justify-center shrink-0 ${sc.bg} border`}
                  >
                    <StatusIcon className={`size-5 ${sc.color}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="font-medium text-sm truncate">
                        {run.projectName}
                      </h3>
                      <Badge
                        variant="outline"
                        className={`text-[10px] ${sc.bg} ${sc.color} border`}
                      >
                        {sc.label}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-4 mt-1 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Calendar className="size-3" />
                        {format(new Date(run.startTime), 'yyyy-MM-dd HH:mm', {
                          locale: zhCN,
                        })}
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock className="size-3" />
                        {run.duration}
                      </span>
                      <span>
                        节点: {run.nodesCompleted}/{run.nodesTotal}
                      </span>
                      <span>日志: {run.logsCount}条</span>
                    </div>
                    <div className="mt-2">
                      <Progress value={progress} className="h-1" />
                    </div>
                  </div>
                  <ChevronRight className="size-4 text-muted-foreground shrink-0" />
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>
      ) : null}

      {backendOnline && platformRuns.length > 0 ? (
        <div className="space-y-3">
          <h2 className="text-sm font-medium">
            内核观测
            <span className="ml-2 font-normal text-muted-foreground">
              {filteredPlatform.length}/{platformRuns.length}
            </span>
          </h2>
          {filteredPlatform.length === 0 ? (
            <div className="rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground">
              没有符合筛选的内核 Run。可把状态改成「全部状态」，或把失败分类改成「全部分类」。
            </div>
          ) : null}
          {filteredPlatform.map((run) => {
            const mapped = mapPlatformStatus(run.status)
            const sc = statusConfig[mapped]
            const StatusIcon = sc.icon
            const obs = run.observe
            const open = expandedId === run.run_id
            const waiting = mapped === 'waiting'
            const cat = obs?.error_category || run.heal?.error_category
            const progress = deliverProgress(run)
            return (
              <Card
                key={run.run_id}
                id={`kernel-run-${run.run_id}`}
                className={
                  focusRun === run.run_id
                    ? 'border-primary ring-1 ring-primary/40'
                    : undefined
                }
              >
                <CardContent className="p-4">
                  <div className="flex items-start gap-4">
                    <div
                      className={`size-10 rounded-lg flex items-center justify-center shrink-0 ${sc.bg} border`}
                    >
                      <StatusIcon className={`size-5 ${sc.color}`} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="font-medium text-sm truncate">
                          {run.workflow_id || run.run_id}
                        </h3>
                        <Badge
                          variant="outline"
                          className={`text-[10px] ${sc.bg} ${sc.color} border`}
                        >
                          {sc.label}
                        </Badge>
                        {(obs?.heal_attempts || run.heal?.round) ? (
                          <Badge
                            variant="outline"
                            className="text-[10px] border-amber-500/40 bg-amber-500/10 text-amber-700"
                          >
                            自愈 {obs?.heal_attempts ?? run.heal?.round}/
                            {run.heal?.max_rounds || 3}
                            {obs?.node_retries
                              ? ` · 重试 ${obs.node_retries}`
                              : ''}
                          </Badge>
                        ) : null}
                        {cat ? (
                          <Badge variant="outline" className="text-[10px]">
                            {ERROR_CATEGORY_LABEL[cat] || cat}
                          </Badge>
                        ) : null}
                      </div>
                      <div className="mt-1 flex flex-wrap gap-3 text-[11px] text-muted-foreground">
                        <span className="font-mono">{run.run_id}</span>
                        <span className="flex items-center gap-1">
                          <Clock className="size-3" />
                          {formatMs(obs?.duration_ms)}
                        </span>
                        {obs?.usage?.total_tokens ? (
                          <span>
                            {formatTokens(obs.usage.total_tokens)} tok ·{' '}
                            {formatCny(obs.usage.cost_cny)}
                          </span>
                        ) : null}
                        <span>
                          节点: {progress.completed}/{progress.total}
                          {run.current_node_id
                            ? ` · ${NODE_LABELS[run.current_node_id] || run.current_node_id}`
                            : ''}
                        </span>
                        {run.error ? (
                          <span className="text-red-500 truncate max-w-[280px]">
                            {run.error}
                          </span>
                        ) : null}
                      </div>
                      <div className="mt-2">
                        <Progress value={progress.percent} className="h-1" />
                      </div>
                      {waiting ? (
                        <div className="mt-2 flex gap-2">
                          <Button
                            size="sm"
                            className="h-7"
                            disabled={actingId === run.run_id}
                            onClick={() => void actOnRun(run.run_id, 'approve')}
                          >
                            <Check className="size-3.5 mr-1" />
                            通过
                          </Button>
                          <Button
                            size="sm"
                            variant="secondary"
                            className="h-7"
                            disabled={actingId === run.run_id}
                            onClick={() => void actOnRun(run.run_id, 'reject')}
                          >
                            <X className="size-3.5 mr-1" />
                            驳回
                          </Button>
                        </div>
                      ) : null}
                      {open && (obs?.nodes?.length || obs?.usage?.by_agent?.length) ? (
                        <div className="mt-3 space-y-1.5 text-[11px]">
                          {obs?.nodes?.map((n) => (
                            <div
                              key={n.node_id}
                              className="flex items-center justify-between gap-2 text-muted-foreground"
                            >
                              <span>
                                {NODE_LABELS[n.node_id] || n.node_id}
                                {n.retries ? ` · 重试${n.retries}` : ''}
                              </span>
                              <span className="tabular-nums">
                                {n.status || '—'} · {formatMs(n.duration_ms)}
                                {n.total_tokens
                                  ? ` · ${formatTokens(n.total_tokens)} tok`
                                  : ''}
                              </span>
                            </div>
                          ))}
                          {obs?.usage?.by_agent?.length ? (
                            <div className="pt-1 text-muted-foreground/80">
                              {obs.usage.by_agent.map((a) => (
                                <div
                                  key={a.agent}
                                  className="flex justify-between gap-2"
                                >
                                  <span>
                                    {NODE_LABELS[a.agent] || a.agent}
                                    {a.models?.[0] ? ` · ${a.models[0]}` : ''}
                                  </span>
                                  <span className="tabular-nums">
                                    {formatTokens(a.total_tokens)} · {formatCny(a.cost_cny)}
                                  </span>
                                </div>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 px-2 text-[11px]"
                        onClick={() => openOrchestration(run)}
                        title="回到编排并定位失败/当前节点"
                      >
                        <Workflow className="size-3.5 mr-1" />
                        定位节点
                      </Button>
                      <button
                        type="button"
                        className="text-muted-foreground p-1"
                        onClick={() =>
                          setExpandedId((id) => (id === run.run_id ? null : run.run_id))
                        }
                        title="节点耗时"
                      >
                        {open ? (
                          <ChevronDown className="size-4" />
                        ) : (
                          <ChevronRight className="size-4" />
                        )}
                      </button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      ) : null}
    </div>
  )
}
