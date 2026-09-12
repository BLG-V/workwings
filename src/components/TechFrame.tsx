import type { CSSProperties, ReactNode } from 'react'
import { cn } from '@/lib/utils'

type TechFrameProps = {
  children: ReactNode
  className?: string
  /** inner content class */
  contentClassName?: string
  /** soft=轻；panel=侧栏分区；normal=默认；strong=输入框等更明显光迹 */
  intensity?: 'soft' | 'panel' | 'normal' | 'strong'
  /** 错开各框光迹相位（秒） */
  delaySec?: number
  as?: 'div' | 'section'
}

/** 科技风边框：边缘有柔和滑动光线 */
export default function TechFrame({
  children,
  className,
  contentClassName,
  intensity = 'normal',
  delaySec = 0,
  as: Tag = 'div',
}: TechFrameProps) {
  return (
    <Tag
      className={cn(
        'tech-frame relative',
        intensity === 'soft' && 'tech-frame--soft',
        intensity === 'panel' && 'tech-frame--panel',
        intensity === 'strong' && 'tech-frame--strong',
        className,
      )}
      style={
        delaySec
          ? ({ ['--tech-spin-delay']: `${delaySec}s` } as CSSProperties)
          : undefined
      }
    >
      <span className="tech-frame-trace" aria-hidden />
      <span className="tech-frame-trace tech-frame-trace--lag" aria-hidden />
      <span className="tech-frame-glow" aria-hidden />
      <div className={cn('tech-frame-inner relative z-[1]', contentClassName)}>
        {children}
      </div>
    </Tag>
  )
}
