import { Check, Circle, ArrowRight, Sparkles, AlertTriangle, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { AdvancedPhase } from '@/lib/advanced-api'

/** 里程碑依赖链：默认串行 p1→p2→…，高亮当前期与完成态 */
export default function PhaseDependencyGraph({
  phases,
  currentPhaseId,
}: {
  phases: AdvancedPhase[]
  currentPhaseId?: string | null
}) {
  if (!phases.length) return null

  const doneCount = phases.filter((p) => p.status === 'done').length
  const pct = Math.round((doneCount / phases.length) * 100)

  return (
    <div className="rounded-xl border border-border/80 bg-muted/20 overflow-hidden">
      <div className="flex items-center justify-between gap-2 border-b border-border/60 px-3 py-2">
        <div className="flex items-center gap-1.5 text-xs font-medium">
          <Sparkles className="size-3.5 text-primary" />
          分期依赖图
        </div>
        <span className="text-[10px] text-muted-foreground">
          {doneCount}/{phases.length} 完成 · {pct}%
        </span>
      </div>

      <div className="px-3 pt-3">
        <div className="h-1.5 rounded-full bg-muted overflow-hidden">
          <div
            className="h-full rounded-full bg-primary/80 transition-all duration-500"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      <div className="flex items-stretch gap-0 overflow-x-auto px-3 py-3">
        {phases.map((phase, i) => {
          const isCurrent = phase.id === currentPhaseId
          const isDone = phase.status === 'done'
          const isPartial = phase.status === 'partial'
          const isFailed = phase.status === 'failed'
          return (
            <div key={phase.id} className="flex items-center min-w-0">
              <div
                className={cn(
                  'w-[140px] shrink-0 rounded-xl border px-2.5 py-2 transition-colors',
                  isDone && 'border-emerald-500/35 bg-emerald-500/5',
                  isPartial && 'border-amber-500/40 bg-amber-500/5',
                  isFailed && 'border-red-500/40 bg-red-500/5',
                  isCurrent && !isDone && !isPartial && !isFailed && 'border-primary/45 bg-primary/5',
                  !isDone && !isPartial && !isFailed && !isCurrent && 'border-border/70 bg-card/50',
                )}
                title={phase.goal}
              >
                <div className="flex items-center gap-1.5 mb-1">
                  {isDone ? (
                    <Check className="size-3.5 text-emerald-600 shrink-0" />
                  ) : isPartial ? (
                    <AlertTriangle className="size-3.5 text-amber-600 shrink-0" />
                  ) : isFailed ? (
                    <X className="size-3.5 text-red-600 shrink-0" />
                  ) : isCurrent ? (
                    <Circle className="size-3.5 text-primary shrink-0 fill-primary/30" />
                  ) : (
                    <Circle className="size-3.5 text-muted-foreground/50 shrink-0" />
                  )}
                  <span className="text-[10px] font-mono text-muted-foreground">
                    {phase.id.toUpperCase()}
                  </span>
                </div>
                <div className="text-[12px] font-medium leading-snug line-clamp-2">
                  {phase.title}
                </div>
                <div className="mt-1 text-[10px] text-muted-foreground">
                  {isDone
                    ? '真正完成'
                    : isPartial
                      ? '部分完成'
                      : isFailed
                        ? '失败'
                        : isCurrent
                          ? '当前待生成'
                          : '等待前置'}
                </div>
                {(() => {
                  const deps =
                    phase.depends_on && phase.depends_on.length > 0
                      ? phase.depends_on
                      : i > 0
                        ? [phases[i - 1].id]
                        : []
                  return deps.length ? (
                    <div className="mt-1 text-[9px] text-muted-foreground/80">
                      依赖 ← {deps.map((d) => d.toUpperCase()).join(' · ')}
                    </div>
                  ) : (
                    <div className="mt-1 text-[9px] text-muted-foreground/80">起点</div>
                  )
                })()}
              </div>
              {i < phases.length - 1 ? (
                <ArrowRight
                  className={cn(
                    'mx-1.5 size-3.5 shrink-0',
                    isDone ? 'text-emerald-600/70' : 'text-muted-foreground/40',
                  )}
                />
              ) : null}
            </div>
          )
        })}
      </div>
    </div>
  )
}
