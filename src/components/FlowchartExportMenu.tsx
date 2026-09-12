import { useEffect, useRef, useState } from 'react'
import { ChevronDown, Download } from 'lucide-react'
import { toast } from 'sonner'
import type { FlowchartPayload } from '@/lib/flowchart'
import {
  exportFlowchart,
  FLOWCHART_EXPORT_OPTIONS,
  type FlowchartExportFormat,
} from '@/lib/flowchart-export'
import { cn } from '@/lib/utils'

type Props = {
  doc: FlowchartPayload
  /** 阻止冒泡到卡片打开 */
  stopPropagation?: boolean
  align?: 'left' | 'right'
  compact?: boolean
  className?: string
}

export default function FlowchartExportMenu({
  doc,
  stopPropagation,
  align = 'right',
  compact,
  className,
}: Props) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  const run = async (format: FlowchartExportFormat) => {
    setBusy(true)
    try {
      await exportFlowchart(doc, format)
      const label =
        FLOWCHART_EXPORT_OPTIONS.find((o) => o.id === format)?.label || format
      toast.success(`已导出 ${label}`)
      setOpen(false)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '导出失败')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      ref={rootRef}
      className={cn('relative', className)}
      onClick={(e) => {
        if (stopPropagation) e.stopPropagation()
      }}
    >
      <button
        type="button"
        title="导出"
        disabled={busy}
        onClick={(e) => {
          if (stopPropagation) e.stopPropagation()
          setOpen((v) => !v)
        }}
        className={cn(
          'inline-flex items-center justify-center gap-0.5 rounded-md text-muted-foreground hover:bg-muted hover:text-foreground pressable disabled:opacity-50',
          compact ? 'size-7' : 'h-8 px-2 text-[12px]',
        )}
      >
        <Download className={compact ? 'size-3.5' : 'size-3.5'} />
        {!compact ? (
          <>
            <span>导出</span>
            <ChevronDown className="size-3 opacity-70" />
          </>
        ) : null}
      </button>

      {open ? (
        <div
          className={cn(
            'absolute z-30 mt-1 w-52 overflow-hidden rounded-xl border border-border/80 bg-popover py-1 shadow-lg',
            align === 'right' ? 'right-0' : 'left-0',
          )}
        >
          {FLOWCHART_EXPORT_OPTIONS.map((opt) => (
            <button
              key={opt.id}
              type="button"
              disabled={busy}
              className="flex w-full flex-col items-start px-3 py-2 text-left hover:bg-muted pressable disabled:opacity-50"
              onClick={() => void run(opt.id)}
            >
              <span className="text-[13px] font-medium text-foreground">
                {opt.label}
              </span>
              <span className="text-[11px] text-muted-foreground">{opt.hint}</span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}
