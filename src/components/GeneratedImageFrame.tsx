import { useState } from 'react'
import { Download, ExternalLink, ImageOff, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'

type GeneratedImageFrameProps = {
  src?: string
  alt?: string
  className?: string
}

/** 对话里的生成图：加载态 / 失败重试 / 下载 */
export default function GeneratedImageFrame({
  src,
  alt,
  className,
}: GeneratedImageFrameProps) {
  const [status, setStatus] = useState<'loading' | 'ok' | 'error'>('loading')
  const [bust, setBust] = useState(0)

  if (!src) return null

  const displaySrc =
    bust > 0
      ? `${src}${src.includes('?') ? '&' : '?'}_r=${bust}`
      : src

  const download = async () => {
    if (!src) return
    try {
      if (src.startsWith('data:')) {
        const a = document.createElement('a')
        a.href = src
        a.download = `${(alt || '智流图像').slice(0, 40)}.png`
        a.click()
        toast.success('已下载图片')
        return
      }
      const res = await fetch(src, { cache: 'no-store' })
      if (!res.ok) throw new Error('fetch failed')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${(alt || '智流图像').slice(0, 40)}.png`
      a.click()
      URL.revokeObjectURL(url)
      toast.success('已下载图片')
    } catch {
      window.open(src, '_blank', 'noopener,noreferrer')
      toast.message('已在新标签打开，可右键另存为')
    }
  }

  return (
    <figure
      className={cn(
        'my-2 overflow-hidden rounded-2xl border border-border/60 bg-muted/30',
        className,
      )}
    >
      <div className="relative bg-[linear-gradient(160deg,#f4f6fa,#e8edf5)]">
        {status === 'loading' ? (
          <div className="flex h-56 items-center justify-center gap-2 text-[13px] text-muted-foreground">
            <Loader2 className="size-4 animate-spin text-primary" />
            画面加载中…
          </div>
        ) : null}
        {status === 'error' ? (
          <div className="flex h-56 flex-col items-center justify-center gap-2 px-4 text-center text-[13px] text-muted-foreground">
            <ImageOff className="size-5 opacity-60" />
            <span>图片加载失败（网络或服务繁忙）</span>
            <button
              type="button"
              className="rounded-md bg-primary/10 px-2.5 py-1 text-primary pressable"
              onClick={() => {
                setStatus('loading')
                setBust((n) => n + 1)
              }}
            >
              重试加载
            </button>
          </div>
        ) : null}
        <img
          key={displaySrc}
          src={displaySrc}
          alt={alt || '生成图像'}
          className={cn(
            'mx-auto max-h-[480px] w-full object-contain',
            status !== 'ok' && 'absolute opacity-0 pointer-events-none',
          )}
          loading="eager"
          onLoad={() => setStatus('ok')}
          onError={() => setStatus('error')}
        />
      </div>
      <figcaption className="flex items-center gap-2 border-t border-border/50 px-3 py-2">
        <span className="min-w-0 flex-1 truncate text-[12px] text-muted-foreground">
          {alt || '智流图像'}
        </span>
        <button
          type="button"
          title="下载"
          onClick={() => void download()}
          className="inline-flex size-7 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground pressable"
        >
          <Download className="size-3.5" />
        </button>
        {!src.startsWith('data:') ? (
          <a
            href={src}
            target="_blank"
            rel="noreferrer"
            title="新窗口打开"
            className="inline-flex size-7 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground pressable"
          >
            <ExternalLink className="size-3.5" />
          </a>
        ) : null}
      </figcaption>
    </figure>
  )
}
