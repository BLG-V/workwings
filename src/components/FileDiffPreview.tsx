import { useEffect, useState } from 'react'
import { X, Check, FileDiff, Loader2, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

export interface DiffResult {
  has_diff: boolean
  diff: string
  old_size: number
  new_size: number
  path: string
}

interface FileDiffPreviewProps {
  projectRoot: string
  filePath: string
  oldContent?: string
  onClose?: () => void
  onApply?: () => void
}

export default function FileDiffPreview({
  projectRoot,
  filePath,
  oldContent = '',
  onClose,
  onApply,
}: FileDiffPreviewProps) {
  const [diff, setDiff] = useState<DiffResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchDiff() {
      try {
        setLoading(true)
        setError(null)
        
        // Import dynamically to avoid circular dependencies
        const { compareProjectFileDiff } = await import('@/lib/mawp-api')
        
        const result = await compareProjectFileDiff(
          projectRoot,
          filePath,
          oldContent,
        )
        setDiff(result)
      } catch (err) {
        setError(err instanceof Error ? err.message : '获取 diff 失败')
      } finally {
        setLoading(false)
      }
    }

    if (projectRoot && filePath) {
      fetchDiff()
    }
  }, [projectRoot, filePath, oldContent])

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-8 min-h-[200px]">
        <Loader2 className="size-6 mb-3 animate-spin text-primary" />
        <p className="text-sm text-muted-foreground">正在计算 diff...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center p-8 min-h-[200px]">
        <X className="size-6 mb-3 text-destructive" />
        <p className="text-sm text-muted-foreground">{error}</p>
        <Button
          size="sm"
          variant="secondary"
          className="mt-3"
          onClick={() => {
            setError(null)
            setLoading(true)
          }}
        >
          <RefreshCw className="size-3.5 mr-1.5" />
          重试
        </Button>
      </div>
    )
  }

  if (!diff) {
    return (
      <div className="flex flex-col items-center justify-center p-8 min-h-[200px]">
        <FileDiff className="size-6 mb-3 text-muted-foreground/70" />
        <p className="text-sm text-muted-foreground">无 diff 数据</p>
      </div>
    )
  }

  const { has_diff, diff: diffText, old_size, new_size } = diff
  const sizeChange = new_size - old_size

  return (
    <div className="flex flex-col h-full min-h-[200px]">
      <div className="flex items-center justify-between gap-2 border-b border-border/60 px-3 py-2">
        <div className="flex items-center gap-2">
          <FileDiff className="size-4 text-primary" />
          <span className="text-sm font-medium">{filePath}</span>
          {has_diff ? (
            <Badge variant="default" className="bg-amber-100 text-amber-700 border-amber-200">
              有变更
            </Badge>
          ) : (
            <Badge variant="secondary" className="bg-emerald-100 text-emerald-700 border-emerald-200">
              无变更
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-muted-foreground">
            {old_size} → {new_size} bytes ({sizeChange >= 0 ? '+' : ''}{sizeChange})
          </span>
          {onClose && (
            <Button
              size="icon"
              variant="ghost"
              className="size-6 pressable"
              onClick={onClose}
            >
              <X className="size-3.5" />
            </Button>
          )}
        </div>
      </div>
      
      <div className="flex-1 overflow-y-auto bg-muted/30 p-3">
        {has_diff ? (
          <pre className="text-[11px] font-mono leading-relaxed whitespace-pre-wrap break-all">
            {diffText}
          </pre>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground/70">
            <Check className="size-5 mb-2" />
            <p className="text-sm">文件内容未变更</p>
          </div>
        )}
      </div>

      {has_diff && onApply && (
        <div className="border-t border-border/60 px-3 py-2">
          <Button
            size="sm"
            className="w-full pressable"
            onClick={onApply}
          >
            <Check className="size-3.5 mr-1.5" />
            应用变更
          </Button>
        </div>
      )}
    </div>
  )
}

// 简单的 diff 视图，用于展示多个文件的变更摘要
export interface FileChangeSummary {
  path: string
  has_diff: boolean
  old_size: number
  new_size: number
}

export function FileChangesSummary({
  changes,
  onSelectFile,
}: {
  changes: FileChangeSummary[]
  onSelectFile?: (path: string) => void
}) {
  const changedCount = changes.filter((c) => c.has_diff).length
  const totalSizeChange = changes.reduce(
    (sum, c) => sum + (c.new_size - c.old_size),
    0,
  )

  return (
    <div className="rounded-xl border border-border/80 bg-muted/20 overflow-hidden">
      <div className="flex items-center justify-between border-b border-border/60 px-3 py-2">
        <span className="text-xs font-medium">文件变更摘要</span>
        <span className="text-[10px] text-muted-foreground">
          {changedCount}/{changes.length} 个文件有变更
          {totalSizeChange !== 0 && (
            <>
              {' '}
              ({totalSizeChange >= 0 ? '+' : ''}{totalSizeChange} bytes)
            </>
          )}
        </span>
      </div>
      <div className="max-h-40 overflow-y-auto">
        {changes.length === 0 ? (
          <p className="px-3 py-3 text-[11px] text-muted-foreground">
            暂无文件变更
          </p>
        ) : (
          changes.map((change) => (
            <button
              key={change.path}
              type="button"
              className={cn(
                'flex items-center justify-between w-full gap-2 px-3 py-1.5 text-left text-[11px] pressable hover:bg-muted/70',
                change.has_diff
                  ? 'bg-amber-50/50 text-amber-800'
                  : 'text-muted-foreground/80',
              )}
              onClick={() => onSelectFile?.(change.path)}
            >
              <span className="truncate flex-1">{change.path}</span>
              <span
                className={cn(
                  'text-[10px] font-mono',
                  change.has_diff
                    ? 'text-amber-600'
                    : 'text-emerald-600',
                )}
              >
                {change.has_diff ? '修改' : '无变更'}
              </span>
            </button>
          ))
        )}
      </div>
    </div>
  )
}
