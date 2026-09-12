import { useSyncExternalStore } from 'react'
import type { ChatFileMeta } from '@/lib/chat-file'
import type { FlowchartPayload } from '@/lib/flowchart'
import { getStoredUser } from '@/lib/auth'

export type { ChatFileMeta }
export type { FlowchartPayload }

export interface ChatMessageAction {
  type: 'navigate'
  label: string
  path: string
  state?: Record<string, unknown>
}

export interface WritingDocPayload {
  title: string
  content: string
  createdAt: string
}

export interface ChatMessageRecord {
  id: string
  role: 'user' | 'assistant'
  content: string
  model?: string
  files?: ChatFileMeta[]
  thinking?: string[]
  thinkingDone?: boolean
  action?: ChatMessageAction
  /** 帮我写作：关闭写作框后在对话里展示的文档卡片 */
  writingDoc?: WritingDocPayload
  /** 流程图卡片 */
  flowchart?: FlowchartPayload
}

export interface ChatSession {
  id: string
  title: string
  updatedAt: string
  createdAt: string
  messages: ChatMessageRecord[]
  model?: string
}

const LEGACY_KEY = 'mawp-chat-history'
const MAX_SESSIONS = 40
const CHANNEL_NAME = 'mawp-chat-history-sync'

function ownerKey(): string {
  const user = getStoredUser()
  return user?.id || 'anonymous'
}

function storageKey(owner = ownerKey()): string {
  return `mawp-chat-history:${owner}`
}

/** 旧版全局历史不再共享给新账号，仅挂到原机「未迁移」桶 */
function retireLegacyGlobalHistory() {
  try {
    const raw = localStorage.getItem(LEGACY_KEY)
    if (!raw) return
    if (!localStorage.getItem(`${LEGACY_KEY}:_retired`)) {
      localStorage.setItem(`${LEGACY_KEY}:_retired`, raw)
    }
    localStorage.removeItem(LEGACY_KEY)
  } catch {
    /* ignore */
  }
}

