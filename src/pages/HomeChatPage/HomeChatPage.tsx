import { useEffect, useLayoutEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode, type RefObject } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ArrowUp,
  ArrowRight,
  Loader2,
  Paperclip,
  ImagePlus,
  X,
  File as FileIcon,
  Copy,
  RefreshCw,
  Pencil,
  Plus,
  Zap,
  FileText,
  Presentation,
  Image as ImageIcon,
  Mic,
  Search,
  LayoutGrid,
  PenLine,
  Podcast,
  Check,
  Boxes,
  ChevronRight,
  Globe,
  Workflow,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { resolveChatIntent } from '@/lib/chat-intent'
import {
  createSessionTitle,
  getChatSession,
  upsertChatSession,
  useChatSessions,
  type ChatMessageRecord,
  type ChatFileMeta,
} from '@/lib/chat-history'
import { getStoredUser } from '@/lib/auth'
import {
  DEEPSEEK_MODELS,
  streamChatWithDeepSeek,
  reasoningToSteps,
  type DeepSeekModelId,
} from '@/lib/deepseek'
import { searchWeb } from '@/lib/web-search'
import {
  getDeepSeekSkill,
  type DeepSeekSkillId,
} from '@/lib/deepseek-skills'
import {
  EXTERNAL_SKILL_META,
  runExternalSkill,
  type ExternalSkillId,
} from '@/lib/skill-runners'
import { buildAttachmentPrompt, buildFileMeta } from '@/lib/file-utils'
import { clearPipelineSession } from '@/lib/studio-session'
import ThinkingProcess from '@/components/ThinkingProcess'
import ChatMarkdown from '@/components/ChatMarkdown'
import BrandLogo from '@/components/BrandLogo'
import TechFrame from '@/components/TechFrame'
import VoiceInputBar from '@/components/VoiceInputBar'
import LoginGateDialog from '@/components/LoginGateDialog'
import WritingOverlay from '@/components/WritingOverlay'
import WritingDocCard from '@/components/WritingDocCard'
import GeneratedImageFrame from '@/components/GeneratedImageFrame'
import FlowchartCard from '@/components/FlowchartCard'
import FlowchartOverlay from '@/components/FlowchartOverlay'
import { useAuth } from '@/hooks/use-auth'
import { resolveHotDirections } from '@/lib/hot-directions'
import { TencentVoiceSession, getVoiceInputUnavailableReason } from '@/lib/tencent-asr'
import { toast } from 'sonner'
import type { WritingDocPayload, FlowchartPayload } from '@/lib/chat-history'

interface AttachedFile {
  id: string
  file: File
  meta?: ChatFileMeta
}

const MODELS = DEEPSEEK_MODELS

const REPLY_MODES = [
  {
    id: 'fast',
    label: '极速',
    icon: Zap,
    deepThink: false,
    model: 'deepseek-v4-flash' as DeepSeekModelId,
  },
  {
    id: 'expert',
    label: '专家',
    icon: Boxes,
    deepThink: true,
    model: 'deepseek-v4-flash' as DeepSeekModelId,
  },
  {
    id: 'turbo',
    label: '工作任务 Turbo',
    icon: PenLine,
    deepThink: true,
    model: 'deepseek-v4-flash' as DeepSeekModelId,
  },
  {
    id: 'pro',
    label: '工作任务 Pro',
    icon: PenLine,
    deepThink: true,
    model: 'deepseek-v4-flash' as DeepSeekModelId,
    badge: '深度思考',
  },
] as const

type ReplyModeId = (typeof REPLY_MODES)[number]['id']

/** 挂到 body，避开输入框层叠上下文覆盖 */
function AnchoredMenu({
  open,
  anchorRef,
  align = 'left',
  className,
  children,
}: {
  open: boolean
  anchorRef: RefObject<HTMLElement | null>
  align?: 'left' | 'right'
  className?: string
  children: ReactNode
}) {
  const [style, setStyle] = useState<CSSProperties>({
    position: 'fixed',
    top: 0,
    left: 0,
    visibility: 'hidden',
  })

  useLayoutEffect(() => {
    if (!open || !anchorRef.current) return
    const place = () => {
      const r = anchorRef.current!.getBoundingClientRect()
      const gap = 8
      setStyle({
        position: 'fixed',
        bottom: window.innerHeight - r.top + gap,
        ...(align === 'right'
          ? { right: window.innerWidth - r.right }
          : { left: r.left }),
        zIndex: 300,
        visibility: 'visible',
      })
    }
    place()
    window.addEventListener('resize', place)
    window.addEventListener('scroll', place, true)
    return () => {
      window.removeEventListener('resize', place)
      window.removeEventListener('scroll', place, true)
    }
  }, [open, anchorRef, align])

  if (!open) return null
  return createPortal(
    <div data-composer-menu className={className} style={style}>
      {children}
    </div>,
    document.body,
  )
}

type SkillChipId = DeepSeekSkillId | ExternalSkillId

type SkillChip = {
  id: SkillChipId
  label: string
  icon: typeof PenLine
  /** DeepSeek：写作链路 */
  deepseekSkill?: DeepSeekSkillId
  /** 其他模型/引擎 */
  externalSkill?: ExternalSkillId
}

/** 输入栏主技能（联网搜索单独渲染，紧跟其后是需求分析） */
const RAIL_SKILLS: SkillChip[] = [
  {
    id: 'req',
    label: '需求分析',
    icon: FileText,
    deepseekSkill: 'req',
  },
  {
    id: 'write',
    label: '帮我写作',
    icon: PenLine,
    deepseekSkill: 'write',
  },
  {
    id: 'ppt',
    label: 'PPT 生成',
    icon: Presentation,
    externalSkill: 'ppt',
  },
  {
    id: 'flowchart',
    label: '流程图',
    icon: Workflow,
    externalSkill: 'flowchart',
  },
]

/** 「更多」里的次要技能 */
const MORE_SKILLS: SkillChip[] = [
  {
    id: 'image',
    label: '图像生成',
    icon: ImageIcon,
    externalSkill: 'image',
  },
  {
    id: 'research',
    label: '深入研究',
    icon: Search,
    externalSkill: 'research',
  },
  {
    id: 'podcast',
    label: 'AI 播客',
    icon: Podcast,
    externalSkill: 'podcast',
  },
]

function toastSkillEnabled(label: string) {
  toast.success(`已开启${label}`)
}

function toastSkillDisabled(label: string) {
  toast.success(`已关闭${label}`)
}

function clearSkillPrefix(current: string, prefix: string) {
  const t = current.trim()
  if (!prefix) return current
  if (t === prefix.trim() || t.startsWith(prefix)) {
    return ''
  }
  return current
}

function formatSize(size: number) {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

/** 是否像对写作文档的改稿指令 */
function looksLikeWritingRevision(text: string) {
  return /改|修改|精简|扩写|润色|重写|缩短|加长|字数|删掉|删去|换成|调整|润一下|再写|再改|压缩|扩充|更短|更长|简短|详细|\d+\s*字|字以内|字左右|五百|一千/.test(
    text,
  )
}

function findLatestWritingMessage(messages: ChatMessageRecord[]) {
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i]
    if (m.writingDoc?.content?.trim()) return m
  }
  return null
}

function findWritingReviseTarget(
  messages: ChatMessageRecord[],
  text: string,
): ChatMessageRecord | null {
  const latest = findLatestWritingMessage(messages)
  if (!latest?.writingDoc?.content?.trim()) return null
  if (looksLikeWritingRevision(text)) return latest

  // 紧跟写作跟进问句时，短指令也视为改稿
  const last = messages[messages.length - 1]
  if (
    last?.id === latest.id &&
    /修改要求|精简字数|再改一版|继续调整/.test(last.content || '') &&
    text.trim().length > 0 &&
    text.trim().length <= 80
  ) {
    return latest
  }
  return null
}

