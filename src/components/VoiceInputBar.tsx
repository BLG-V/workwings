import { useEffect, useMemo, useState } from 'react'
import { ArrowUp, X } from 'lucide-react'
import { cn } from '@/lib/utils'

type VoiceInputBarProps = {
  open: boolean
  /** 实时识别文案 */
  transcript: string
  /** 0~1 音量，驱动波形 */
  level: number
  busy?: boolean
  onCancel: () => void
  onConfirm: () => void
}

const BAR_COUNT = 28

/** 豆包风格：底部半透明蓝条 + 波形 + 取消/发送 */
export default function VoiceInputBar({
  open,
  transcript,
  level,
  busy,
  onCancel,
  onConfirm,
}: VoiceInputBarProps) {
  const [tick, setTick] = useState(0)

  useEffect(() => {
    if (!open) return
    const id = window.setInterval(() => setTick((n) => n + 1), 80)
    return () => window.clearInterval(id)
  }, [open])

  const heights = useMemo(() => {
    // level 很低时几乎不晃，方便判断麦是否真正在采音
    const live = level > 0.04
    const base = live ? 0.2 + level * 0.85 : 0.08
    return Array.from({ length: BAR_COUNT }, (_, i) => {
      if (!live) {
        const mid = 1 - Math.abs(i - (BAR_COUNT - 1) / 2) / (BAR_COUNT / 2)
        return 0.08 + mid * 0.06
      }
      const wave =
        0.55 +
        0.45 * Math.sin(tick * 0.55 + i * 0.45) * (0.35 + level * 0.9)
      const mid = 1 - Math.abs(i - (BAR_COUNT - 1) / 2) / (BAR_COUNT / 2)
      return Math.max(0.12, Math.min(1, base * wave * (0.45 + mid * 0.7)))
    })
  }, [level, tick])

  if (!open) return null

  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-0 z-40 flex flex-col items-center px-4 pb-5 pt-10">
      <div
        className={cn(
          'pointer-events-auto mb-3 max-w-[min(100%,28rem)] truncate rounded-full px-4 py-1.5 text-center text-[13px]',
          'bg-black/35 text-white/95 backdrop-blur-md',
          !transcript && 'text-white/70',
        )}
      >
        {transcript || '请开始说话…'}
      </div>

      <div
        className={cn(
          'pointer-events-auto flex w-full max-w-[min(100%,36rem)] items-center gap-3 rounded-[22px] px-3 py-2.5',
          'shadow-[0_12px_40px_rgba(37,99,235,0.35)]',
        )}
        style={{
          background:
            'linear-gradient(105deg, rgba(59,130,246,0.92) 0%, rgba(37,99,235,0.88) 45%, rgba(29,78,216,0.9) 100%)',
          backdropFilter: 'blur(16px)',
        }}
      >
        <button
          type="button"
          title="取消"
          onClick={onCancel}
          className="inline-flex size-9 shrink-0 items-center justify-center rounded-full bg-white/20 text-white hover:bg-white/30 pressable"
        >
          <X className="size-4" />
        </button>

        <div className="flex h-9 min-w-0 flex-1 items-center justify-center gap-[3px] px-1">
          {heights.map((h, i) => (
            <span
              key={i}
              className="w-[3px] rounded-full bg-white/95"
              style={{
                height: `${Math.round(8 + h * 22)}px`,
                opacity: 0.55 + h * 0.45,
                transition: 'height 70ms linear',
              }}
            />
          ))}
        </div>

        <button
          type="button"
          title="发送"
          onClick={onConfirm}
          disabled={busy}
          className="inline-flex size-10 shrink-0 items-center justify-center rounded-full bg-[#2563eb] text-white shadow-md hover:bg-[#1d4ed8] disabled:opacity-60 pressable"
        >
          <ArrowUp className="size-5" />
        </button>
      </div>
    </div>
  )
}