function readAll(): ChatSession[] {
  retireLegacyGlobalHistory()
  try {
    const raw = localStorage.getItem(storageKey())
    if (!raw) return []
    const parsed = JSON.parse(raw) as ChatSession[]
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

type Listener = () => void
const listeners = new Set<Listener>()
let snapshot: ChatSession[] = []
let snapshotSig = ''
let channel: BroadcastChannel | null = null

function sortedSessions(list: ChatSession[]): ChatSession[] {
  return [...list].sort(
    (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime(),
  )
}

function signature(list: ChatSession[]): string {
  return list
    .map(
      (s) =>
        `${s.id}:${s.updatedAt}:${s.messages.length}:${s.title}:${s.model || ''}`,
    )
    .join('|')
}

/** @returns 是否有实质变化 */
function rebuildSnapshot(): boolean {
  const next = sortedSessions(readAll())
  const sig = signature(next)
  if (sig === snapshotSig) return false
  snapshot = next
  snapshotSig = sig
  return true
}

rebuildSnapshot()

function ensureChannel() {
  if (typeof window === 'undefined' || typeof BroadcastChannel === 'undefined') {
    return null
  }
  if (channel) return channel
  try {
    channel = new BroadcastChannel(CHANNEL_NAME)
    channel.onmessage = (ev) => {
      if (ev?.data?.type === 'chat-change') {
        if (rebuildSnapshot()) listeners.forEach((l) => l())
      }
    }
  } catch {
    channel = null
  }
  return channel
}

function emitListeners() {
  listeners.forEach((l) => l())
}

function notifyChatChange(opts?: { broadcast?: boolean }) {
  rebuildSnapshot()
  window.dispatchEvent(new Event('mawp-chat-change'))
  if (opts?.broadcast !== false) {
    try {
      ensureChannel()?.postMessage({ type: 'chat-change', at: Date.now() })
    } catch {
      /* ignore */
    }
  }
  emitListeners()
}

function writeAll(list: ChatSession[]) {
  localStorage.setItem(
    storageKey(),
    JSON.stringify(list.slice(0, MAX_SESSIONS)),
  )
  notifyChatChange()
}

export function listChatSessions(): ChatSession[] {
  return sortedSessions(readAll())
}

/** 供 useSyncExternalStore：引用稳定，仅在数据变化时换新数组 */
export function getChatHistorySnapshot(): ChatSession[] {
  return snapshot
}

export function subscribeChatHistory(onStoreChange: Listener): () => void {
  ensureChannel()
  listeners.add(onStoreChange)

  const refreshIfChanged = () => {
    if (rebuildSnapshot()) onStoreChange()
  }

  const onStorage = (e: StorageEvent) => {
    if (!e.key || e.key.startsWith('mawp-chat-history')) {
      refreshIfChanged()
    }
  }
  const onFocus = () => refreshIfChanged()
  const onVisible = () => {
    if (document.visibilityState === 'visible') refreshIfChanged()
  }
  // 同源自定义事件：其它旧代码仍可能只 dispatch 事件
  const onCustom = () => refreshIfChanged()

  window.addEventListener('mawp-chat-change', onCustom)
  window.addEventListener('mawp-auth-change', onCustom)
  window.addEventListener('storage', onStorage)
  window.addEventListener('focus', onFocus)
  document.addEventListener('visibilitychange', onVisible)

  const timer = window.setInterval(() => {
    if (document.visibilityState !== 'visible') return
    refreshIfChanged()
  }, 1500)

  return () => {
    listeners.delete(onStoreChange)
    window.removeEventListener('mawp-chat-change', onCustom)
    window.removeEventListener('mawp-auth-change', onCustom)
    window.removeEventListener('storage', onStorage)
    window.removeEventListener('focus', onFocus)
    document.removeEventListener('visibilitychange', onVisible)
    window.clearInterval(timer)
  }
}

/** React Hook：历史会话列表实时订阅 */
export function useChatSessions(): ChatSession[] {
  return useSyncExternalStore(
    subscribeChatHistory,
    getChatHistorySnapshot,
    () => [],
  )
}

export function getChatSession(id: string): ChatSession | null {
  return readAll().find((s) => s.id === id) ?? null
}

export function upsertChatSession(session: ChatSession) {
  const owner = ownerKey()
  if (!owner || owner === 'anonymous') return
  const existing = readAll().find((s) => s.id === session.id)
  const all = readAll().filter((s) => s.id !== session.id)
  all.unshift({
    ...session,
    createdAt: existing?.createdAt || session.createdAt,
  })
  writeAll(all)
}

export function deleteChatSession(id: string) {
  writeAll(readAll().filter((s) => s.id !== id))
}

/** 账号切换后刷新侧栏 / 对话列表 */
export function notifyChatOwnerChanged() {
  retireLegacyGlobalHistory()
  notifyChatChange({ broadcast: true })
}

export function createSessionTitle(firstUserText: string) {
  const t = firstUserText.trim().replace(/\s+/g, ' ')
  if (!t) return '新对话'
  return t.length > 24 ? `${t.slice(0, 24)}…` : t
}

export function buildThinkingSteps(
  userText: string,
  intentTitle: string,
  model: string,
  opts: { deepThink?: boolean; webSearch?: boolean; hasFiles?: boolean },
): string[] {
  const brief = userText.trim().slice(0, 22) || '当前请求'
  const steps = [
    `理解用户问题：「${brief}${userText.trim().length > 22 ? '…' : ''}」`,
    '拆解任务目标与约束条件',
    `匹配能力分区：${intentTitle}`,
    `选择推理模型：${model}`,
  ]
  if (opts.hasFiles) steps.push('解析上传附件内容，提取关键上下文')
  if (opts.webSearch) steps.push('检索联网信息并交叉验证关键事实')
  if (opts.deepThink) {
    steps.push('展开多路径推理，比较可行方案与风险')
    steps.push('评估实现成本、依赖与落地顺序')
    steps.push('收敛最优执行路径，生成可落地建议')
  } else {
    steps.push('组织回答结构，准备跳转或执行动作')
  }
  steps.push('整理结论并输出最终回复')
  return steps
}
