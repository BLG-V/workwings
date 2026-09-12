import { useEffect, useMemo, useRef, useState } from 'react'
import { Copy, Download, Loader2, Sparkles, X } from 'lucide-react'
import { createPortal } from 'react-dom'
import { toast } from 'sonner'
import BrandLogo from '@/components/BrandLogo'
import ChatMarkdown from '@/components/ChatMarkdown'
import { streamChatWithDeepSeek } from '@/lib/deepseek'
import { getDeepSeekSkill } from '@/lib/deepseek-skills'
import type { WritingDocPayload } from '@/lib/chat-history'
import { downloadWritingDocx } from '@/lib/export-docx'
import { cn } from '@/lib/utils'

function extractTitle(markdown: string): string {
  const m = markdown.match(/^#{1,2}\s+(.+)$/m)
  if (m?.[1]) return m[1].trim()
  const first = markdown
    .split(/\n+/)
    .map((l) => l.replace(/^[*_#>\-\s]+/, '').trim())
    .find((l) => l.length > 0)
  return (first || '未命名文档').slice(0, 40)
}

function bodyWithoutLeadingTitle(markdown: string): string {
  return markdown.replace(/^#{1,2}\s+.+\n+/, '')
}

function toPlainParagraphs(markdown: string): string[] {
  const body = bodyWithoutLeadingTitle(markdown)
  const parts = body
    .split(/\n{2,}/)
    .map((p) =>
      p
        .replace(/^#{1,6}\s+/gm, '')
        .replace(/[*_`>#]/g, '')
        .replace(/\n+/g, ' ')
        .trim(),
    )
    .filter(Boolean)
  return parts.length ? parts : [body.trim() || '（空文档）']
}

type EditPhase = 'idle' | 'selecting' | 'rewriting' | 'done'

type WritingOverlayProps = {
  open: boolean
  /** 新写作主题 */
  topic?: string
  /** 对已有文档的修改指令，如「改成500字」 */
  reviseInstruction?: string
  initialDoc?: WritingDocPayload | null
  onClose: (doc: WritingDocPayload | null) => void
  onDocChange?: (doc: WritingDocPayload) => void
}

function sleep(ms: number, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException('Aborted', 'AbortError'))
      return
    }
    const t = window.setTimeout(() => resolve(), ms)
    const onAbort = () => {
      window.clearTimeout(t)
      reject(new DOMException('Aborted', 'AbortError'))
    }
    signal?.addEventListener('abort', onAbort, { once: true })
  })
}

/** 豆包式写作弹层：新建 / 改稿（含选中动画） */
export default function WritingOverlay({
  open,
  topic,
  reviseInstruction,
  initialDoc,
  onClose,
  onDocChange,
}: WritingOverlayProps) {
  const skill = getDeepSeekSkill('write')!
  const abortRef = useRef<AbortController | null>(null)
  const sessionKeyRef = useRef<string | null>(null)
  const createdAtRef = useRef(new Date().toISOString())
  const latestRef = useRef<WritingDocPayload>({
    title: '新文档',
    content: '',
    createdAt: createdAtRef.current,
  })
  const onDocChangeRef = useRef(onDocChange)
  onDocChangeRef.current = onDocChange
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose
  const initialDocRef = useRef(initialDoc)
  initialDocRef.current = initialDoc

  const [docTitle, setDocTitle] = useState('新文档')
  const [docContent, setDocContent] = useState('')
  const [generating, setGenerating] = useState(false)
  const [phase, setPhase] = useState<EditPhase>('idle')
  const [selectCount, setSelectCount] = useState(0)
  const [selectParagraphs, setSelectParagraphs] = useState<string[]>([])
  const [reviseHint, setReviseHint] = useState('')

  const displayBody = useMemo(() => {
    if (!docContent.trim()) return ''
    return bodyWithoutLeadingTitle(docContent)
  }, [docContent])

  const pushDoc = (title: string, content: string) => {
    const doc: WritingDocPayload = {
      title,
      content,
      createdAt: createdAtRef.current,
    }
    latestRef.current = doc
    setDocTitle(title)
    setDocContent(content)
    onDocChangeRef.current?.(doc)
  }

  useEffect(() => {
    if (open) return
    sessionKeyRef.current = null
    abortRef.current?.abort()
    abortRef.current = null
    setGenerating(false)
    setPhase('idle')
    setSelectCount(0)
    setSelectParagraphs([])
    setReviseHint('')
  }, [open])

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
      abortRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!open) return

    const t = topic?.trim()
    const revise = reviseInstruction?.trim()
    const doc = initialDocRef.current
    const sessionKey = revise
      ? `revise:${doc?.createdAt || 'x'}:${revise}`
      : t
        ? `topic:${t}`
        : doc?.createdAt
          ? `view:${doc.createdAt}`
          : null

    if (!sessionKey || sessionKeyRef.current === sessionKey) return
    sessionKeyRef.current = sessionKey

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    // 仅查看已有文档
    if (!t && !revise && doc?.content) {
      createdAtRef.current = doc.createdAt
      pushDoc(doc.title, doc.content)
      setGenerating(false)
      setPhase('idle')
      return
    }

    void (async () => {
      try {
        // —— 改稿：先展示原文 → 逐段选中 → 再流式重写 ——
        if (revise && doc?.content) {
          createdAtRef.current = doc.createdAt
          pushDoc(doc.title, doc.content)
          const paragraphs = toPlainParagraphs(doc.content)
          setSelectParagraphs(paragraphs)
          setReviseHint(revise)
          setGenerating(true)
          setPhase('selecting')

          for (let i = 0; i < paragraphs.length; i++) {
            if (controller.signal.aborted) throw new DOMException('Aborted', 'AbortError')
            setSelectCount(i + 1)
            await sleep(220 + Math.min(paragraphs[i].length, 80), controller.signal)
          }
          await sleep(360, controller.signal)

          setPhase('rewriting')
          setSelectCount(0)

          let full = ''
          const keepTitle = doc.title
          await streamChatWithDeepSeek({
            model: skill.model,
            deepThink: skill.deepThink,
            systemPrompt: `${skill.systemPrompt}

你正在根据用户修改要求改写已有文稿。保留合适的标题气质；按要求调整篇幅、语气或结构。只输出完整成稿，不要解释修改过程。`,
            messages: [
              {
                role: 'user',
                content: `【当前文稿】\n${doc.content}\n\n【修改要求】\n${revise}\n\n请输出改写后的完整文稿（第一行 # 标题，正文用段落；将作为 Word 文档交付）。`,
              },
            ],
            signal: controller.signal,
            onContentDelta: (_d, all) => {
              full = all
              pushDoc(extractTitle(all) || keepTitle, all)
            },
          })
          pushDoc(extractTitle(full) || keepTitle, full)
          setPhase('done')
          toast.success('已按要求改好')
          return
        }

        // —— 新建 ——
        if (!t) return
        const provisional =
          t.replace(/^帮我写[：:：]?\s*/i, '').slice(0, 28) || '新文档'
        createdAtRef.current = new Date().toISOString()
        pushDoc(provisional, '')
        setGenerating(true)
        setPhase('rewriting')
        setReviseHint('')

        let full = ''
        await streamChatWithDeepSeek({
          model: skill.model,
          deepThink: skill.deepThink,
          systemPrompt: skill.systemPrompt,
          messages: [{ role: 'user', content: skill.wrapUserMessage(t) }],
          signal: controller.signal,
          onContentDelta: (_d, all) => {
            full = all
            pushDoc(extractTitle(all) || provisional, all)
          },
        })
        pushDoc(extractTitle(full) || provisional, full)
        setPhase('done')
        toast.success('写作完成')
      } catch (err) {
        if ((err as Error)?.name === 'AbortError') return
        toast.error(err instanceof Error ? err.message : '写作失败')
        setPhase('idle')
      } finally {
        setGenerating(false)
        if (abortRef.current === controller) abortRef.current = null
      }
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 每次打开按会话键启动一次
  }, [open, topic, reviseInstruction, initialDoc?.createdAt])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCloseRef.current(latestRef.current)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  if (!open) return null

  const statusLabel =
    phase === 'selecting'
      ? '选中原文…'
      : phase === 'rewriting'
        ? reviseHint
          ? '改写中…'
          : '撰写中…'
        : null

  const copyDoc = async () => {
    const text = latestRef.current.content.trim()
    if (!text) {
      toast.message('还没有可复制的内容')
      return
    }
    try {
      await navigator.clipboard.writeText(text)
      toast.success('已复制全文')
    } catch {
      toast.error('复制失败')
    }
  }

  const downloadDoc = () => {
    const text = latestRef.current.content.trim()
    if (!text) {
      toast.message('还没有可下载的内容')
      return
    }
    void downloadWritingDocx(latestRef.current.title || '文档', text)
      .then(() => toast.success('已下载 Word 文档'))
      .catch(() => toast.error('下载失败'))
  }

  return createPortal(
    <div className="fixed inset-0 z-[80] flex items-stretch justify-center bg-black/45 p-0 md:p-4">
      <div className="relative flex h-full w-full max-w-5xl flex-col overflow-hidden bg-[#f7f8fa] text-[#1f2329] shadow-2xl md:rounded-2xl">
        <header className="flex items-center gap-2 border-b border-black/5 bg-white/95 px-4 py-2.5">
          <div className="min-w-0 flex-1">
            <div className="text-[12px] text-[#8b939e]">云文档 · Word</div>
            <input
              value={docTitle}
              onChange={(e) => pushDoc(e.target.value, docContent)}
              className="w-full truncate bg-transparent text-[15px] font-medium outline-none"
            />
          </div>
          {statusLabel ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-[#2f6bff] px-2.5 py-1 text-[12px] text-white">
              <Loader2 className="size-3 animate-spin" />
              {statusLabel}
            </span>
          ) : null}
          <button
            type="button"
            title="复制"
            onClick={() => void copyDoc()}
            className="inline-flex size-8 items-center justify-center rounded-lg text-[#5c6370] hover:bg-black/5 pressable"
          >
            <Copy className="size-4" />
          </button>
          <button
            type="button"
            title="下载"
            onClick={downloadDoc}
            className="inline-flex size-8 items-center justify-center rounded-lg text-[#5c6370] hover:bg-black/5 pressable"
          >
            <Download className="size-4" />
          </button>
          <button
            type="button"
            title="关闭"
            onClick={() => onClose(latestRef.current)}
            className="inline-flex size-8 items-center justify-center rounded-lg text-[#5c6370] hover:bg-black/5 pressable"
          >
            <X className="size-4" />
          </button>
        </header>

        {reviseHint ? (
          <div className="flex items-center gap-2 border-b border-[#2f6bff]/15 bg-[#2f6bff]/08 px-4 py-2 text-[13px] text-[#2f4f9a]">
            <Sparkles className="size-3.5 shrink-0 text-[#2f6bff]" />
            <span className="min-w-0 truncate">
              修改要求：{reviseHint}
              {phase === 'selecting'
                ? ` · 已选中 ${selectCount}/${Math.max(selectParagraphs.length, 1)} 段`
                : phase === 'rewriting'
                  ? ' · 正在替换选中内容'
                  : phase === 'done'
                    ? ' · 已完成改写'
                    : ''}
            </span>
          </div>
        ) : null}

        <div className="flex-1 overflow-y-auto">
          <article className="mx-auto w-full max-w-3xl px-6 py-8 md:px-10 md:py-10">
            {!docContent.trim() && generating ? (
              <div className="flex items-center justify-center gap-2 pt-20 text-[14px] text-[#8b939e]">
                <Loader2 className="size-4 animate-spin text-[#2f6bff]" />
                正在生成文档…
              </div>
            ) : !docContent.trim() ? (
              <div className="pt-20 text-center text-[14px] text-[#8b939e]">
                暂无内容
              </div>
            ) : (
              <>
                <h1 className="text-[28px] font-semibold leading-tight tracking-tight md:text-[32px]">
                  {docTitle || '未命名文档'}
                </h1>
                <div className="mb-8 mt-3 flex items-center gap-2 text-[12px] text-[#8b939e]">
                  <BrandLogo variant="icon" size={24} className="text-[#2f6bff]" />
                  <span>智流写作</span>
                  <span>·</span>
                  <span>
                    {phase === 'selecting'
                      ? '正在选中要修改的内容…'
                      : phase === 'rewriting'
                        ? '正在改写…'
                        : generating
                          ? '正在编辑…'
                          : '刚刚更新'}
                  </span>
                </div>

                {phase === 'selecting' ? (
                  <div className="space-y-4 text-[16px] leading-8 text-[#1f2329]">
                    {selectParagraphs.map((p, i) => {
                      const on = i < selectCount
                      return (
                        <p
                          key={i}
                          className={cn(
                            'rounded-sm px-1 transition-[background-color,box-shadow] duration-200',
                            on && 'writing-select-mark',
                          )}
                        >
                          {p}
                        </p>
                      )
                    })}
                  </div>
                ) : (
                  <div className="writing-doc-prose chat-prose">
                    <ChatMarkdown content={displayBody || docContent} />
                    {phase === 'rewriting' ? (
                      <span className="ml-0.5 inline-block h-4 w-1.5 align-middle animate-pulse bg-[#2f6bff]/70" />
                    ) : null}
                  </div>
                )}
              </>
            )}
          </article>
        </div>
      </div>
    </div>,
    document.body,
  )
}
