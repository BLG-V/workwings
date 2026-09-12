import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, Clock3, History, RotateCcw, GitCompareArrows, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import { toast } from 'sonner'
import {
  listProjectVersions,
  getProjectVersionDetail,
  rollbackProjectVersion,
  diffProjectVersions,
} from '@/lib/mawp-api'

interface VersionManagerProps {
  projectRoot: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

interface VersionItem {
  snapshot_id: string
  path?: string
  label?: string
  created_at?: string
  file_count?: number
  run_id?: string
  status?: string
  note?: string
}

export default function VersionManager({ projectRoot, open, onOpenChange }: VersionManagerProps) {
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [versions, setVersions] = useState<VersionItem[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [selectedDetail, setSelectedDetail] = useState<any>(null)
  const [compareWith, setCompareWith] = useState<string | null>(null)
  const [diffText, setDiffText] = useState('')
  const [diffSummary, setDiffSummary] = useState<{ added: number; removed: number; changed: number } | null>(null)
  const [showDiff, setShowDiff] = useState(false)

  const loadVersions = async () => {
    if (!projectRoot) return
    setLoading(true)
    try {
      const data = await listProjectVersions(projectRoot)
      setVersions(data.versions || [])
      setSelected((prev) => prev || data.versions?.[0]?.snapshot_id || null)
      if (data.versions?.[0]?.snapshot_id) {
        const detail = await getProjectVersionDetail(projectRoot, data.versions[0].snapshot_id)
        setSelectedDetail(detail)
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '加载版本失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (open && projectRoot) {
      void loadVersions()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, projectRoot])

  const selectedVersion = useMemo(
    () => versions.find((v) => v.snapshot_id === selected) || null,
    [versions, selected],
  )

  const handleSelect = async (versionId: string) => {
    setSelected(versionId)
    if (!projectRoot) return
    try {
      const detail = await getProjectVersionDetail(projectRoot, versionId)
      setSelectedDetail(detail)
      setCompareWith(null)
      setDiffText('')
      setDiffSummary(null)
      setShowDiff(false)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '加载版本详情失败')
    }
  }

  const handleRollback = async (versionId: string) => {
    if (!projectRoot) return
    setSaving(true)
    try {
      await rollbackProjectVersion(projectRoot, versionId)
      toast.success('已回滚到所选版本')
      await loadVersions()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '回滚失败')
    } finally {
      setSaving(false)
    }
  }

  const handleCompare = async () => {
    if (!projectRoot || !selected || !compareWith) return
    setSaving(true)
    try {
      const data = await diffProjectVersions(projectRoot, selected, compareWith)
      setDiffText(JSON.stringify(data, null, 2))
      setDiffSummary(data.summary || null)
      setShowDiff(true)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '对比失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl max-h-[88vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="font-display flex items-center gap-2">
            <History className="size-4 text-primary" />
            版本历史管理
            {projectRoot && (
              <Badge variant="secondary" className="font-mono text-[10px]">
                {projectRoot}
              </Badge>
            )}
          </DialogTitle>
          <DialogDescription>
            查看历史快照、对比版本差异，并一键回滚到稳定版本。
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[320px,1fr] flex-1 min-h-0">
          {/* 左侧版本列表 */}
          <div className="rounded-xl border border-border/70 bg-muted/20 flex flex-col min-h-0">
            <div className="flex items-center justify-between px-3 py-2 border-b border-border/60">
              <span className="text-xs font-medium">版本列表</span>
              {loading ? <Loader2 className="size-3.5 animate-spin text-primary" /> : null}
            </div>
            <ScrollArea className="flex-1">
              <div className="p-2 space-y-1.5">
                {versions.length === 0 ? (
                  <div className="px-2 py-6 text-center text-xs text-muted-foreground">
                    暂无版本快照
                  </div>
                ) : (
                  versions.map((v) => {
                    const active = selected === v.snapshot_id
                    return (
                      <button
                        key={v.snapshot_id}
                        type="button"
                        onClick={() => void handleSelect(v.snapshot_id)}
                        className={cn(
                          'w-full text-left rounded-lg border px-3 py-2 transition-colors',
                          active
                            ? 'border-primary bg-primary/5'
                            : 'border-border/60 bg-background hover:bg-muted/40',
                        )}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs font-medium truncate">
                            {v.label || v.snapshot_id}
                          </span>
                          <Badge variant="secondary" className="text-[9px]">
                            {v.file_count || 0} files
                          </Badge>
                        </div>
                        <div className="mt-1 flex items-center gap-2 text-[10px] text-muted-foreground">
                          <Clock3 className="size-3" />
                          <span>{v.created_at || '未知时间'}</span>
                        </div>
                        <div className="mt-1 text-[10px] text-muted-foreground font-mono break-all">
                          {v.snapshot_id}
                        </div>
                      </button>
                    )
                  })
                )}
              </div>
            </ScrollArea>
          </div>

          {/* 右侧详情 */}
          <div className="rounded-xl border border-border/70 bg-background flex flex-col min-h-0">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border/60">
              <div>
                <div className="text-sm font-medium">
                  {selectedVersion?.label || selectedVersion?.snapshot_id || '版本详情'}
                </div>
                <div className="text-[11px] text-muted-foreground mt-0.5">
                  {selectedDetail?.manifest?.note || selectedVersion?.note || '无说明'}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  className="h-8 gap-1.5 text-xs"
                  disabled={!selected || saving}
                  onClick={() => void handleRollback(selected!)}
                >
                  <RotateCcw className="size-3.5" />
                  回滚到此版本
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 p-4 lg:grid-cols-2 min-h-0 flex-1">
              <div className="rounded-lg border border-border/60 bg-muted/10 p-3 min-h-0 flex flex-col">
                <div className="text-xs font-medium mb-2">版本信息</div>
                <div className="space-y-2 text-[11px] text-muted-foreground">
                  <div><span className="text-foreground">Run：</span>{selectedVersion?.run_id || '—'}</div>
                  <div><span className="text-foreground">文件数：</span>{selectedVersion?.file_count || 0}</div>
                  <div><span className="text-foreground">时间：</span>{selectedVersion?.created_at || '—'}</div>
                  <div><span className="text-foreground">状态：</span>{selectedVersion?.status || '—'}</div>
                  <div><span className="text-foreground">版本 ID：</span><span className="font-mono">{selectedVersion?.snapshot_id || '—'}</span></div>
                </div>
                <Separator className="my-3" />
                <div className="text-xs font-medium mb-2">版本文件</div>
                <div className="flex-1 overflow-y-auto rounded-md border border-border/60 bg-background/70 p-2 text-[11px] font-mono">
                  {selectedDetail?.manifest?.files?.length ? (
                    <div className="space-y-0.5">
                      {selectedDetail.manifest.files.slice(0, 120).map((file: string) => (
                        <div key={file} className="truncate">{file}</div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-muted-foreground">暂无文件清单</div>
                  )}
                </div>
              </div>

              <div className="rounded-lg border border-border/60 bg-muted/10 p-3 min-h-0 flex flex-col">
                <div className="flex items-center justify-between gap-2 mb-2">
                  <div className="text-xs font-medium">版本对比</div>
                  <div className="flex items-center gap-2">
                    <select
                      value={compareWith || ''}
                      onChange={(e) => setCompareWith(e.target.value || null)}
                      className="rounded-md border border-border bg-background px-2 py-1 text-[11px]"
                    >
                      <option value="">选择对比版本</option>
                      {versions.filter((v) => v.snapshot_id !== selected).map((v) => (
                        <option key={v.snapshot_id} value={v.snapshot_id}>
                          {v.label || v.snapshot_id}
                        </option>
                      ))}
                    </select>
                    <Button
                      size="sm"
                      variant="secondary"
                      className="h-7 gap-1.5 text-xs"
                      disabled={!selected || !compareWith || saving}
                      onClick={() => void handleCompare()}
                    >
                      <GitCompareArrows className="size-3.5" />
                      对比
                    </Button>
                  </div>
                </div>
                <div className="flex-1 overflow-y-auto rounded-md border border-border/60 bg-background/70 p-2">
                  {showDiff ? (
                    <pre className="whitespace-pre-wrap text-[11px] leading-relaxed font-mono break-all">
                      {diffText || '暂无 diff'}
                    </pre>
                  ) : (
                    <div className="text-[11px] text-muted-foreground">
                      选择版本后可对比两个版本的差异。
                      {diffSummary ? (
                        <div className="mt-3 grid grid-cols-3 gap-2">
                          <div className="rounded-md border border-emerald-500/20 bg-emerald-50 px-2 py-1 text-center">
                            <div className="text-[10px] text-emerald-700">新增</div>
                            <div className="text-sm font-semibold text-emerald-900">{diffSummary.added}</div>
                          </div>
                          <div className="rounded-md border border-amber-500/20 bg-amber-50 px-2 py-1 text-center">
                            <div className="text-[10px] text-amber-700">修改</div>
                            <div className="text-sm font-semibold text-amber-900">{diffSummary.changed}</div>
                          </div>
                          <div className="rounded-md border border-red-500/20 bg-red-50 px-2 py-1 text-center">
                            <div className="text-[10px] text-red-700">删除</div>
                            <div className="text-sm font-semibold text-red-900">{diffSummary.removed}</div>
                          </div>
                        </div>
                      ) : null}
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between gap-2 border-t border-border/60 px-4 py-3">
              <div className="text-[11px] text-muted-foreground">
                版本快照保存在 `versions/` 目录，可用于回滚与审计。
              </div>
              <div className="flex gap-2">
                <Button variant="ghost" size="sm" onClick={() => void loadVersions()} disabled={loading || saving}>
                  重新加载
                </Button>
                <Button variant="secondary" size="sm" onClick={() => onOpenChange(false)}>
                  关闭
                </Button>
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
