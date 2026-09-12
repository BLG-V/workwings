import { getStoredUser } from '@/lib/auth'

export interface IRun {
  id: string
  projectId: string
  projectName: string
  status: 'running' | 'completed' | 'failed'
  startTime: string
  endTime?: string
  duration: string
  nodesTotal: number
  nodesCompleted: number
  logsCount: number
}

function ownerKey() {
  return getStoredUser()?.id || 'anonymous'
}

function storageKey(owner = ownerKey()) {
  return `mawp-runs:${owner}`
}

function readAll(): IRun[] {
  try {
    const raw = localStorage.getItem(storageKey())
    if (!raw) return []
    const parsed = JSON.parse(raw) as IRun[]
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function writeAll(list: IRun[]) {
  localStorage.setItem(storageKey(), JSON.stringify(list.slice(0, 100)))
  window.dispatchEvent(new Event('mawp-runs-change'))
}

export function listRuns(): IRun[] {
  return readAll().sort(
    (a, b) => new Date(b.startTime).getTime() - new Date(a.startTime).getTime(),
  )
}

export function getRun(id: string): IRun | null {
  return readAll().find((r) => r.id === id) ?? null
}

export function upsertRun(run: IRun) {
  const all = readAll().filter((r) => r.id !== run.id)
  all.unshift(run)
  writeAll(all)
}

export function removeRun(id: string) {
  writeAll(readAll().filter((r) => r.id !== id))
}

/** 同一项目只保留一条进行中的记录，避免 pending 占位和内核 Run 各一条。 */
export function replaceRunningRunForProject(projectId: string, run: IRun) {
  const kept = readAll().filter(
    (r) =>
      r.id === run.id ||
      r.projectId !== projectId ||
      r.status !== 'running',
  )
  const withoutSelf = kept.filter((r) => r.id !== run.id)
  withoutSelf.unshift(run)
  writeAll(withoutSelf)
}

export function deleteRunsForProject(projectId: string) {
  writeAll(readAll().filter((r) => r.projectId !== projectId))
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}毫秒`
  const sec = Math.round(ms / 1000)
  if (sec < 60) return `${sec}秒`
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}分${s}秒`
}

export function notifyRunsOwnerChanged() {
  window.dispatchEvent(new Event('mawp-runs-change'))
}
