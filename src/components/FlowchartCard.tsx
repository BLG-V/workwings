import type { MouseEvent } from 'react'
import { useEffect, useMemo, useState } from 'react'
import mermaid from 'mermaid'
import { GitBranch } from 'lucide-react'
import type { FlowchartPayload } from '@/lib/flowchart'
import { flowchartToMermaid } from '@/lib/flowchart'
import FlowchartExportMenu from '@/components/FlowchartExportMenu'
import { cn } from '@/lib/utils'

let mermaidReady = false
function ensureMermaid() {
  if (mermaidReady) return
  mermaid.initialize({
    startOnLoad: false,
    theme: 'neutral',
    securityLevel: 'loose',
    flowchart: { curve: 'basis', htmlLabels: true },
  })
  mermaidReady = true
}

type FlowchartCardProps = {
  doc: FlowchartPayload
  onOpen: () => void
  className?: string
}

export default function FlowchartCard({ doc, onOpen, className }: FlowchartCardProps) {
  const [svg, setSvg] = useState('')
  const [err, setErr] = useState('')
  const code = useMemo(() => flowchartToMermaid(doc), [doc])

  useEffect(() => {
    let cancelled = false
    ensureMermaid()
    const id = `fc-${Math.random().toString(36).slice(2, 9)}`
    void mermaid
      .render(id, code)
      .then(({ svg: out }) => {
        if (!cancelled) {
          setSvg(out)
          setErr('')
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setSvg('')
          setErr(e instanceof Error ? e.message : '预览失败')
        }
      })
    return () => {
      cancelled = true
    }
  }, [code])

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onOpen()
        }
      }}
      className={cn(
        'group w-full max-w-[520px] cursor-pointer overflow-hidden rounded-2xl border border-border/70 bg-card text-left shadow-sm pressable',
        'hover:border-primary/35',
        className,
      )}
    >
      <div className="flex items-start gap-2.5 border-b border-border/50 px-3.5 py-2.5">
        <div className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-emerald-500/12 text-emerald-700">
          <GitBranch className="size-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-[11px] text-muted-foreground">流程图 · 可编辑</div>
          <div className="truncate text-[14px] font-semibold">{doc.title}</div>
          <div className="mt-0.5 text-[12px] text-muted-foreground">
            {doc.nodes.length} 节点 · {doc.edges.length} 连线
          </div>
        </div>
        <FlowchartExportMenu doc={doc} stopPropagation compact />
      </div>
      <div
        className="max-h-[220px] overflow-auto bg-[linear-gradient(165deg,#f7faf8,#eef3f0)] p-3"
        onClick={(e: MouseEvent) => e.stopPropagation()}
      >
        {err ? (
          <div className="py-8 text-center text-[12px] text-muted-foreground">
            预览失败，点击打开编辑器
          </div>
        ) : svg ? (
          <div
            className="flowchart-mermaid-preview flex justify-center [&_svg]:max-w-full"
            dangerouslySetInnerHTML={{ __html: svg }}
          />
        ) : (
          <div className="py-8 text-center text-[12px] text-muted-foreground">
            生成预览中…
          </div>
        )}
      </div>
    </div>
  )
}
