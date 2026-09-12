import { getStoredUser } from '@/lib/auth'
import { STUDIO_ORDER, type StudioPageKind } from '@/lib/chat-intent'

const DRAFTS_BASE = 'mawp-studio-drafts'
const SEED_BASE = 'mawp-pipeline-seed'
const TOPIC_BASE = 'mawp-pipeline-topic'
const ACTIVE_BASE = 'mawp-pipeline-active'
const COMPLETED_BASE = 'mawp-pipeline-completed'
const RUN_ID_BASE = 'mawp-platform-run-id'

export type StudioDraft = {
  prompt: string
  output?: string
  done?: boolean
  isDemo?: boolean
  thinkingSteps?: string[]
  thinkingDone?: boolean
}

type DraftMap = Partial<Record<StudioPageKind, StudioDraft>>

function ownerId(): string {
  return getStoredUser()?.id || 'anonymous'
}

function scoped(base: string, owner = ownerId()): string {
  return `${base}:${owner}`
}

function readMap(): DraftMap {
  try {
    const raw = sessionStorage.getItem(scoped(DRAFTS_BASE))
    if (!raw) return {}
    const parsed = JSON.parse(raw) as DraftMap
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

function writeMap(map: DraftMap) {
  sessionStorage.setItem(scoped(DRAFTS_BASE), JSON.stringify(map))
}

export function isPipelineActive(): boolean {
  return sessionStorage.getItem(scoped(ACTIVE_BASE)) === '1'
}

export function readStudioDraft(kind: StudioPageKind): StudioDraft | null {
  if (!isPipelineActive()) return null
  return readMap()[kind] ?? null
}

export function writeStudioDraft(
  kind: StudioPageKind,
  patch: Partial<StudioDraft>,
) {
  if (!isPipelineActive()) return
  const map = readMap()
  const prev = map[kind] || { prompt: '' }
  map[kind] = { ...prev, ...patch }
  writeMap(map)
}

export function clearStudioDraft(kind: StudioPageKind) {
  const map = readMap()
  delete map[kind]
  writeMap(map)
}

export function getPipelineSeed(): string {
  if (!isPipelineActive()) return ''
  return sessionStorage.getItem(scoped(SEED_BASE)) || ''
}

export function getPipelineTopic(): string {
  if (!isPipelineActive()) return ''
  return sessionStorage.getItem(scoped(TOPIC_BASE)) || ''
}

export function readCompletedStages(): StudioPageKind[] {
  try {
    const raw = sessionStorage.getItem(scoped(COMPLETED_BASE))
    if (!raw) return []
    const parsed = JSON.parse(raw) as StudioPageKind[]
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function markStageCompleted(kind: StudioPageKind) {
  const set = new Set(readCompletedStages())
  set.add(kind)
  sessionStorage.setItem(scoped(COMPLETED_BASE), JSON.stringify([...set]))
}

export function getScopedPlatformRunId(): string | null {
  return sessionStorage.getItem(scoped(RUN_ID_BASE))
}

export function setScopedPlatformRunId(id: string | null) {
  const key = scoped(RUN_ID_BASE)
  if (id) sessionStorage.setItem(key, id)
  else sessionStorage.removeItem(key)
}

/** 开启一轮完整流程：激活保留模式，各阶段预填同一目标 */
export function startPipelineFlow(seed: string, topic?: string) {
  const text = seed.trim()
  const owner = ownerId()
  sessionStorage.setItem(scoped(ACTIVE_BASE, owner), '1')
  sessionStorage.setItem(scoped(SEED_BASE, owner), text)
  if (topic?.trim()) sessionStorage.setItem(scoped(TOPIC_BASE, owner), topic.trim())
  else sessionStorage.removeItem(scoped(TOPIC_BASE, owner))
  sessionStorage.setItem(scoped(COMPLETED_BASE, owner), JSON.stringify([]))

  const map: DraftMap = {}
  for (const kind of STUDIO_ORDER) {
    map[kind] = { prompt: text }
  }
  sessionStorage.setItem(scoped(DRAFTS_BASE, owner), JSON.stringify(map))
}

/** 非流程入口：清空当前用户各模块草稿与完成态 */
export function clearPipelineSession() {
  const owner = ownerId()
  for (const base of [
    ACTIVE_BASE,
    SEED_BASE,
    TOPIC_BASE,
    DRAFTS_BASE,
    COMPLETED_BASE,
    RUN_ID_BASE,
  ]) {
    sessionStorage.removeItem(scoped(base, owner))
  }
  // 兼容旧版未分桶键
  sessionStorage.removeItem(ACTIVE_BASE)
  sessionStorage.removeItem(SEED_BASE)
  sessionStorage.removeItem(TOPIC_BASE)
  sessionStorage.removeItem(DRAFTS_BASE)
  sessionStorage.removeItem(COMPLETED_BASE)
  sessionStorage.removeItem(RUN_ID_BASE)
}

export function resolveStagePrompt(kind: StudioPageKind): string {
  if (!isPipelineActive()) return ''
  const draft = readStudioDraft(kind)
  if (draft?.prompt?.trim()) return draft.prompt
  return getPipelineSeed()
}

/** 流程内跳转用的 location.state */
export function flowNavState() {
  return { continueFlow: true as const }
}
