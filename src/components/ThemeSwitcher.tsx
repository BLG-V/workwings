import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from 'react'
import { createPortal } from 'react-dom'
import { Palette, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useThemePalette } from '@/hooks/use-theme'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'

/** 侧栏/顶栏快捷主题切换（Portal 弹出，避免被 overflow 裁切） */
export default function ThemeSwitcher({
  compact = false,
}: {
  compact?: boolean
}) {
  const { palette, setPalette, presets } = useThemePalette()
  const [open, setOpen] = useState(false)
  const btnRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState({ top: 0, left: 0 })
  const previewStyle = (swatch: string[]): CSSProperties =>
    ({
      '--pixel-preview-rail': swatch[0],
      '--pixel-preview-surface': swatch[1],
      '--pixel-preview-primary': swatch[2],
      '--pixel-preview-secondary': swatch[3],
      '--pixel-preview-line': swatch[3],
    }) as CSSProperties

  useLayoutEffect(() => {
    if (!open || !btnRef.current) return
    const rect = btnRef.current.getBoundingClientRect()
    const menuW = 304
    const menuH = Math.min(360, window.innerHeight - 24)
    let left = rect.left
    if (left + menuW > window.innerWidth - 8) {
      left = Math.max(8, window.innerWidth - menuW - 8)
    }
    // 优先向上展开
    let top = rect.top - 8 - menuH
    if (top < 8) {
      top = Math.min(rect.bottom + 8, window.innerHeight - menuH - 8)
    }
    setPos({ top, left })
  }, [open])

  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      const t = e.target as Node
      if (btnRef.current?.contains(t) || menuRef.current?.contains(t)) return
      setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDoc)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <>
      <Button
        ref={btnRef}
        type="button"
        variant="ghost"
        size={compact ? 'icon' : 'sm'}
        className={cn(
          'pressable text-muted-foreground hover:text-foreground',
          compact ? 'size-8' : 'h-8 gap-1.5 px-2',
        )}
        title="切换主题"
        aria-expanded={open}
        onClick={(e) => {
          e.stopPropagation()
          setOpen((v) => !v)
        }}
      >
        <Palette className="size-3.5" />
        {!compact && <span className="text-xs">主题</span>}
      </Button>
      {open &&
        createPortal(
          <div
            ref={menuRef}
            className="pixel-theme-menu fixed z-[200] w-[304px] max-h-[min(420px,calc(100vh-24px))] overflow-y-auto border border-border/80 bg-popover p-2 shadow-xl"
            style={{ top: pos.top, left: pos.left }}
            role="menu"
          >
            <div className="pixel-theme-menu__header px-2 pb-2 text-[11px] text-muted-foreground">
              <span className="font-mono text-primary">THEME / 06</span>
              <span className="ml-2">像素工作台主题</span>
            </div>
            {presets.map((preset) => {
              const selected = palette === preset.id
              return (
                <button
                  key={preset.id}
                  type="button"
                  role="menuitem"
                  aria-current={selected ? 'true' : undefined}
                  onClick={() => {
                    setPalette(preset.id)
                    toast.success(`已切换「${preset.label}」`)
                    setOpen(false)
                  }}
                  className={cn(
                    'pixel-theme-option flex w-full items-center gap-2.5 border border-transparent px-2 py-2 text-left pressable transition-colors',
                    selected
                      ? 'bg-primary/15 text-foreground ring-1 ring-primary/35'
                      : 'hover:bg-muted/70 text-muted-foreground hover:text-foreground',
                  )}
                >
                  <span className="pixel-theme-preview w-[76px] shrink-0" style={previewStyle(preset.swatch)} aria-hidden>
                    <span className="pixel-theme-preview__rail" />
                    <span className="pixel-theme-preview__body">
                      <span className="pixel-theme-preview__top" />
                      <span className="pixel-theme-preview__blocks">
                        <span />
                        <span />
                        <span />
                      </span>
                      <span className="pixel-theme-preview__bottom" />
                    </span>
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-1.5">
                      <span className="text-[12px] font-medium truncate">
                        {preset.label}
                      </span>
                      <span className="text-[10px] text-primary/80 shrink-0">
                        {preset.hue}
                      </span>
                    </span>
                    <span className="block text-[10px] opacity-70 truncate">
                      {preset.desc}
                    </span>
                  </span>
                  {selected && (
                    <Check className="size-3.5 text-primary shrink-0" />
                  )}
                </button>
              )
            })}
          </div>,
          document.body,
        )}
    </>
  )
}
