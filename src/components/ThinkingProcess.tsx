import { useEffect, useState } from 'react'
import { Brain, Check, ChevronDown, ChevronRight, Loader2 } from 'lucide-react'

interface ThinkingProcessProps {
  steps: string[]
  done?: boolean
  /** 完成后默认是否展开；思考中始终展开 */
  defaultOpen?: boolean
  titleThinking?: string
  titleDone?: string
  /** 主对话更醒目的样式 */
  prominent?: boolean
}

export default function ThinkingProcess({
  steps,
  done,
  defaultOpen = true,
  titleThinking = '正在思考…',
  titleDone = '思考过程',
  prominent = false,
}: ThinkingProcessProps) {
  const [open, setOpen] = useState(!done ? true : defaultOpen)

  useEffect(() => {
    if (!done) setOpen(true)
  }, [done])

  const list = steps.length ? steps : ['理解请求…']

  return (
    <div
      className={`overflow-hidden rounded-xl border ${
        prominent
          ? 'border-primary/25 bg-primary/[0.04] shadow-sm'
          : 'border-border/80 bg-muted/40'
      }`}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2.5 text-xs font-medium text-foreground/90 pressable"
      >
        {open ? (
          <ChevronDown className="size-3.5 text-primary shrink-0" />
        ) : (
          <ChevronRight className="size-3.5 text-primary shrink-0" />
        )}
        <Brain className={`size-3.5 text-primary shrink-0 ${!done ? 'animate-pulse' : ''}`} />
        <span>{done ? titleDone : titleThinking}</span>
        {!done && (
          <Loader2 className="size-3 animate-spin text-primary" />
        )}
        <span className="ml-auto text-[10px] text-muted-foreground tabular-nums">
          {done ? `共 ${list.length} 步 · 已完成` : `已推理 ${list.length} 步`}
        </span>
      </button>
      {open && (
        <div className="space-y-2 border-t border-border/70 px-3 py-2.5">
          {list.map((step, i) => {
            const isCurrent = !done && i === list.length - 1
            const isPending = !done && i === list.length - 1
            return (
              <div
                key={`${step}-${i}`}
                className={`flex items-start gap-2 text-[12px] leading-relaxed ${
                  isCurrent ? 'text-foreground' : 'text-muted-foreground'
                }`}
              >
                {isPending ? (
                  <Loader2 className="mt-0.5 size-3.5 animate-spin text-primary shrink-0" />
                ) : (
                  <Check className="mt-0.5 size-3.5 text-emerald-500 shrink-0" />
                )}
                <span>
                  <span className="mr-1.5 font-mono text-[10px] text-muted-foreground/80">
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  {step}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
