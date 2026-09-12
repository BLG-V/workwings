import { Download, Expand, FileType } from 'lucide-react'
import type { MouseEvent } from 'react'
import { toast } from 'sonner'
import type { WritingDocPayload } from '@/lib/chat-history'
import { downloadWritingDocx } from '@/lib/export-docx'
import { cn } from '@/lib/utils'

function formatTime(iso: string) {
  try {
    const d = new Date(iso)
    const hh = String(d.getHours()).padStart(2, '0')
    const mm = String(d.getMinutes()).padStart(2, '0')
    return `${hh}:${mm}`
  } catch {
    return ''
  }
}

function previewLines(content: string): string[] {
  return content
    .replace(/^#{1,2}\s+.+\n+/, '')
    .split(/\n+/)
    .map((l) => l.replace(/^[#>*\-\s]+/, '').trim())
    .filter(Boolean)
    .slice(0, 6)
}

type WritingDocCardProps = {
  doc: WritingDocPayload
  onOpen: () => void
  className?: string
}

/** 对话里的 Word 云文档卡片（关闭写作框后） */
export default function WritingDocCard({
  doc,
  onOpen,
  className,
}: WritingDocCardProps) {
  const lines = previewLines(doc.content)

  const download = async (e: MouseEvent) => {
    e.stopPropagation()
    e.preventDefault()
    const text = doc.content.trim()
    if (!text) {
      toast.message('文档还是空的')
      return
    }
    try {
      await downloadWritingDocx(doc.title || '文档', text)
      toast.success('已下载 Word 文档')
    } catch {
      toast.error('下载失败')
    }
  }

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
        'group w-full max-w-[420px] cursor-pointer overflow-hidden rounded-2xl border border-border/70 bg-card text-left shadow-sm pressable',
        'hover:border-[#2b579a]/35 hover:bg-card',
        className,
      )}
    >
      <div className="flex gap-0">
        <div className="min-w-0 flex-1 px-3.5 py-3">
          <div className="mb-1.5 text-[11px] text-muted-foreground">
            云文档 · Word
          </div>
          <div className="flex items-start gap-2.5">
            <div className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-[#2b579a]/12 text-[#2b579a]">
              <FileType className="size-4" />
            </div>
            <div className="min-w-0">
              <div className="truncate text-[14px] font-semibold text-foreground">
                {doc.title || '未命名文档'}
              </div>
              <div className="mt-0.5 text-[12px] text-muted-foreground">
                创建时间：{formatTime(doc.createdAt)}
              </div>
            </div>
          </div>
        </div>

        <div className="relative w-[112px] shrink-0 border-l border-border/50 bg-[linear-gradient(165deg,#f3f7fc_0%,#e8eef6_55%,#dde6f0_100%)]">
          <div className="absolute inset-0 p-2.5">
            <div className="text-[9px] font-medium text-[#2b579a]/80">Word 文档</div>
            <div className="mt-1 space-y-1">
              {(lines.length ? lines : ['暂无预览']).map((line, i) => (
                <div
                  key={i}
                  className="h-1.5 rounded-sm bg-[#9db0c8]/55"
                  style={{ width: `${88 - i * 10}%`, opacity: 1 - i * 0.08 }}
                  title={line}
                />
              ))}
            </div>
          </div>
          <div className="absolute bottom-1.5 right-1.5 flex gap-1 opacity-90 group-hover:opacity-100">
            <span
              className="inline-flex size-6 items-center justify-center rounded-md bg-black/45 text-white"
              title="打开"
            >
              <Expand className="size-3" />
            </span>
            <button
              type="button"
              title="下载 Word"
              onClick={(e) => void download(e)}
              className="inline-flex size-6 items-center justify-center rounded-md bg-black/45 text-white pressable"
            >
              <Download className="size-3" />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
