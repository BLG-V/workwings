import { useEffect, useRef, useState } from 'react'
import {
  Activity,
  CheckCircle2,
  XCircle,
  Loader2,
  RotateCcw,
  Clock,
  X,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { toast } from 'sonner'
import { streamRunEvents, retryRun, fetchStudioStages, type SSEEvent } from '@/lib/mawp-api'

interface RunMonitorProps {
  runId: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

interface NodeState {
  nodeId: string
  status: 'pending' | 'running' | 'ok' | 'failed' | 'retry'
  startTime?: number
  endTime?: number
  durationMs?: number
  attempt?: number
  maxRetries?: number
  error?: string
  agent?: string
}

const NODE_ORDER = ['start', 'planner', 'coding', 'frontend', 'testing', 'debug', 'review', 'ship', 'end']

const NODE_LABELS: Record<string, string> = {
  start: '启动',
  planner: '规划器',
  coding: '代码生成',
  frontend: '前端生成',
  testing: '测试验证',
  debug: '调试修复',
  review: '代码审查',
  ship: '交付部署',
  end: '完成',
}

export default function RunMonitor({ runId, open, onOpenChange }: RunMonitorProps) {
  const [nodes, setNodes] = useState<Record<string, NodeState>>({})
  const [events, setEvents] = useState<SSEEvent[]>([])
  const [runStatus, setRunStatus] = useState<string>('')
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [retrying, setRetrying] = useState(false)
  const [healRound, setHealRound] = useState<number>(0)
  const [healMax, setHealMax] = useState<number>(3)
  const cleanupRef = useRef<(() => void) | null>(null)

  useEffect(() => {
    if (!open || !runId) {
      cleanupRef.current?.()
      cleanupRef.current = null
      return
    }

    setHealRound(0)
    setHealMax(3)

    // 初始拉一次状态
    fetchStudioStages(runId).then((data) => {
      setRunStatus(data.run.status)
      const completed = Object.keys(data.run.node_outputs || {}).length
      setProgress(Math.min(95, Math.round((completed / 8) * 100)))
      const heal = data.run.heal
      if (heal?.round) {
        setHealRound(Number(heal.round) || 0)
        setHealMax(Number(heal.max_rounds) || 3)
      }
    }).catch(() => {})

    // 启动 SSE
    const cleanup = streamRunEvents(
      runId,
      // onEvent
      (evt) => {
        setEvents((prev) => [...prev.slice(-80), evt])

        if (evt.type === 'heal_attempt' || evt.type === 'heal_handoff') {
          if (typeof evt.round === 'number') setHealRound(evt.round)
          if (typeof evt.max_rounds === 'number') setHealMax(evt.max_rounds)
        }

        const nodeId = evt.node_id || evt.from || ''
        if (!nodeId) return

        setNodes((prev) => {
          const existing = prev[nodeId] || { nodeId, status: 'pending' as const }
          if (evt.type === 'node_start') {
            return { ...prev, [nodeId]: { ...existing, status: 'running', startTime: Date.now(), agent: evt.agent } }
          }
          if (evt.type === 'node_end') {
            const durationMs = existing.startTime ? Date.now() - existing.startTime : undefined
            return {
              ...prev,
              [nodeId]: {
                ...existing,
                status: evt.status === 'ok' ? 'ok' : 'failed',
                endTime: Date.now(),
                durationMs,
              },
            }
          }
          if (evt.type === 'node_retry' || evt.type === 'heal_attempt') {
            return {
              ...prev,
              [nodeId]: {
                ...existing,
                status: 'retry',
                attempt: evt.round ?? evt.attempt,
                maxRetries: evt.max_rounds ?? evt.max_retries,
                error: evt.reason || evt.error,
              },
            }
          }
          return prev
        })
      },
      // onStatus
      (status) => {
        setRunStatus(status.status || '')
        const completed = status.completed_nodes || 0
        const total = status.total_nodes || 8
        setProgress(Math.min(95, Math.round((completed / total) * 100)))
        if (status.error) setError(status.error)
      },
      // onDone
      (finalStatus) => {
        setRunStatus(finalStatus)
        setProgress(100)
      },
      // onError
      (err) => {
        setError(err)
      },
    )
    cleanupRef.current = cleanup

    return () => {
      cleanup()
      cleanupRef.current = null
    }
  }, [open, runId])

  const handleRetry = async () => {
    if (!runId) return
    setRetrying(true)
    try {
      const result = await retryRun(runId)
      setRunStatus(result.run.status)
      setNodes({})
      setEvents([])
      setError(null)
      setProgress(0)
      setHealRound(0)
      toast.success('已重新触发运行')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '重试失败')
    } finally {
      setRetrying(false)
    }
  }

  const isTerminal = ['DONE', 'FAILED', 'CANCELLED'].includes((runStatus || '').toUpperCase())
  const isFailed = (runStatus || '').toUpperCase() === 'FAILED'

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[85vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="font-display flex items-center gap-2">
            <Activity className="size-4 text-primary" />
            运行监控
            {runId && (
              <Badge variant="secondary" className="ml-2 font-mono text-[10px]">
                {runId.slice(0, 16)}…
              </Badge>
            )}
          </DialogTitle>
          <DialogDescription>
            实时监控工作流执行状态
          </DialogDescription>
        </DialogHeader>

        {/* 顶部状态栏 */}
        <div className="flex items-center gap-3 rounded-xl border border-border/80 bg-muted/30 px-4 py-2.5">
          <div className="flex items-center gap-2">
            {isTerminal ? (
              isFailed ? (
                <XCircle className="size-4 text-red-500" />
              ) : (
                <CheckCircle2 className="size-4 text-emerald-500" />
              )
            ) : (
              <Loader2 className="size-4 animate-spin text-primary" />
            )}
            <span className="text-sm font-medium">{runStatus || '等待中'}</span>
            {healRound > 0 && (
              <Badge variant="outline" className="border-amber-500/40 bg-amber-500/10 text-[10px] text-amber-700">
                自愈 {healRound}/{healMax}
              </Badge>
            )}
          </div>
          <div className="flex-1">
            <Progress value={progress} className="h-1.5" />
          </div>
          <span className="text-xs tabular-nums text-muted-foreground">{progress}%</span>
          {isFailed && (
            <Button
              size="sm"
              variant="secondary"
              className="h-7 gap-1.5 text-xs"
              disabled={retrying}
              onClick={() => void handleRetry()}
            >
              {retrying ? (
                <Loader2 className="size-3 animate-spin" />
              ) : (
                <RotateCcw className="size-3" />
              )}
              重试
            </Button>
          )}
        </div>

        {/* 节点状态网格 */}
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
          {NODE_ORDER.map((nodeId) => {
            const node = nodes[nodeId]
            const label = NODE_LABELS[nodeId] || nodeId
            return (
              <div
                key={nodeId}
                className={cn(
                  'rounded-lg border px-2.5 py-2 text-center transition-colors',
                  !node && 'border-border/40 bg-muted/20 opacity-50',
                  node?.status === 'running' && 'border-primary/40 bg-primary/5',
                  node?.status === 'ok' && 'border-emerald-500/30 bg-emerald-500/5',
                  node?.status === 'failed' && 'border-red-500/30 bg-red-500/5',
                  node?.status === 'retry' && 'border-amber-500/30 bg-amber-500/5',
                )}
              >
                <div className="flex items-center justify-center gap-1">
                  {!node || node.status === 'pending' ? (
                    <span className="size-2 rounded-full bg-muted-foreground/30" />
                  ) : node.status === 'running' ? (
                    <Loader2 className="size-3 animate-spin text-primary" />
                  ) : node.status === 'ok' ? (
                    <CheckCircle2 className="size-3 text-emerald-500" />
                  ) : node.status === 'failed' ? (
                    <XCircle className="size-3 text-red-500" />
                  ) : (
                    <RotateCcw className="size-3 text-amber-500" />
                  )}
                  <span className="text-[11px] font-medium">{label}</span>
                </div>
                {node?.durationMs != null && (
                  <div className="text-[9px] text-muted-foreground mt-0.5 flex items-center justify-center gap-0.5">
                    <Clock className="size-2.5" />
                    {node.durationMs < 1000
                      ? `${node.durationMs}ms`
                      : `${(node.durationMs / 1000).toFixed(1)}s`}
                  </div>
                )}
                {node?.status === 'retry' && node.attempt != null && (
                  <div className="text-[9px] text-amber-600 mt-0.5">
                    重试 {node.attempt}/{node.maxRetries || 3}
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* 错误信息 */}
        {error && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/5 px-3 py-2">
            <div className="text-[11px] font-medium text-red-700 mb-1">错误信息</div>
            <p className="text-[11px] text-red-600/80 font-mono break-all">{error.slice(0, 500)}</p>
          </div>
        )}

        {/* 事件流 */}
        <div className="flex-1 overflow-y-auto rounded-xl border border-border/60 bg-muted/20 p-2 max-h-[200px]">
          <div className="text-[10px] text-muted-foreground mb-1.5 px-1">事件流</div>
          {events.length === 0 ? (
            <p className="text-[11px] text-muted-foreground px-2 py-3 text-center">
              等待事件…
            </p>
          ) : (
            <div className="space-y-0.5 font-mono text-[10px]">
              {events.slice(-40).map((evt, idx) => (
                <div key={idx} className="flex items-start gap-2 px-1 py-0.5 rounded hover:bg-muted/40">
                  <span className="text-muted-foreground shrink-0">
                    {evt.ts ? new Date(evt.ts).toLocaleTimeString('zh-CN', { hour12: false }) : ''}
                  </span>
                  <span
                    className={cn(
                      'shrink-0',
                      evt.type === 'node_end' && evt.status === 'ok' && 'text-emerald-600',
                      evt.type === 'node_end' && evt.status === 'failed' && 'text-red-600',
                      evt.type === 'node_retry' && 'text-amber-600',
                      evt.type === 'heal_attempt' && 'text-amber-600',
                      evt.type === 'heal_handoff' && 'text-orange-700',
                      evt.type === 'node_start' && 'text-primary',
                      !evt.type && 'text-muted-foreground',
                    )}
                  >
                    {evt.type || 'event'}
                  </span>
                  <span className="text-foreground/70 truncate">
                    {evt.node_id || ''}
                    {evt.agent ? ` (${evt.agent})` : ''}
                    {evt.status ? ` ${evt.status}` : ''}
                    {evt.reason ? ` ${evt.reason}` : ''}
                    {evt.from && evt.to ? ` ${evt.from}→${evt.to}` : ''}
                    {evt.round != null && evt.max_rounds != null ? ` ${evt.round}/${evt.max_rounds}` : ''}
                    {evt.selected_model ? ` [${evt.selected_model}]` : ''}
                    {evt.error ? ` ${evt.error.slice(0, 80)}` : ''}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
