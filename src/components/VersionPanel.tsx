import { useEffect, useState } from 'react'
import {
  History,
  Loader2,
  CheckCircle2,
  XCircle,
  RotateCcw,
  GitCompare,
  Clock,
  FileText,
  AlertTriangle,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { toast } from 'sonner'
import {
  listProjectVersions,
  rollbackProjectVersion,
  diffProjectVersions,
} from '@/lib/mawp-api'

type VersionEntry = {
  version_id: string
  version_num: number
  run_id: string
  goal: string
  created_at: string
  file_count: number
  testing_passed: boolean
  diff_count?: number
}

interface DiffResult {
  added: string[]
  removed: string[]
  modified: string[]
  unchanged_count: number
  summary: {
    added: number
    removed: number
    modified: number
    unchanged: number
    total_changed: number
    total: number
  }
}

export default function VersionPanel({
  projectRoot,
  onClose,
}: {
  projectRoot: string
  onClose: () => void
}) {
  const [loading, setLoading] = useState(true)
  const [versions, setVersions] = useState<VersionEntry[]>([])
  const [latest, setLatest] = useState<string | null>(null)
  const [rollbackTarget, setRollbackTarget] = useState<string | null>(null)
  const [rolling, setRolling] = useState(false)
  const [diffA, setDiffA] = useState<string | null>(null)
  const [diffB, setDiffB] = useState<string | null>(null)
  const [diffResult, setDiffResult] = useState<DiffResult | null>(null)
  const [diffing, setDiffing] = useState(false)

  const fetchVersions = async () => {
    setLoading(true)
    try {
      const data = await listProjectVersions(projectRoot)
      setVersions(data.versions || [])
      setLatest(data.latest)
    } catch {
      // 离线忽略
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void fetchVersions()
  }, [projectRoot])

  const handleRollback = async () => {
    if (!rollbackTarget) return
    setRolling(true)
    try {
      const result = await rollbackProjectVersion(projectRoot, rollbackTarget)
      toast.success(result.message || `已回滚到 ${rollbackTarget}`)
      setRollbackTarget(null)
      await fetchVersions()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '回滚失败')
    } finally {
      setRolling(false)
    }
  }

  const handleDiff = async () => {
    if (!diffA || !diffB || diffA === diffB) {
      toast.message('请选择两个不同的版本')
      return
    }
    setDiffing(true)
    try {
      const result = await diffProjectVersions(projectRoot, diffA, diffB)
      setDiffResult(result.diff)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '对比失败')
    } finally {
      setDiffing(false)
    }
  }

  const formatTime = (iso: string) => {
    try {
      const d = new Date(iso)
      return d.toLocaleString('zh-CN', { hour12: false })
    } catch {
      return iso
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="h-[85vh] w-full max-w-4xl rounded-2xl border border-border bg-card shadow-xl flex flex-col overflow-hidden">
        {/* 头部 */}
        <div className="flex items-center justify-between border-b border-border/60 px-5 py-3">
          <div className="flex items-center gap-2">
            <History className="size-4 text-primary" />
            <span className="text-sm font-medium">版本管理</span>
            {latest && (
              <Badge variant="secondary" className="text-[10px]">
                最新：{latest}
              </Badge>
            )}
          </div>
          <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={onClose}>
            关闭
          </Button>
        </div>

        {loading ? (
          <div className="flex flex-1 items-center justify-center">
            <Loader2 className="size-6 animate-spin text-primary" />
          </div>
        ) : versions.length === 0 ? (
          <div className="flex flex-1 items-center justify-center text-muted-foreground">
            <div className="text-center">
              <History className="size-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">暂无版本快照</p>
              <p className="text-xs mt-1">运行 Deliver 后会自动创建版本</p>
            </div>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* Diff 对比区 */}
            <div className="rounded-xl border border-border/80 bg-muted/20 p-3 space-y-2">
              <div className="flex items-center gap-2 text-xs font-medium">
                <GitCompare className="size-3.5 text-primary" />
                版本对比
              </div>
              <div className="flex items-center gap-2">
                <select
                  value={diffA || ''}
                  onChange={(e) => setDiffA(e.target.value)}
                  className="flex-1 rounded-lg border border-border bg-background px-2 py-1 text-xs"
                >
                  <option value="">版本 A</option>
                  {versions.map((v) => (
                    <option key={v.version_id} value={v.version_id}>
                      {v.version_id} · {formatTime(v.created_at)}
                    </option>
                  ))}
                </select>
                <span className="text-xs text-muted-foreground">vs</span>
                <select
                  value={diffB || ''}
                  onChange={(e) => setDiffB(e.target.value)}
                  className="flex-1 rounded-lg border border-border bg-background px-2 py-1 text-xs"
                >
                  <option value="">版本 B</option>
                  {versions.map((v) => (
                    <option key={v.version_id} value={v.version_id}>
                      {v.version_id} · {formatTime(v.created_at)}
                    </option>
                  ))}
                </select>
                <Button
                  size="sm"
                  variant="secondary"
                  className="h-7 text-xs"
                  disabled={!diffA || !diffB || diffA === diffB || diffing}
                  onClick={() => void handleDiff()}
                >
                  {diffing ? <Loader2 className="size-3 animate-spin" /> : '对比'}
                </Button>
              </div>

              {diffResult && (
                <div className="rounded-lg border border-border/60 bg-background/60 p-2.5 space-y-1.5">
                  <div className="flex items-center gap-3 text-[11px]">
                    <span className="text-emerald-600">+{diffResult.summary.added} 新增</span>
                    <span className="text-red-600">-{diffResult.summary.removed} 删除</span>
                    <span className="text-amber-600">~{diffResult.summary.modified} 修改</span>
                    <span className="text-muted-foreground">{diffResult.summary.unchanged} 不变</span>
                  </div>
                  {diffResult.added.length > 0 && (
                    <div>
                      <div className="text-[10px] text-emerald-700 font-medium mb-0.5">新增文件</div>
                      {diffResult.added.slice(0, 8).map((f) => (
                        <div key={f} className="text-[10px] text-emerald-600/80 font-mono pl-2">+ {f}</div>
                      ))}
                    </div>
                  )}
                  {diffResult.removed.length > 0 && (
                    <div>
                      <div className="text-[10px] text-red-700 font-medium mb-0.5">删除文件</div>
                      {diffResult.removed.slice(0, 8).map((f) => (
                        <div key={f} className="text-[10px] text-red-600/80 font-mono pl-2">- {f}</div>
                      ))}
                    </div>
                  )}
                  {diffResult.modified.length > 0 && (
                    <div>
                      <div className="text-[10px] text-amber-700 font-medium mb-0.5">修改文件</div>
                      {diffResult.modified.slice(0, 8).map((f) => (
                        <div key={f} className="text-[10px] text-amber-600/80 font-mono pl-2">~ {f}</div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* 版本列表 */}
            <div className="space-y-2">
              {[...versions].reverse().map((v) => (
                <div
                  key={v.version_id}
                  className={cn(
                    'rounded-xl border px-3 py-2.5 transition-colors',
                    v.version_id === latest
                      ? 'border-primary/30 bg-primary/5'
                      : 'border-border/60 bg-muted/20',
                    rollbackTarget === v.version_id && 'ring-2 ring-amber-400/50',
                  )}
                >
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2 shrink-0">
                      {v.testing_passed ? (
                        <CheckCircle2 className="size-4 text-emerald-500" />
                      ) : (
                        <XCircle className="size-4 text-red-500" />
                      )}
                      <span className="text-sm font-medium font-mono">{v.version_id}</span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-xs text-muted-foreground truncate">
                        {v.goal || '—'}
                      </div>
                      <div className="flex items-center gap-3 text-[10px] text-muted-foreground mt-0.5">
                        <span className="flex items-center gap-0.5">
                          <Clock className="size-2.5" />
                          {formatTime(v.created_at)}
                        </span>
                        <span className="flex items-center gap-0.5">
                          <FileText className="size-2.5" />
                          {v.file_count} 文件
                        </span>
                        {v.diff_count != null && v.diff_count > 0 && (
                          <span className="flex items-center gap-0.5 text-amber-600">
                            <AlertTriangle className="size-2.5" />
                            {v.diff_count} 处变更
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      {v.version_id !== latest && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 px-2 text-[11px] text-amber-600 hover:text-amber-700"
                          onClick={() => setRollbackTarget(v.version_id)}
                        >
                          <RotateCcw className="size-3 mr-1" />
                          回滚
                        </Button>
                      )}
                      {v.version_id === latest && (
                        <Badge variant="secondary" className="text-[9px]">当前</Badge>
                      )}
                    </div>
                  </div>

                  {/* 回滚确认 */}
                  {rollbackTarget === v.version_id && (
                    <div className="mt-2 rounded-lg border border-amber-400/40 bg-amber-50/70 px-3 py-2 flex items-center justify-between gap-2">
                      <span className="text-[11px] text-amber-800">
                        确认回滚到 {v.version_id}？当前状态将自动备份为新版本。
                      </span>
                      <div className="flex gap-1.5">
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-6 text-[10px]"
                          onClick={() => setRollbackTarget(null)}
                        >
                          取消
                        </Button>
                        <Button
                          size="sm"
                          className="h-6 text-[10px] bg-amber-600 hover:bg-amber-700"
                          disabled={rolling}
                          onClick={() => void handleRollback()}
                        >
                          {rolling ? <Loader2 className="size-3 animate-spin" /> : '确认回滚'}
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
