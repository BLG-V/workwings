import { Link, useLocation } from 'react-router-dom'
import { STUDIO_ORDER, STUDIO_META, type StudioPageKind } from '@/lib/chat-intent'
import { Check } from 'lucide-react'
import FlowEffectDemo from '@/components/FlowEffectDemo'
import { flowNavState, isPipelineActive } from '@/lib/studio-session'

const KIND_PATH: Record<StudioPageKind, string> = {
  requirement: '/studio/requirement',
  architecture: '/studio/architecture',
  code: '/studio/code',
  test: '/studio/test',
  deploy: '/studio/deploy',
}

interface CoreFlowBarProps {
  active?: StudioPageKind | 'chat'
  completed?: StudioPageKind[]
  /** 是否展示可播放的效果演示区，默认开启 */
  showDemo?: boolean
}

export default function CoreFlowBar({
  active = 'chat',
  completed = [],
  showDemo = true,
}: CoreFlowBarProps) {
  const location = useLocation()
  const current =
    active !== 'chat'
      ? active
      : (STUDIO_ORDER.find((k) => location.pathname.includes(`/studio/${k}`)) ??
        null)
  const inFlow = isPipelineActive()

  return (
    <div className="pixel-flowbar rounded-2xl border border-border bg-card/80 px-3 py-2.5 shadow-sm">
      <div className="pixel-flowbar__header mb-2 flex items-center justify-between px-1">
        <div className="text-xs font-medium text-foreground">工作台阶段（WorkWings Agent 编排）</div>
        <div className="text-[11px] text-muted-foreground">
          WorkWings Agent：需求(requirement) → 架构(planner) → 代码(coding/frontend) → 测试(testing) →
          交付(ship)
        </div>
      </div>
      <div className="flex items-center gap-1 overflow-x-auto pb-0.5">
        {STUDIO_ORDER.map((kind, index) => {
          const done = completed.includes(kind)
          const isActive = current === kind
          return (
            <div key={kind} className="flex items-center min-w-0">
              <Link
                to={KIND_PATH[kind]}
                state={inFlow ? flowNavState() : { clearFlow: true }}
                className={`pixel-flowbar__step pressable inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] whitespace-nowrap transition-colors ${
                  isActive
                    ? 'border-primary bg-primary/10 text-primary'
                    : done
                      ? 'border-emerald-300 bg-emerald-50 text-emerald-700'
                      : 'border-border bg-muted/40 text-muted-foreground hover:border-primary/40 hover:text-foreground'
                }`}
              >
                <span className="font-mono text-[10px] opacity-70">
                  {String(index + 1).padStart(2, '0')}
                </span>
                {done && !isActive ? <Check className="size-3" /> : null}
                {STUDIO_META[kind].title.replace(/生成|验证|上线/g, '')}
              </Link>
              {index < STUDIO_ORDER.length - 1 && (
                <div className="pixel-flowbar__connector mx-1 h-px w-4 shrink-0 bg-border" />
              )}
            </div>
          )
        })}
      </div>

      {showDemo ? <FlowEffectDemo defaultKind={current} /> : null}
    </div>
  )
}
