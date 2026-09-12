import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { ExternalLink, AlertCircle, X, ArrowUp, ArrowDown, ArrowLeft, ArrowRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  buildCodePreview,
  createPreviewObjectUrl,
} from '@/lib/code-preview'

interface CodePreviewDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  markdown: string
}

export default function CodePreviewDialog({
  open,
  onOpenChange,
  markdown,
}: CodePreviewDialogProps) {
  const preview = useMemo(() => buildCodePreview(markdown), [markdown])
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const [blobUrl, setBlobUrl] = useState<string | null>(null)

  useEffect(() => {
    if (!open || !preview.ok) {
      setBlobUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev)
        return null
      })
      return
    }
    const url = createPreviewObjectUrl(preview.html)
    setBlobUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return url
    })
    return () => URL.revokeObjectURL(url)
  }, [open, preview])

  const injectKey = (type: 'keydown' | 'keyup', key: string, code: string) => {
    const win = iframeRef.current?.contentWindow as
      | (Window & { __mawpInjectKey?: (t: string, k: string, c: string) => void })
      | null
    if (!win) return
    if (typeof win.__mawpInjectKey === 'function') {
      win.__mawpInjectKey(type, key, code)
      return
    }
    try {
      const doc = win.document
      const ev = new win.KeyboardEvent(type, {
        key,
        code,
        bubbles: true,
        cancelable: true,
      })
      doc.dispatchEvent(ev)
      win.dispatchEvent(ev)
    } catch {
      /* ignore */
    }
  }

  const pressKey = (key: string, code: string) => {
    injectKey('keydown', key, code)
    window.setTimeout(() => injectKey('keyup', key, code), 60)
  }

  // 把方向键等转发给 iframe，绕过弹层焦点问题
  useEffect(() => {
    if (!open || !preview.ok) return
    const onKeyDown = (e: KeyboardEvent) => {
      const forward = [
        'ArrowUp',
        'ArrowDown',
        'ArrowLeft',
        'ArrowRight',
        ' ',
        'Enter',
        'p',
        'P',
        'w',
        'a',
        's',
        'd',
        'W',
        'A',
        'S',
        'D',
      ]
      if (!forward.includes(e.key)) return
      e.preventDefault()
      e.stopPropagation()
      injectKey('keydown', e.key, e.code)
    }
    const onKeyUp = (e: KeyboardEvent) => {
      const forward = [
        'ArrowUp',
        'ArrowDown',
        'ArrowLeft',
        'ArrowRight',
        ' ',
        'Enter',
        'p',
        'P',
        'w',
        'a',
        's',
        'd',
        'W',
        'A',
        'S',
        'D',
      ]
      if (!forward.includes(e.key)) return
      e.preventDefault()
      e.stopPropagation()
      injectKey('keyup', e.key, e.code)
    }
    window.addEventListener('keydown', onKeyDown, true)
    window.addEventListener('keyup', onKeyUp, true)
    return () => {
      window.removeEventListener('keydown', onKeyDown, true)
      window.removeEventListener('keyup', onKeyUp, true)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, preview, blobUrl])

  const openBlank = () => {
    if (!preview.ok) return
    const url = createPreviewObjectUrl(preview.html)
    const w = window.open(url, '_blank', 'noopener,noreferrer')
    if (!w) {
      // 弹窗被拦时退回当前页下载式打开
      const a = document.createElement('a')
      a.href = url
      a.target = '_blank'
      a.rel = 'noopener'
      a.click()
    }
    // 延迟回收，给新窗口加载时间
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
  }

  useEffect(() => {
    if (!open || !preview.ok) return
    // 打开时自动新窗口，保证键盘可玩（弹窗里常被焦点陷阱挡）
    const t = window.setTimeout(() => openBlank(), 120)
    return () => window.clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, blobUrl])

  if (!open) return null

  return createPortal(
    <div className="fixed inset-0 z-[80] flex items-center justify-center p-4 md:p-8">
      <button
        type="button"
        className="absolute inset-0 bg-black/55"
        aria-label="关闭预览"
        onClick={() => onOpenChange(false)}
      />
      <div
        role="dialog"
        aria-modal="true"
        className="relative z-10 flex w-full max-w-5xl max-h-[92vh] flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-2xl"
        onMouseDown={() => iframeRef.current?.focus()}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-display text-lg font-semibold">运行预览</h2>
              {preview.ok && (
                <Badge variant="outline" className="text-[10px] font-normal">
                  {preview.mode}
                </Badge>
              )}
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              已尝试打开独立游戏窗口（键盘最稳）。也可在下方画面游玩，或点虚拟按键。
            </p>
          </div>
          <Button
            size="icon"
            variant="ghost"
            className="shrink-0"
            onClick={() => onOpenChange(false)}
          >
            <X className="size-4" />
          </Button>
        </div>

        {!preview.ok ? (
          <div className="rounded-xl border border-amber-200 bg-amber-50 text-amber-900 p-4 text-sm flex gap-2">
            <AlertCircle className="size-4 mt-0.5 shrink-0" />
            <div>
              <p>{preview.reason}</p>
              <p className="mt-2 text-xs opacity-80">
                提示：重新生成时加一句「请输出可直接运行的单文件 HTML（含 CSS/JS）」
              </p>
            </div>
          </div>
        ) : (
          <div className="grid gap-3 lg:grid-cols-[1fr_150px] min-h-0 flex-1">
            <div className="relative min-h-[420px] rounded-xl border border-border overflow-hidden bg-[#0b1220]">
              {blobUrl ? (
                <iframe
                  ref={iframeRef}
                  title="code-preview"
                  className="absolute inset-0 h-full w-full border-0"
                  sandbox="allow-scripts allow-same-origin allow-pointer-lock"
                  src={blobUrl}
                  tabIndex={0}
                  onLoad={() => {
                    iframeRef.current?.focus()
                    try {
                      iframeRef.current?.contentWindow?.focus()
                    } catch {
                      /* ignore */
                    }
                  }}
                />
              ) : null}
            </div>

            <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-border bg-muted/30 p-3">
              <p className="text-[11px] text-muted-foreground mb-1">虚拟按键</p>
              <Button
                size="icon"
                variant="secondary"
                className="pressable"
                onClick={() => pressKey('ArrowUp', 'ArrowUp')}
              >
                <ArrowUp className="size-4" />
              </Button>
              <div className="flex gap-2">
                <Button
                  size="icon"
                  variant="secondary"
                  className="pressable"
                  onClick={() => pressKey('ArrowLeft', 'ArrowLeft')}
                >
                  <ArrowLeft className="size-4" />
                </Button>
                <Button
                  size="icon"
                  variant="secondary"
                  className="pressable"
                  onClick={() => pressKey('ArrowDown', 'ArrowDown')}
                >
                  <ArrowDown className="size-4" />
                </Button>
                <Button
                  size="icon"
                  variant="secondary"
                  className="pressable"
                  onClick={() => pressKey('ArrowRight', 'ArrowRight')}
                >
                  <ArrowRight className="size-4" />
                </Button>
              </div>
              <Button
                size="sm"
                variant="secondary"
                className="w-full pressable mt-1"
                onClick={() => pressKey(' ', 'Space')}
              >
                空格
              </Button>
              <Button
                size="sm"
                variant="secondary"
                className="w-full pressable"
                onClick={() => pressKey('Enter', 'Enter')}
              >
                Enter 重开
              </Button>
              <Button
                size="sm"
                variant="secondary"
                className="w-full pressable"
                onClick={() => pressKey('p', 'KeyP')}
              >
                P 暂停
              </Button>
            </div>
          </div>
        )}

        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            关闭
          </Button>
          {preview.ok && (
            <Button className="pressable" onClick={openBlank}>
              <ExternalLink className="size-3.5 mr-1.5" />
              再次打开游戏窗口
            </Button>
          )}
        </div>
      </div>
    </div>,
    document.body,
  )
}