export default function HomeChatPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { isLoggedIn } = useAuth()
  const sessions = useChatSessions()
  const hotDirections = useMemo(
    () => resolveHotDirections(sessions, { limit: 8 }),
    [sessions],
  )
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMessageRecord[]>([])
  const [thinking, setThinking] = useState(false)
  const [liveThinking, setLiveThinking] = useState<string[]>([])
  const [thinkingWithDeep, setThinkingWithDeep] = useState(false)
  const [model, setModel] = useState<DeepSeekModelId>('deepseek-v4-flash')
  const [attachments, setAttachments] = useState<AttachedFile[]>([])
  const [webSearch, setWebSearch] = useState(false)
  const [deepThink, setDeepThink] = useState(false)
  const [replyMode, setReplyMode] = useState<ReplyModeId>('fast')
  const [activeSkillId, setActiveSkillId] = useState<SkillChipId | null>(null)
  const [modeOpen, setModeOpen] = useState(false)
  const [plusOpen, setPlusOpen] = useState(false)
  const [moreOpen, setMoreOpen] = useState(false)
  const [streamingId, setStreamingId] = useState<string | null>(null)
  /** 流式结束后延迟露出「前往」按钮，避免误触跳页 */
  const [revealedActionIds, setRevealedActionIds] = useState<string[]>([])
  const [loginGateOpen, setLoginGateOpen] = useState(false)
  const [chatKey, setChatKey] = useState(0)
  const [sessionId, setSessionId] = useState(() => `s-${Date.now()}`)
  const listRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const imageRef = useRef<HTMLInputElement>(null)
  const skillRailRef = useRef<HTMLDivElement>(null)
  const plusBtnRef = useRef<HTMLButtonElement>(null)
  const modeBtnRef = useRef<HTMLButtonElement>(null)
  const moreBtnRef = useRef<HTMLButtonElement>(null)
  const timersRef = useRef<number[]>([])
  const abortRef = useRef<AbortController | null>(null)
  const scrollRafRef = useRef<number | null>(null)
  const stickToBottomRef = useRef(true)
  /** 用户主动上滑后锁定，直到回到底部附近才恢复跟随 */
  const userDetachedRef = useRef(false)
  const touchYRef = useRef(0)
  const [voiceOpen, setVoiceOpen] = useState(false)
  const [voiceTranscript, setVoiceTranscript] = useState('')
  const [voiceLevel, setVoiceLevel] = useState(0)
  const [voiceBusy, setVoiceBusy] = useState(false)
  const voiceSessionRef = useRef<TencentVoiceSession | null>(null)
  const spaceHoldRef = useRef(false)
  /** 豆包式写作弹层 */
  const [writingOpen, setWritingOpen] = useState(false)
  const [writingTopic, setWritingTopic] = useState<string | undefined>()
  const [writingRevise, setWritingRevise] = useState<string | undefined>()
  const [writingDoc, setWritingDoc] = useState<WritingDocPayload | null>(null)
  const [writingMsgId, setWritingMsgId] = useState<string | null>(null)
  const [flowchartOpen, setFlowchartOpen] = useState(false)
  const [flowchartDoc, setFlowchartDoc] = useState<FlowchartPayload | null>(null)
  const [flowchartMsgId, setFlowchartMsgId] = useState<string | null>(null)

  const clearTimers = () => {
    timersRef.current.forEach((id) => window.clearTimeout(id))
    timersRef.current = []
  }

  const abortOngoing = () => {
    abortRef.current?.abort()
    abortRef.current = null
    clearTimers()
  }

  const persist = (nextMessages: ChatMessageRecord[], sid = sessionId, modelName?: string) => {
    if (nextMessages.length === 0) return
    if (!getStoredUser()?.id) return
    const firstWithText = nextMessages.find(
      (m) => m.role === 'user' && m.content.trim(),
    )?.content
    const hasImageOnly = nextMessages.some(
      (m) => m.role === 'user' && (m.files?.some((f) => f.previewUrl) ?? false),
    )
    const firstUser = firstWithText || (hasImageOnly ? '图片对话' : '新对话')
    // dataUrl 过大时不写入 localStorage，避免配额爆掉；当前会话内存里仍可看图
    const forStore = nextMessages.map((m) => ({
      ...m,
      files: m.files?.map((f) => {
        const url = f.previewUrl || ''
        if (url.startsWith('data:') && url.length > 180_000) {
          return { ...f, previewUrl: undefined }
        }
        return f
      }),
    }))
    upsertChatSession({
      id: sid,
      title: createSessionTitle(firstUser),
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      messages: forStore,
      model: modelName,
    })
  }

  const startNewChat = () => {
    abortOngoing()
    clearPipelineSession()
    setMessages([])
    setRevealedActionIds([])
    stickToBottomRef.current = true
    setInput('')
    setAttachments([])
    setThinking(false)
    setLiveThinking([])
    setStreamingId(null)
    setWebSearch(false)
    setDeepThink(false)
    setThinkingWithDeep(false)
    setSessionId(`s-${Date.now()}`)
    setChatKey((k) => k + 1)
    inputRef.current?.focus()
    toast.success('已开启新对话')
  }

  useEffect(() => {
    const el = skillRailRef.current
    if (!el) return

    const onWheel = (e: WheelEvent) => {
      // 鼠标滚轮 / 触控板：把纵向滚动转成横向滑动
      if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
        el.scrollLeft += e.deltaY
        e.preventDefault()
      } else {
        el.scrollLeft += e.deltaX
      }
    }

    let dragging = false
    let moved = false
    let startX = 0
    let startScroll = 0
    let activePointer: number | null = null

    const isInteractive = (target: EventTarget | null) => {
      const node = target as HTMLElement | null
      return Boolean(
        node?.closest?.(
          'button, a, input, textarea, select, label, [role="button"]',
        ),
      )
    }

    const onPointerDown = (e: PointerEvent) => {
      if (e.button !== 0) return
      // 点在技能按钮上：绝不抢点击
      if (isInteractive(e.target)) return
      dragging = true
      moved = false
      activePointer = e.pointerId
      startX = e.clientX
      startScroll = el.scrollLeft
    }
    const onPointerMove = (e: PointerEvent) => {
      if (!dragging || activePointer !== e.pointerId) return
      const dx = e.clientX - startX
      if (Math.abs(dx) <= 8) return
      if (!moved) {
        moved = true
        try {
          el.setPointerCapture(e.pointerId)
        } catch {
          /* ignore */
        }
      }
      el.scrollLeft = startScroll - dx
    }
    const endDrag = (e: PointerEvent) => {
      if (activePointer !== null && e.pointerId !== activePointer) return
      dragging = false
      activePointer = null
      // 下一帧再清 moved，避免同一次手势的 click 被误触
      if (moved) {
        window.setTimeout(() => {
          moved = false
        }, 0)
      }
    }
    const onClickCapture = (e: MouseEvent) => {
      if (!moved) return
      // 仅拦截「拖动产生的误点击」，不拦正常点按
      if (isInteractive(e.target) && Math.abs(e.clientX - startX) <= 8) {
        moved = false
        return
      }
      e.preventDefault()
      e.stopPropagation()
      moved = false
    }

    el.addEventListener('wheel', onWheel, { passive: false })
    el.addEventListener('pointerdown', onPointerDown)
    el.addEventListener('pointermove', onPointerMove)
    el.addEventListener('pointerup', endDrag)
    el.addEventListener('pointercancel', endDrag)
    el.addEventListener('click', onClickCapture, true)
    return () => {
      el.removeEventListener('wheel', onWheel)
      el.removeEventListener('pointerdown', onPointerDown)
      el.removeEventListener('pointermove', onPointerMove)
      el.removeEventListener('pointerup', endDrag)
      el.removeEventListener('pointercancel', endDrag)
      el.removeEventListener('click', onClickCapture, true)
    }
  }, [chatKey])

  useEffect(() => {
    let ownerId = getStoredUser()?.id || 'anonymous'
    const onAuth = () => {
      const nextId = getStoredUser()?.id || 'anonymous'
      if (nextId === ownerId) return
      ownerId = nextId
      abortOngoing()
      setMessages([])
      setRevealedActionIds([])
      stickToBottomRef.current = true
      setInput('')
      setAttachments([])
      setThinking(false)
      setLiveThinking([])
      setWebSearch(false)
      setDeepThink(false)
      setThinkingWithDeep(false)
      setSessionId(`s-${Date.now()}`)
      setChatKey((k) => k + 1)
    }
    window.addEventListener('mawp-auth-change', onAuth)
    return () => window.removeEventListener('mawp-auth-change', onAuth)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const state = location.state as {
      newChat?: number
      resumeSessionId?: string
    } | null
    if (state?.newChat) {
      startNewChat()
      navigate('/chat', { replace: true, state: {} })
      return
    }
    if (state?.resumeSessionId) {
      const session = getChatSession(state.resumeSessionId)
      if (session) {
        abortOngoing()
        setSessionId(session.id)
        setMessages(session.messages)
        setRevealedActionIds(
          session.messages.filter((m) => m.action).map((m) => m.id),
        )
        setChatKey((k) => k + 1)
        setThinking(false)
        setLiveThinking([])
        setThinkingWithDeep(false)
        toast.success(`已恢复：${session.title}`)
      }
      navigate('/chat', { replace: true, state: {} })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state])

  const queueScrollToBottom = () => {
    if (userDetachedRef.current || !stickToBottomRef.current) return
    if (scrollRafRef.current != null) return
    scrollRafRef.current = window.requestAnimationFrame(() => {
      scrollRafRef.current = null
      if (userDetachedRef.current || !stickToBottomRef.current) return
      const el = listRef.current
      if (!el) return
      // 瞬时贴底，避免 smooth 叠动画导致一卡一卡
      el.scrollTop = el.scrollHeight
    })
  }

  useEffect(() => {
    queueScrollToBottom()
  }, [messages, thinking, liveThinking])

  useEffect(() => {
    const el = listRef.current
    if (!el) return

    const BOTTOM_GAP = 140

    const syncStickFromScroll = () => {
      const distance = el.scrollHeight - el.scrollTop - el.clientHeight
      const nearBottom = distance < BOTTOM_GAP
      stickToBottomRef.current = nearBottom
      if (nearBottom) userDetachedRef.current = false
    }

    const onWheel = (e: WheelEvent) => {
      if (e.deltaY < -2) {
        // 用户往上看：立刻停止跟随，允许自由浏览历史
        userDetachedRef.current = true
        stickToBottomRef.current = false
      } else if (e.deltaY > 2) {
        const distance = el.scrollHeight - el.scrollTop - el.clientHeight
        if (distance < BOTTOM_GAP) {
          userDetachedRef.current = false
          stickToBottomRef.current = true
        }
      }
    }

    const onTouchStart = (e: TouchEvent) => {
      touchYRef.current = e.touches[0]?.clientY ?? 0
      const distance = el.scrollHeight - el.scrollTop - el.clientHeight
      if (distance > BOTTOM_GAP) {
        userDetachedRef.current = true
        stickToBottomRef.current = false
      }
    }

    const onTouchMove = (e: TouchEvent) => {
      const y = e.touches[0]?.clientY ?? 0
      const dy = y - touchYRef.current
      touchYRef.current = y
      // 手指下拖 → 内容上移，用户在看历史
      if (dy > 6) {
        userDetachedRef.current = true
        stickToBottomRef.current = false
      }
    }

    el.addEventListener('scroll', syncStickFromScroll, { passive: true })
    el.addEventListener('wheel', onWheel, { passive: true })
    el.addEventListener('touchstart', onTouchStart, { passive: true })
    el.addEventListener('touchmove', onTouchMove, { passive: true })
    syncStickFromScroll()
    return () => {
      el.removeEventListener('scroll', syncStickFromScroll)
      el.removeEventListener('wheel', onWheel)
      el.removeEventListener('touchstart', onTouchStart)
      el.removeEventListener('touchmove', onTouchMove)
      if (scrollRafRef.current) {
        window.cancelAnimationFrame(scrollRafRef.current)
        scrollRafRef.current = null
      }
    }
  }, [])

  useEffect(() => () => abortOngoing(), [])

  useEffect(() => {
    if (!plusOpen && !modeOpen && !moreOpen) return
    const onDoc = (e: MouseEvent) => {
      const t = e.target as HTMLElement | null
      if (!t?.closest?.('[data-composer-menu]')) {
        setPlusOpen(false)
        setModeOpen(false)
        setMoreOpen(false)
      }
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [plusOpen, modeOpen, moreOpen])

  const modelLabel = MODELS.find((m) => m.id === model)?.label ?? model

  const addFiles = async (list: FileList | null) => {
    if (!list?.length) return
    if (!isLoggedIn) {
      setLoginGateOpen(true)
      return
    }
    const next: AttachedFile[] = []
    for (const file of Array.from(list)) {
      if (file.size > 20 * 1024 * 1024) {
        toast.error(`${file.name} 超过 20MB，已跳过`)
        continue
      }
      try {
        const meta = await buildFileMeta(file)
        next.push({
          id: `${file.name}-${file.size}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
          file,
          meta,
        })
      } catch {
        toast.error(`${file.name} 读取失败`)
      }
    }
    if (next.length) {
      setAttachments((prev) => [...prev, ...next].slice(0, 8))
      toast.success(`已添加 ${next.length} 个文件`)
    }
  }

  const removeFile = (id: string) => {
    setAttachments((prev) => prev.filter((f) => f.id !== id))
  }

  const copyText = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      toast.success('已复制')
    } catch {
      toast.error('复制失败')
    }
  }

  const editUserMessage = (content: string) => {
    setInput(content)
    inputRef.current?.focus()
    toast.success('已填入输入框，可修改后发送')
  }

  /** 从该条用户消息重新生成：截断其后内容并再请求 */
  const regenerateFromUser = (userMsgId: string) => {
    if (thinking) return
    const idx = messages.findIndex((m) => m.id === userMsgId)
    if (idx < 0) return
    const target = messages[idx]
    if (target.role !== 'user') return
    void send(target.content, { historyOverride: messages.slice(0, idx) })
  }

  /** 对某条助手回复重载：找到其前一条用户消息再生成 */
  const regenerateAssistant = (assistantMsgId: string) => {
    if (thinking) return
    const idx = messages.findIndex((m) => m.id === assistantMsgId)
    if (idx <= 0) return
    let userIdx = idx - 1
    while (userIdx >= 0 && messages[userIdx].role !== 'user') userIdx -= 1
    if (userIdx < 0) return
    regenerateFromUser(messages[userIdx].id)
  }

  const send = async (
    raw: string,
    opts?: {
      historyOverride?: ChatMessageRecord[]
      skillId?: DeepSeekSkillId | null
      externalSkillId?: ExternalSkillId | null
    },
  ) => {
    const text = raw.trim()
    if ((!text && attachments.length === 0) || thinking) return

    if (!isLoggedIn) {
      setLoginGateOpen(true)
      return
    }

    // 帮我写作：弹写作框，不走普通对话气泡流式
    const writeSkillId =
      opts && 'skillId' in opts ? opts.skillId : activeSkillId
    if (writeSkillId === 'write') {
      startWritingFlow(text)
      return
    }

    // 已有写作文档时，改稿指令重新弹出写作框（选中 → 改写）
    const reviseTarget = findWritingReviseTarget(messages, text)
    if (reviseTarget) {
      startWritingReviseFlow(
        text,
        reviseTarget.id,
        reviseTarget.writingDoc!,
      )
      return
    }

    // 外部技能：不走 DeepSeek
    const externalId =
      opts && 'externalSkillId' in opts
        ? opts.externalSkillId
        : activeSkillId && activeSkillId in EXTERNAL_SKILL_META
          ? (activeSkillId as ExternalSkillId)
          : null

    if (externalId) {
      const meta = EXTERNAL_SKILL_META[externalId]
      const topic = text || meta.label
      const pendingFiles = attachments.map((a) => a.file)
      const pendingMeta: ChatFileMeta[] = attachments.map(
        (a) =>
          a.meta || {
            name: a.file.name,
            size: a.file.size,
            type: a.file.type,
            kind: 'file' as const,
          },
      )
      setActiveSkillId(null)
      setInput('')
      setAttachments([])
      userDetachedRef.current = false
      stickToBottomRef.current = true
      const userMsg: ChatMessageRecord = {
        id: `u-${Date.now()}`,
        role: 'user',
        content: `「${meta.label}」${topic}`,
        model: meta.providerHint,
        files: pendingMeta.length ? pendingMeta : undefined,
      }
      setMessages((prev) => {
        const next = [...prev, userMsg]
        persist(next, sessionId, meta.providerHint)
        stickToBottomRef.current = true
        return next
      })
      setThinking(true)
      setThinkingWithDeep(false)
      setLiveThinking([
        externalId === 'flowchart'
          ? pendingFiles.length
            ? '正在读取附件并用 DeepSeek 生成流程图…'
            : '正在用 DeepSeek 生成流程图…'
          : `正在用 ${meta.providerHint} 执行「${meta.label}」…`,
      ])
      try {
        const result = await runExternalSkill(externalId, topic, {
          files: pendingFiles,
        })
        const assistantId = `a-${Date.now()}`
        const assistantMsg: ChatMessageRecord = {
          id: assistantId,
          role: 'assistant',
          content: result.content,
          model: result.provider,
          thinking:
            externalId === 'flowchart'
              ? [`提供方：${result.provider}`, 'DeepSeek 结构化出图']
              : [`提供方：${result.provider}`, '未调用 DeepSeek'],
          thinkingDone: true,
          files: result.images?.map((img, i) => ({
            name: `${img.alt || 'image'}-${i + 1}.png`,
            size: 0,
            type: 'image/png',
            kind: 'image' as const,
            previewUrl: img.url,
          })),
          flowchart: result.flowchart,
        }
        setMessages((prev) => {
          const next = [...prev, assistantMsg]
          persist(next, sessionId, result.provider)
          stickToBottomRef.current = true
          return next
        })
        if (result.flowchart) {
          setFlowchartMsgId(assistantId)
          setFlowchartDoc(result.flowchart)
          setFlowchartOpen(true)
        }
        toast.success(`${meta.label}完成（${result.provider}）`)
      } catch (err) {
        const message = err instanceof Error ? err.message : '技能执行失败'
        toast.error(message)
        const assistantMsg: ChatMessageRecord = {
          id: `a-${Date.now()}`,
          role: 'assistant',
          content: `「${meta.label}」执行失败：${message}`,
          model: meta.providerHint,
        }
        setMessages((prev) => {
          const next = [...prev, assistantMsg]
          persist(next, sessionId, meta.providerHint)
          stickToBottomRef.current = true
          return next
        })
      } finally {
        setThinking(false)
        setLiveThinking([])
        setThinkingWithDeep(false)
      }
      return
    }

    const pending = [...attachments]
    const fileMeta: ChatFileMeta[] = pending.map(
      (a) =>
        a.meta || {
          name: a.file.name,
          size: a.file.size,
          type: a.file.type,
          kind: 'file' as const,
        },
    )
    const imageCount = fileMeta.filter((f) => f.kind === 'image').length
    const displayRaw = text
    const skill = getDeepSeekSkill(
      opts && 'skillId' in opts ? opts.skillId : activeSkillId,
    )
    const display = displayRaw
    const apiFallback =
      display ||
      (imageCount > 0
        ? `用户上传了 ${imageCount} 张图片，请结合附件说明协助。`
        : fileMeta.length
          ? `用户上传了 ${fileMeta.length} 个文件，请结合附件说明协助。`
          : '')

    const attachmentPrompt = await buildAttachmentPrompt(
      pending.map((p) => p.file),
      fileMeta,
    )
    const skillWrapped =
      skill && apiFallback
        ? skill.wrapUserMessage(apiFallback)
        : apiFallback
    const apiUserContent = [skillWrapped, attachmentPrompt].filter(Boolean).join('\n\n')

    const baseMessages = opts?.historyOverride ?? messages

    const userMsg: ChatMessageRecord = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: skill
        ? `【${skill.label}】${display || apiFallback}`
        : display,
      files: fileMeta,
      model: modelLabel,
    }

    const historyForApi = [...baseMessages, userMsg]
      .filter((m) => m.role === 'user' || m.role === 'assistant')
      .map((m, i, arr) => {
        const isLastUser =
          m.role === 'user' && i === arr.length - 1 && m.id === userMsg.id
        return {
          role: m.role as 'user' | 'assistant',
          content: isLastUser ? apiUserContent : m.content,
        }
      })
      .slice(-16)

    setMessages(() => {
      const next = [...baseMessages, userMsg]
      persist(next, sessionId, modelLabel)
      userDetachedRef.current = false
      stickToBottomRef.current = true
      return next
    })
    setInput('')
    setAttachments([])
    const skillUsed = skill
    setActiveSkillId(null)

    const modeAtSend =
      REPLY_MODES.find((m) => m.id === replyMode) ?? REPLY_MODES[0]
    const useDeepThink = skillUsed?.deepThink ?? modeAtSend.deepThink
    // 聊天统一 DeepSeek V4 Flash；技能可自带模型
    const useModel: DeepSeekModelId = skillUsed?.model ?? 'deepseek-v4-flash'
    const resultModelLabel =
      DEEPSEEK_MODELS.find((m) => m.id === useModel)?.label ?? useModel
    const intent = skillUsed
      ? { kind: 'chat' as const, title: '', path: '', reply: '' }
      : resolveChatIntent(display || apiFallback)

    abortOngoing()
    const controller = new AbortController()
    abortRef.current = controller

    const assistantId = `a-${Date.now()}`
    setStreamingId(assistantId)
    setThinking(true)
    setThinkingWithDeep(useDeepThink)
    setLiveThinking(
      useDeepThink
        ? [
            skillUsed
              ? `技能「${skillUsed.label}」·深度思考中…`
              : '正在连接 DeepSeek，启动深度思考…',
          ]
        : skillUsed
          ? [`技能「${skillUsed.label}」·正在调用 DeepSeek…`]
          : [],
    )

    // 先插入空助手气泡，流式写入
    setMessages((prev) => [
      ...prev,
      {
        id: assistantId,
        role: 'assistant' as const,
        content: '',
        model: resultModelLabel,
        ...(useDeepThink
          ? {
              thinking: [
                skillUsed
                  ? `技能「${skillUsed.label}」·深度思考中…`
                  : '正在深度思考…',
              ],
              thinkingDone: false,
            }
          : {}),
      },
    ])

    const patchAssistant = (patch: Partial<ChatMessageRecord>) => {
      setMessages((prev) =>
        prev.map((m) => (m.id === assistantId ? { ...m, ...patch } : m)),
      )
    }

    try {
      let reasoningFull = ''
      let contentFull = ''
      let sawContent = false
      let apiMessages = historyForApi
      let contentFlushTimer: number | null = null
      let reasoningFlushTimer: number | null = null

      const flushContent = (force = false) => {
        if (force && contentFlushTimer != null) {
          window.clearTimeout(contentFlushTimer)
          contentFlushTimer = null
        }
        if (!force && contentFlushTimer != null) return
        const run = () => {
          contentFlushTimer = null
          patchAssistant({ content: contentFull })
          queueScrollToBottom()
        }
        if (force) run()
        else contentFlushTimer = window.setTimeout(run, 72)
      }

      const flushReasoning = (steps: string[], force = false) => {
        if (force && reasoningFlushTimer != null) {
          window.clearTimeout(reasoningFlushTimer)
          reasoningFlushTimer = null
        }
        if (!force && reasoningFlushTimer != null) return
        const run = () => {
          reasoningFlushTimer = null
          setLiveThinking(steps)
          patchAssistant({
            thinking: steps,
            thinkingDone: false,
          })
          queueScrollToBottom()
        }
        if (force) run()
        else reasoningFlushTimer = window.setTimeout(run, 100)
      }

      if (webSearch) {
        const searchHint = '正在联网检索相关资料…'
        setLiveThinking((prev) =>
          useDeepThink ? [searchHint, ...prev] : [searchHint],
        )
        if (useDeepThink) {
          patchAssistant({
            thinking: [searchHint, '检索完成后开始推理…'],
            thinkingDone: false,
          })
        }
        try {
          const sr = await searchWeb(display || apiFallback, {
            signal: controller.signal,
            count: 8,
          })
          apiMessages = historyForApi.map((m, i, arr) => {
            if (i === arr.length - 1 && m.role === 'user') {
              return {
                ...m,
                content: `${m.content}\n\n【联网检索结果｜请优先依据下列资料作答；涉及天气/时效信息请引用摘要并给出数据来源链接；不要编造未出现的数字】\n${sr.contextText}`,
              }
            }
            return m
          })
          const found = `联网检索完成，共 ${sr.hits.length} 条结果`
          setLiveThinking((prev) =>
            useDeepThink ? [found, ...prev.filter((s) => s !== searchHint)] : [found],
          )
          if (useDeepThink) {
            patchAssistant({
              thinking: [found, '基于检索结果深度思考中…'],
              thinkingDone: false,
            })
          }
        } catch (searchErr) {
          if ((searchErr as Error)?.name === 'AbortError') throw searchErr
          const msg =
            searchErr instanceof Error ? searchErr.message : '联网搜索失败'
          toast.error(msg)
          apiMessages = historyForApi.map((m, i, arr) => {
            if (i === arr.length - 1 && m.role === 'user') {
              return {
                ...m,
                content: `${m.content}\n\n【联网检索失败：${msg}。请明确告知用户检索未成功，并建议其稍后重试或改用天气 App。】`,
              }
            }
            return m
          })
        }
      }

      const result = await streamChatWithDeepSeek({
        model: useModel,
        messages: apiMessages,
        deepThink: useDeepThink,
        signal: controller.signal,
        systemPrompt: skillUsed?.systemPrompt,
        onReasoningDelta: (_delta, full) => {
          reasoningFull = full
          const steps = reasoningToSteps(full)
          const nextSteps =
            steps.length > 0
              ? steps
              : [full.trim().slice(-280) || '正在深度思考…']
          flushReasoning(nextSteps)
        },
        onContentDelta: (_delta, full) => {
          contentFull = full
          if (!sawContent) {
            sawContent = true
            // 正文开始后收起「思考中」态，保留思考步骤
            if (useDeepThink) {
              const steps =
                reasoningToSteps(reasoningFull).length > 0
                  ? reasoningToSteps(reasoningFull)
                  : reasoningFull.trim()
                    ? [reasoningFull.trim().slice(0, 400)]
                    : ['已完成推理，正在生成回答…']
              if (reasoningFlushTimer != null) {
                window.clearTimeout(reasoningFlushTimer)
                reasoningFlushTimer = null
              }
              patchAssistant({
                thinking: steps,
                thinkingDone: true,
                content: full,
              })
              setThinkingWithDeep(false)
              setLiveThinking([])
              queueScrollToBottom()
              return
            }
          }
          flushContent()
        },
      })

      if (contentFlushTimer != null) {
        window.clearTimeout(contentFlushTimer)
        contentFlushTimer = null
      }
      if (reasoningFlushTimer != null) {
        window.clearTimeout(reasoningFlushTimer)
        reasoningFlushTimer = null
      }

      let thinkingSteps = useDeepThink
        ? reasoningToSteps(result.reasoning || reasoningFull)
        : skillUsed
          ? [`已用 DeepSeek 完成「${skillUsed.label}」`, `模型：${result.model}`]
          : webSearch
            ? ['已完成联网检索并生成回答', `模型：${result.model}`]
            : []

      if (useDeepThink && thinkingSteps.length === 0) {
        thinkingSteps = [
          '已启用 DeepSeek 深度思考模式',
          `模型：${result.model}`,
          '已完成推理并生成回答',
        ]
      }

      // 流式结束后留在本页；绝不自动 navigate。仅在明确进工作台意图时挂「前往」按钮。
      const content = (result.content || contentFull).trim()
      const navigateAction =
        intent.kind !== 'chat'
          ? {
              type: 'navigate' as const,
              label: `前往「${intent.title}」`,
              path: intent.path,
              state: {
                prompt: display,
                topic: intent.topic,
                fromChat: true,
                model: resultModelLabel,
                files: fileMeta,
              },
            }
          : undefined

      const finalized: ChatMessageRecord = {
        id: assistantId,
        role: 'assistant',
        content,
        model: resultModelLabel,
        ...(thinkingSteps.length
          ? { thinking: thinkingSteps, thinkingDone: true }
          : {}),
        ...(navigateAction ? { action: navigateAction } : {}),
      }

      setMessages((prev) => {
        const next = prev.map((m) => (m.id === assistantId ? finalized : m))
        persist(next, sessionId, resultModelLabel)
        // 答完后关闭贴底，方便从回答开头往下读，避免被滚走
        stickToBottomRef.current = false
        return next
      })

      if (navigateAction) {
        // 延迟露出按钮，避免流结束瞬间误触「前往」导致跳页
        const tid = window.setTimeout(() => {
          setRevealedActionIds((prev) => {
            if (prev.includes(assistantId)) return prev
            return [...prev, assistantId]
          })
          toast.message(`可前往「${intent.title}」`, {
            description: '回答可继续阅读；需要时再点回复下方按钮',
          })
        }, 900)
        timersRef.current.push(tid)
      }
    } catch (err) {
      if ((err as Error)?.name === 'AbortError') {
        setMessages((prev) => prev.filter((m) => m.id !== assistantId || m.content.trim()))
        return
      }
      const message =
        err instanceof Error ? err.message : '调用 DeepSeek 失败'
      toast.error(message)
      const assistantMsg: ChatMessageRecord = {
        id: assistantId,
        role: 'assistant',
        content: `抱歉，模型调用失败：${message}\n\n请确认已配置 DEEPSEEK_API_KEY，并重启了开发服务器。`,
        model: resultModelLabel,
      }
      setMessages((prev) => {
        const next = prev.map((m) => (m.id === assistantId ? assistantMsg : m))
        persist(next, sessionId, modelLabel)
        stickToBottomRef.current = true
        return next
      })
    } finally {
      setThinking(false)
      setLiveThinking([])
      setThinkingWithDeep(false)
      setStreamingId(null)
      abortRef.current = null
    }
  }

  const currentMode =
    REPLY_MODES.find((m) => m.id === replyMode) ?? REPLY_MODES[0]

  const selectReplyMode = (id: ReplyModeId) => {
    const mode = REPLY_MODES.find((m) => m.id === id)
    if (!mode) return
    setReplyMode(id)
    setDeepThink(mode.deepThink)
    setModel(mode.model)
    setModeOpen(false)
    toast.success(`已切换为「${mode.label}」`)
  }

  const applySkill = (chip: SkillChip) => {
    if (!isLoggedIn) {
      setLoginGateOpen(true)
      return
    }

    // 再次点击同一能力 → 关闭
    if (activeSkillId === chip.id) {
      const label =
        chip.externalSkill
          ? EXTERNAL_SKILL_META[chip.externalSkill].label
          : chip.deepseekSkill
            ? getDeepSeekSkill(chip.deepseekSkill)?.label || chip.label
            : chip.label
      const prefix = chip.externalSkill
        ? EXTERNAL_SKILL_META[chip.externalSkill].promptPrefix
        : chip.deepseekSkill === 'write'
          ? '帮我写：'
          : getDeepSeekSkill(chip.deepseekSkill)?.promptPrefix || ''
      setActiveSkillId(null)
      setInput((prev) => clearSkillPrefix(prev, prefix))
      toastSkillDisabled(label)
      return
    }

    // 外部技能
    if (chip.externalSkill) {
      const meta = EXTERNAL_SKILL_META[chip.externalSkill]
      setActiveSkillId(chip.externalSkill)
      const topic = input.trim()
      if (topic && !topic.startsWith(meta.promptPrefix)) {
        toast.success(`正在用 ${meta.providerHint} 执行「${meta.label}」`)
        void send(topic, { externalSkillId: chip.externalSkill })
        return
      }
      setInput(meta.promptPrefix)
      inputRef.current?.focus()
      toastSkillEnabled(meta.label)
      return
    }

    // DeepSeek 写作：点技能只准备输入；发出消息时再弹写作框
    const skillId = chip.deepseekSkill
    if (skillId === 'write') {
      setActiveSkillId('write')
      setModel('deepseek-v4-flash')
      const topic = input.trim()
      if (topic && !topic.startsWith('帮我写')) {
        void startWritingFlow(topic)
        return
      }
      setInput('帮我写：')
      inputRef.current?.focus()
      toastSkillEnabled('帮我写作')
      return
    }

    const skill = skillId ? getDeepSeekSkill(skillId) : null
    if (!skill) {
      toast.message('该技能暂未接入')
      return
    }

    setActiveSkillId(skill.id)
    setModel(skill.model)
    setDeepThink(skill.deepThink)
    if (skill.deepThink) {
      setReplyMode((prev) => (prev === 'fast' ? 'expert' : prev))
    }

    const topic = input.trim()
    if (topic && !topic.startsWith(skill.promptPrefix)) {
      toast.success(`正在用 DeepSeek 执行「${skill.label}」`)
      void send(topic, { skillId: skill.id })
      return
    }

    setInput(skill.promptPrefix)
    inputRef.current?.focus()
    toastSkillEnabled(skill.label)
  }

  const startWritingFlow = (topicRaw: string) => {
    if (!isLoggedIn) {
      setLoginGateOpen(true)
      return
    }
    const topic = topicRaw.trim()
    if (!topic) return

    const userId = `u-${Date.now()}`
    const assistantId = `a-${Date.now()}`
    const createdAt = new Date().toISOString()
    const provisionalTitle =
      topic.replace(/^帮我写[：:：]?\s*/i, '').slice(0, 28) || '未命名文档'

    const userMsg: ChatMessageRecord = {
      id: userId,
      role: 'user',
      content: topic,
      model: 'DeepSeek V4 Flash',
    }
    const assistantMsg: ChatMessageRecord = {
      id: assistantId,
      role: 'assistant',
      content: '',
      model: 'DeepSeek V4 Flash',
      writingDoc: {
        title: provisionalTitle,
        content: '',
        createdAt,
      },
    }

    setMessages((prev) => {
      const next = [...prev, userMsg, assistantMsg]
      persist(next, sessionId, 'DeepSeek V4 Flash')
      stickToBottomRef.current = true
      return next
    })
    setInput('')
    setActiveSkillId(null)
    setWritingMsgId(assistantId)
    setWritingDoc({
      title: provisionalTitle,
      content: '',
      createdAt,
    })
    setWritingTopic(topic)
    setWritingRevise(undefined)
    setWritingOpen(true)
  }

  const startWritingReviseFlow = (
    instructionRaw: string,
    _prevMsgId: string,
    doc: WritingDocPayload,
  ) => {
    if (!isLoggedIn) {
      setLoginGateOpen(true)
      return
    }
    const instruction = instructionRaw.trim()
    if (!instruction || !doc.content.trim()) return

    const userId = `u-${Date.now()}`
    const assistantId = `a-${Date.now()}`
    const createdAt = new Date().toISOString()
    // 新版本卡片挂在本次用户消息下方，不覆盖旧文档卡片
    const nextDoc: WritingDocPayload = {
      title: doc.title,
      content: doc.content,
      createdAt,
    }

    const userMsg: ChatMessageRecord = {
      id: userId,
      role: 'user',
      content: instruction,
      model: 'DeepSeek V4 Flash',
    }
    const assistantMsg: ChatMessageRecord = {
      id: assistantId,
      role: 'assistant',
      content: '',
      model: 'DeepSeek V4 Flash',
      writingDoc: nextDoc,
    }

    setMessages((prev) => {
      const next = [...prev, userMsg, assistantMsg]
      persist(next, sessionId, 'DeepSeek V4 Flash')
      stickToBottomRef.current = true
      return next
    })
    setInput('')
    setActiveSkillId(null)
    setWritingMsgId(assistantId)
    setWritingDoc(nextDoc)
    setWritingTopic(undefined)
    setWritingRevise(instruction)
    setWritingOpen(true)
  }

  const openWritingFromCard = (msgId: string, doc: WritingDocPayload) => {
    setWritingMsgId(msgId)
    setWritingDoc(doc)
    setWritingTopic(undefined)
    setWritingRevise(undefined)
    setWritingOpen(true)
  }

  const closeWritingOverlay = (doc: WritingDocPayload | null) => {
    const wasRevise = Boolean(writingRevise)
    setWritingOpen(false)
    setWritingTopic(undefined)
    setWritingRevise(undefined)
    if (!doc || !writingMsgId) {
      setWritingMsgId(null)
      setWritingDoc(null)
      return
    }
    const followUp = wasRevise
      ? '已按你的要求改好了。还要继续调整字数或语气的话，直接说即可。'
      : '需要我帮你精简字数，或按场景再改一版吗？直接说修改要求即可。'
    setMessages((prev) => {
      const next = prev.map((m) =>
        m.id === writingMsgId
          ? {
              ...m,
              content: followUp,
              writingDoc: {
                title: doc.title || '未命名文档',
                content: doc.content,
                createdAt: doc.createdAt,
              },
            }
          : m,
      )
      persist(next, sessionId, 'DeepSeek V4 Flash')
      return next
    })
    setWritingMsgId(null)
    setWritingDoc(null)
  }

  const patchWritingDoc = (doc: WritingDocPayload) => {
    setWritingDoc(doc)
    if (!writingMsgId) return
    setMessages((prev) => {
      const next = prev.map((m) =>
        m.id === writingMsgId ? { ...m, writingDoc: doc } : m,
      )
      persist(next, sessionId, 'DeepSeek V4 Flash')
      return next
    })
  }

  const closeVoiceUi = () => {
    setVoiceOpen(false)
    setVoiceTranscript('')
    setVoiceLevel(0)
    setVoiceBusy(false)
    spaceHoldRef.current = false
  }

  const startVoiceInput = async () => {
    if (voiceOpen || voiceSessionRef.current) return

    const micBlock = getVoiceInputUnavailableReason()
    if (micBlock) {
      toast.error(micBlock)
      return
    }

    // 先立刻弹 UI + 开麦（保持用户手势链），文案直接「请开始说话」
    setVoiceOpen(true)
    setVoiceBusy(false)
    setVoiceTranscript('')
    setVoiceLevel(0)

    const session = new TencentVoiceSession({
      onReady: () => setVoiceBusy(false),
      onPartial: (text) => setVoiceTranscript(text),
      onLevel: (lv) => setVoiceLevel(lv),
      onError: (message) => {
        toast.error(message)
        void voiceSessionRef.current?.cancel()
        voiceSessionRef.current = null
        closeVoiceUi()
      },
    })
    voiceSessionRef.current = session

    try {
      await session.start()
    } catch (err) {
      const msg =
        err instanceof Error
          ? err.message
          : '无法启动语音输入（请允许麦克风权限）'
      toast.error(msg)
      voiceSessionRef.current = null
      closeVoiceUi()
    }
  }

  const cancelVoiceInput = async () => {
    const session = voiceSessionRef.current
    voiceSessionRef.current = null
    await session?.cancel()
    closeVoiceUi()
  }

  const confirmVoiceInput = async (opts?: { autoSend?: boolean }) => {
    const session = voiceSessionRef.current
    voiceSessionRef.current = null
    setVoiceBusy(true)
    let text = ''
    try {
      text = ((await session?.finish()) || voiceTranscript).trim()
    } catch (err) {
      closeVoiceUi()
      toast.error(err instanceof Error ? err.message : '语音识别失败')
      return
    }
    closeVoiceUi()
    if (!text) {
      toast.message('没有识别到内容', {
        description:
          '请大声说 2～3 秒，确认波形明显跳动后再点发送；并检查系统默认麦克风',
      })
      return
    }
    if (opts?.autoSend) {
      void send(text)
    } else {
      setInput((prev) => (prev.trim() ? `${prev.trim()} ${text}` : text))
      inputRef.current?.focus()
    }
  }

  useEffect(() => {
    return () => {
      void voiceSessionRef.current?.cancel()
      voiceSessionRef.current = null
    }
  }, [])

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void send(input)
      return
    }
    // 输入框为空时按住空格 → 语音输入
    if (
      e.code === 'Space' &&
      !e.repeat &&
      !input.trim() &&
      !voiceOpen &&
      !e.ctrlKey &&
      !e.metaKey &&
      !e.altKey
    ) {
      e.preventDefault()
      spaceHoldRef.current = true
      void startVoiceInput()
    }
  }

  const onKeyUp = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.code === 'Space' && spaceHoldRef.current) {
      e.preventDefault()
      spaceHoldRef.current = false
      void confirmVoiceInput({ autoSend: false })
    }
  }

  const canSend = Boolean(input.trim() || attachments.length) && !thinking
  const empty = messages.length === 0

  return (
    <div key={chatKey} className="relative flex h-[calc(100vh-0px)] min-h-[640px] flex-col">
      <div ref={listRef} className="flex-1 overflow-y-auto px-4 md:px-8 pt-4">
        <div className="mx-auto w-full max-w-3xl pb-6">
          {empty ? (
            <div className="pt-[10vh] text-center">
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35 }}
              >
                <BrandLogo
                  variant="icon"
                  size={80}
                  className="mx-auto mb-5 drop-shadow-sm"
                />
                <h1 className="font-display text-3xl md:text-4xl font-semibold tracking-tight text-foreground">
                  你好，今天想推进哪一步？
                </h1>
                <p className="mt-3 text-sm text-muted-foreground">
                  上传资料或直接说需求；选「专家」可看思考过程，回复均为流式输出
                </p>
              </motion.div>

              <div className="mt-12 mx-auto max-w-2xl">
                <div className="mb-4 flex items-center justify-center gap-2 text-[11px] tracking-[0.14em] uppercase text-muted-foreground">
                  <span className="h-px w-8 bg-border" />
                  开始方向
                  <span className="h-px w-8 bg-border" />
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                  {hotDirections.map((item, i) => (
                    <motion.button
                      key={item.id}
                      type="button"
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.04 * i, duration: 0.35 }}
                      whileHover={{ y: -3 }}
                      whileTap={{ scale: 0.98 }}
                      onClick={() => void send(item.prompt)}
                      className="group relative overflow-hidden rounded-2xl border border-border/80 bg-card/55 px-3 py-3 text-left backdrop-blur-sm pressable hover:border-primary/35 hover:bg-card/90 hover:shadow-[0_10px_28px_hsl(var(--background)/0.45)]"
                    >
                      <span
                        aria-hidden
                        className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100"
                        style={{
                          background:
                            'linear-gradient(120deg, transparent 30%, hsl(var(--primary) / 0.08) 50%, transparent 70%)',
                        }}
                      />
                      <span className="relative flex items-center gap-2">
                        <span className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-muted/70 text-muted-foreground transition-colors group-hover:bg-primary/12 group-hover:text-primary">
                          <item.icon className="size-3.5" />
                        </span>
                        <span className="min-w-0">
                          <span className="block text-[10px] text-muted-foreground">
                            {item.hint}
                          </span>
                          <span className="block truncate text-[13px] font-medium text-foreground/90 group-hover:text-primary">
                            {item.label}
                          </span>
                        </span>
                      </span>
                    </motion.button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-5 pt-4">
              <AnimatePresence initial={false}>
                {messages.map((msg) => (
                  <motion.div
                    key={msg.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    {msg.role === 'user' ? (
                      <div className="max-w-[85%] group flex flex-col items-end gap-1.5">
                        {msg.files && msg.files.some((f) => f.previewUrl) && (
                          <div className="flex flex-wrap justify-end gap-2">
                            {msg.files
                              .filter((f) => f.previewUrl)
                              .map((f) => (
                                <a
                                  key={`${f.name}-${f.size}`}
                                  href={f.previewUrl}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="block"
                                >
                                  <img
                                    src={f.previewUrl}
                                    alt={f.name}
                                    className="max-h-64 max-w-[280px] rounded-2xl object-contain"
                                  />
                                </a>
                              ))}
                          </div>
                        )}
                        {msg.files &&
                          msg.files.some((f) => !f.previewUrl) && (
                            <div className="flex flex-wrap justify-end gap-1.5">
                              {msg.files
                                .filter((f) => !f.previewUrl)
                                .map((f) => (
                                  <span
                                    key={`${f.name}-${f.size}`}
                                    className="inline-flex items-center gap-1 rounded-md bg-muted px-2 py-0.5 text-[11px] text-muted-foreground"
                                  >
                                    <FileIcon className="size-3" />
                                    {f.name}
                                  </span>
                                ))}
                            </div>
                          )}
                        {msg.content.trim() ? (
                          <div className="chat-bubble-user">
                            {msg.content}
                          </div>
                        ) : null}
                        <div className="flex items-center gap-0.5 opacity-70 transition-opacity group-hover:opacity-100">
                          <button
                            type="button"
                            title="复制"
                            disabled={thinking || !msg.content.trim()}
                            onClick={() => void copyText(msg.content)}
                            className="inline-flex size-7 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground pressable disabled:opacity-40"
                          >
                            <Copy className="size-3.5" />
                          </button>
                          <button
                            type="button"
                            title="重新生成"
                            disabled={thinking}
                            onClick={() => regenerateFromUser(msg.id)}
                            className="inline-flex size-7 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground pressable disabled:opacity-40"
                          >
                            <RefreshCw className="size-3.5" />
                          </button>
                          <button
                            type="button"
                            title="编辑"
                            disabled={thinking || !msg.content.trim()}
                            onClick={() => editUserMessage(msg.content)}
                            className="inline-flex size-7 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground pressable disabled:opacity-40"
                          >
                            <Pencil className="size-3.5" />
                          </button>
                        </div>
                      </div>
                    ) : msg.writingDoc ? (
                      <div className="w-full max-w-[720px] space-y-3 group">
                        <div className="text-[12px] text-muted-foreground">
                          智流 · {msg.model || 'DeepSeek V4 Flash'}
                        </div>
                        <WritingDocCard
                          doc={msg.writingDoc}
                          onOpen={() =>
                            openWritingFromCard(msg.id, msg.writingDoc!)
                          }
                        />
                        {msg.content.trim() ? (
                          <div className="chat-bubble-assistant chat-bubble-doubao text-[14px]">
                            <ChatMarkdown content={msg.content} />
                          </div>
                        ) : writingOpen && writingMsgId === msg.id ? (
                          <div className="text-[13px] text-muted-foreground">
                            正在写作框中生成文档…
                          </div>
                        ) : null}
                      </div>
                    ) : msg.flowchart ? (
                      <div className="w-full max-w-[720px] space-y-3 group">
                        <div className="text-[12px] text-muted-foreground">
                          智流 · {msg.model || '流程图'}
                        </div>
                        <FlowchartCard
                          doc={msg.flowchart}
                          onOpen={() => {
                            setFlowchartMsgId(msg.id)
                            setFlowchartDoc(msg.flowchart!)
                            setFlowchartOpen(true)
                          }}
                        />
                        {msg.content.trim() ? (
                          <div className="chat-bubble-assistant chat-bubble-doubao text-[14px]">
                            <ChatMarkdown content={msg.content} />
                          </div>
                        ) : null}
                      </div>
                    ) : (
                      <div className="w-full max-w-[720px] space-y-3 group">
                        <div className="text-[12px] text-muted-foreground">
                          智流 · {msg.model}
                        </div>
                        {(msg.thinking?.length ?? 0) > 0 && (
                          <ThinkingProcess
                            steps={msg.thinking!}
                            done={Boolean(msg.thinkingDone)}
                            defaultOpen={
                              streamingId === msg.id && !msg.thinkingDone
                            }
                            prominent
                          />
                        )}
                        {msg.files && msg.files.some((f) => f.previewUrl) ? (
                          <div className="flex flex-col gap-2">
                            {msg.files
                              .filter((f) => f.previewUrl)
                              .map((f) => (
                                <GeneratedImageFrame
                                  key={`${f.name}-${f.previewUrl}`}
                                  src={f.previewUrl}
                                  alt={f.name.replace(/\.\w+$/, '')}
                                />
                              ))}
                          </div>
                        ) : null}
                        {(msg.content.trim() || streamingId === msg.id) && (
                          <div className="relative chat-bubble-assistant chat-bubble-doubao">
                            <div className="absolute right-2 top-2 z-10 flex items-center gap-0.5 rounded-lg bg-background/80 p-0.5 opacity-0 shadow-sm backdrop-blur-sm transition-opacity group-hover:opacity-100">
                              <button
                                type="button"
                                title="复制回答"
                                onClick={() => void copyText(msg.content)}
                                className="inline-flex size-7 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground pressable"
                              >
                                <Copy className="size-3.5" />
                              </button>
                              <button
                                type="button"
                                title="重新生成"
                                disabled={thinking}
                                onClick={() => regenerateAssistant(msg.id)}
                                className="inline-flex size-7 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground pressable disabled:opacity-40"
                              >
                                <RefreshCw className="size-3.5" />
                              </button>
                            </div>
                            <div className="pr-16">
                              {msg.content.trim() ? (
                                <ChatMarkdown content={msg.content} />
                              ) : (
                                <div className="flex items-center gap-2 text-[13px] text-muted-foreground">
                                  <Loader2 className="size-3.5 animate-spin text-primary" />
                                  {msg.thinking?.length
                                    ? '思考完成后将开始回答…'
                                    : '智流回复中…'}
                                </div>
                              )}
                              {streamingId === msg.id && msg.content.trim() ? (
                                <span className="inline-block w-1.5 h-4 ml-0.5 align-middle bg-primary/70 animate-pulse" />
                              ) : null}
                            </div>
                            {msg.action &&
                            streamingId !== msg.id &&
                            revealedActionIds.includes(msg.id) ? (
                              <div className="mt-3 pt-3 border-t border-border/40">
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="pressable"
                                  onClick={() =>
                                    navigate(msg.action!.path, {
                                      state: msg.action!.state as Record<
                                        string,
                                        unknown
                                      >,
                                    })
                                  }
                                >
                                  <ArrowRight className="size-3.5 mr-1.5" />
                                  {msg.action.label}
                                </Button>
                              </div>
                            ) : null}
                          </div>
                        )}
                      </div>
                    )}
                  </motion.div>
                ))}
              </AnimatePresence>
              {thinking && !streamingId && (
                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex justify-start"
                >
                  {thinkingWithDeep ? (
                    <div className="max-w-[92%] w-full space-y-2">
                      <div className="flex items-center gap-2 text-xs font-medium text-primary px-0.5">
                        <Loader2 className="size-3.5 animate-spin" />
                        智流深度思考中
                      </div>
                      <ThinkingProcess
                        steps={
                          liveThinking.length
                            ? liveThinking
                            : ['正在理解你的问题…']
                        }
                        done={false}
                        prominent
                      />
                    </div>
                  ) : (
                    <div className="max-w-[85%] chat-bubble-assistant chat-bubble-doubao">
                      <div className="flex items-center gap-2 text-[13px] text-muted-foreground">
                        <Loader2 className="size-3.5 animate-spin text-primary" />
                        智流回复中…
                      </div>
                    </div>
                  )}
                </motion.div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="relative px-4 md:px-8 pb-5 pt-3">
        <div className={cn('mx-auto w-full max-w-3xl', voiceOpen && 'invisible pointer-events-none')}>
          <TechFrame
            className="rounded-[28px] tech-frame--composer"
            intensity="strong"
            contentClassName="chat-composer"
          >
            <div
              onDragOver={(e) => {
                e.preventDefault()
                e.stopPropagation()
              }}
              onDrop={(e) => {
                e.preventDefault()
                e.stopPropagation()
                void addFiles(e.dataTransfer.files)
              }}
            >
            {attachments.length > 0 && (
              <div className="flex flex-wrap gap-2 px-1 pb-2">
                {attachments.map((item) => (
                  <div
                    key={item.id}
                    className="group relative overflow-hidden rounded-xl border border-border bg-muted/50"
                  >
                    {item.meta?.previewUrl ? (
                      <div className="relative">
                        <img
                          src={item.meta.previewUrl}
                          alt={item.file.name}
                          className="h-20 w-20 object-cover"
                        />
                        <button
                          type="button"
                          onClick={() => removeFile(item.id)}
                          className="absolute right-1 top-1 rounded-full bg-black/55 p-0.5 text-white hover:bg-black/75 pressable"
                        >
                          <X className="size-3.5" />
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2 px-2.5 py-1.5 text-xs">
                        <FileIcon className="size-3.5 text-primary shrink-0" />
                        <div className="min-w-0">
                          <div className="truncate max-w-[140px] font-medium">
                            {item.file.name}
                          </div>
                          <div className="text-[10px] text-muted-foreground">
                            {formatSize(item.file.size)}
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => removeFile(item.id)}
                          className="rounded-full p-0.5 text-muted-foreground hover:bg-card hover:text-foreground pressable"
                        >
                          <X className="size-3.5" />
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              onKeyUp={onKeyUp}
              onPaste={(e) => {
                const files = e.clipboardData?.files
                if (files?.length) void addFiles(files)
              }}
              rows={2}
              placeholder={
                activeSkillId
                  ? activeSkillId in EXTERNAL_SKILL_META
                    ? `${EXTERNAL_SKILL_META[activeSkillId as ExternalSkillId].label}：补充主题后回车`
                    : `${getDeepSeekSkill(activeSkillId)?.label || '写作'}：补充主题后回车（DeepSeek）`
                  : '发消息或按住空格说话…'
              }
              className="w-full resize-none bg-transparent px-2 py-2 text-[15px] outline-none placeholder:text-muted-foreground"
            />

            <div className="flex items-center gap-2 pt-1">
              <div className="relative shrink-0" data-composer-menu>
                <button
                  ref={plusBtnRef}
                  type="button"
                  onClick={() => {
                    setPlusOpen((v) => !v)
                    setModeOpen(false)
                    setMoreOpen(false)
                  }}
                  className="inline-flex size-8 items-center justify-center rounded-full text-muted-foreground hover:bg-muted pressable"
                  title="添加"
                >
                  <Plus className="size-5" />
                </button>
                <AnchoredMenu
                  open={plusOpen}
                  anchorRef={plusBtnRef}
                  className="min-w-[150px] rounded-xl border border-border bg-popover text-popover-foreground p-1.5 shadow-lg"
                >
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-[13px] text-popover-foreground hover:bg-muted pressable"
                    onClick={() => {
                      setPlusOpen(false)
                      fileRef.current?.click()
                    }}
                  >
                    <Paperclip className="size-4 text-muted-foreground" />
                    上传文件
                  </button>
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-[13px] text-popover-foreground hover:bg-muted pressable"
                    onClick={() => {
                      setPlusOpen(false)
                      imageRef.current?.click()
                    }}
                  >
                    <ImagePlus className="size-4 text-muted-foreground" />
                    上传图片
                  </button>
                </AnchoredMenu>
              </div>

              <div className="h-4 w-px shrink-0 bg-border" />

              {/* 极速/专家：Portal 弹出 */}
              <div className="relative shrink-0" data-composer-menu>
                <button
                  ref={modeBtnRef}
                  type="button"
                  onClick={() => {
                    setModeOpen((v) => !v)
                    setPlusOpen(false)
                    setMoreOpen(false)
                  }}
                  className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1.5 text-[12px] pressable ${
                    modeOpen
                      ? 'bg-muted text-foreground'
                      : 'text-muted-foreground hover:bg-muted'
                  }`}
                >
                  <currentMode.icon className="size-3.5 opacity-80" />
                  <span>{currentMode.label}</span>
                  <ChevronRight className="size-3 opacity-50" />
                </button>
                <AnchoredMenu
                  open={modeOpen}
                  anchorRef={modeBtnRef}
                  className="w-[220px] rounded-2xl border border-border bg-popover text-popover-foreground p-1.5 shadow-xl"
                >
                  {REPLY_MODES.map((mode) => {
                    const selected = mode.id === replyMode
                    return (
                      <button
                        key={mode.id}
                        type="button"
                        onClick={() => selectReplyMode(mode.id)}
                        className="flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2.5 text-left text-popover-foreground hover:bg-muted pressable"
                      >
                        <mode.icon className="size-4 shrink-0 text-muted-foreground" />
                        <span className="min-w-0 flex-1 text-[13px] text-popover-foreground">
                          {mode.label}
                          {'badge' in mode && mode.badge ? (
                            <span className="ml-1.5 inline-flex rounded-full bg-primary px-1.5 py-0.5 text-[10px] leading-none text-primary-foreground align-middle">
                              {mode.badge}
                            </span>
                          ) : null}
                        </span>
                        {selected ? (
                          <Check className="size-4 shrink-0 text-foreground" />
                        ) : (
                          <span className="size-4 shrink-0" />
                        )}
                      </button>
                    )
                  })}
                </AnchoredMenu>
              </div>

              <div
                ref={skillRailRef}
                className="flex min-w-0 flex-1 items-center gap-0.5 overflow-x-auto overscroll-x-contain pb-0.5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden touch-pan-x cursor-grab active:cursor-grabbing select-none"
              >
                <button
                  type="button"
                  title={webSearch ? '已开启联网搜索' : '点击开启联网搜索'}
                  onClick={() => {
                    const next = !webSearch
                    setWebSearch(next)
                    toast.success(next ? '已开启联网搜索' : '已关闭联网搜索')
                  }}
                  className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2.5 py-1.5 text-[12px] pressable ${
                    webSearch
                      ? 'bg-primary/15 text-primary'
                      : 'text-muted-foreground hover:bg-muted'
                  }`}
                >
                  <Globe className="size-3.5 opacity-80" />
                  <span>联网搜索</span>
                </button>

                {RAIL_SKILLS.map((chip) => {
                  const active = activeSkillId === chip.id
                  return (
                    <button
                      key={chip.id}
                      type="button"
                      title={active ? `已开启${chip.label}，点击关闭` : `点击开启${chip.label}`}
                      onClick={() => applySkill(chip)}
                      className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2.5 py-1.5 text-[12px] pressable ${
                        active
                          ? 'bg-primary/15 text-primary'
                          : 'text-muted-foreground hover:bg-muted'
                      }`}
                    >
                      <chip.icon className="size-3.5 opacity-80" />
                      <span>{chip.label}</span>
                    </button>
                  )
                })}
              </div>

              {/* 更多：深入研究 / AI 播客 + 模型 */}
              <div className="relative shrink-0" data-composer-menu>
                <button
                  ref={moreBtnRef}
                  type="button"
                  onClick={() => {
                    setMoreOpen((v) => !v)
                    setModeOpen(false)
                    setPlusOpen(false)
                  }}
                  className="inline-flex items-center gap-1 rounded-full px-2.5 py-1.5 text-[12px] text-muted-foreground hover:bg-muted pressable"
                >
                  <LayoutGrid className="size-3.5 opacity-80" />
                  更多
                </button>
                <AnchoredMenu
                  open={moreOpen}
                  anchorRef={moreBtnRef}
                  align="right"
                  className="w-[220px] rounded-2xl border border-border bg-popover text-popover-foreground p-1.5 shadow-xl"
                >
                  <div className="px-2.5 py-1.5 text-[11px] text-muted-foreground">技能</div>
                  {MORE_SKILLS.map((chip) => {
                    const active = activeSkillId === chip.id
                    return (
                      <button
                        key={chip.id}
                        type="button"
                        onClick={() => {
                          setMoreOpen(false)
                          applySkill(chip)
                        }}
                        className={`flex w-full items-center gap-2 rounded-xl px-2.5 py-2 text-left text-[13px] text-popover-foreground hover:bg-muted pressable ${
                          active ? 'text-primary' : ''
                        }`}
                      >
                        <chip.icon className="size-4 shrink-0 text-muted-foreground" />
                        <span className="flex-1">{chip.label}</span>
                        {active ? <Check className="size-3.5" /> : null}
                      </button>
                    )
                  })}
                  <div className="my-1 border-t border-border/60" />
                  <div className="px-2.5 py-1.5 text-[11px] text-muted-foreground">模型</div>
                  {MODELS.map((m) => (
                    <button
                      key={m.id}
                      type="button"
                      onClick={() => {
                        setModel(m.id)
                        setMoreOpen(false)
                        toast.success(`已切换 ${m.label}`)
                      }}
                      className="flex w-full items-center justify-between rounded-xl px-2.5 py-2 text-left text-[13px] text-popover-foreground hover:bg-muted pressable"
                    >
                      <span>{m.label}</span>
                      {model === m.id ? (
                        <Check className="size-3.5 text-foreground" />
                      ) : null}
                    </button>
                  ))}
                </AnchoredMenu>
              </div>

              {canSend ? (
                <Button
                  size="icon"
                  className="size-9 shrink-0 rounded-full pressable"
                  onClick={() => void send(input)}
                >
                  <ArrowUp className="size-4" />
                </Button>
              ) : (
                <button
                  type="button"
                  title={
                    getVoiceInputUnavailableReason() ??
                    '语音输入（也可在空输入时按住空格）'
                  }
                  onClick={() => void startVoiceInput()}
                  className="inline-flex size-9 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground hover:bg-muted/80 pressable"
                >
                  <Mic className="size-4" />
                </button>
              )}
            </div>
            </div>
          </TechFrame>
        </div>

        <VoiceInputBar
          open={voiceOpen}
          transcript={voiceTranscript}
          level={voiceLevel}
          busy={voiceBusy}
          onCancel={() => void cancelVoiceInput()}
          onConfirm={() => void confirmVoiceInput({ autoSend: true })}
        />
      </div>

      <input
        ref={fileRef}
        type="file"
        className="hidden"
        multiple
        accept=".pdf,.doc,.docx,.txt,.md,.csv,.json,.xlsx,.pptx,.zip"
        onChange={(e) => {
          addFiles(e.target.files)
          e.target.value = ''
        }}
      />
      <input
        ref={imageRef}
        type="file"
        className="hidden"
        multiple
        accept="image/*"
        onChange={(e) => {
          addFiles(e.target.files)
          e.target.value = ''
        }}
      />
      <LoginGateDialog open={loginGateOpen} onOpenChange={setLoginGateOpen} />
      <WritingOverlay
        open={writingOpen}
        topic={writingTopic}
        reviseInstruction={writingRevise}
        initialDoc={writingTopic && !writingRevise ? null : writingDoc}
        onClose={closeWritingOverlay}
        onDocChange={patchWritingDoc}
      />
      <FlowchartOverlay
        open={flowchartOpen}
        initial={flowchartDoc}
        onClose={(doc) => {
          setFlowchartOpen(false)
          if (doc && flowchartMsgId) {
            setMessages((prev) => {
              const next = prev.map((m) =>
                m.id === flowchartMsgId ? { ...m, flowchart: doc } : m,
              )
              persist(next, sessionId, 'DeepSeek V4 Flash · 流程图')
              return next
            })
            setFlowchartDoc(doc)
          }
        }}
      />
    </div>
  )
}
