import { getStoredUser } from '@/lib/auth'
import type { IProject } from '@/data/projects'

const LAST_KEY = 'mawp-last-project'

function ownerKey() {
  return getStoredUser()?.id || 'anonymous'
}

function storageKey(owner = ownerKey()) {
  return `mawp-projects:${owner}`
}

function readAll(): IProject[] {
  try {
    const raw = localStorage.getItem(storageKey())
    if (!raw) return []
    const parsed = JSON.parse(raw) as IProject[]
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function writeAll(list: IProject[]) {
  localStorage.setItem(storageKey(), JSON.stringify(list))
  window.dispatchEvent(new Event('mawp-projects-change'))
}

export function listProjects(): IProject[] {
  return readAll().sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
  )
}

export function getProject(id: string): IProject | null {
  return readAll().find((p) => p.id === id) ?? null
}

export function upsertProject(project: IProject) {
  const all = readAll().filter((p) => p.id !== project.id)
  all.unshift(project)
  writeAll(all)
  setLastProjectId(project.id)
}

export function replaceProjects(projects: IProject[]) {
  writeAll(projects)
}

export function createProject(input: {
  name: string
  description?: string
  goal?: string
}): IProject {
  const project: IProject = {
    id: `p-${Date.now()}`,
    name: input.name.trim(),
    description: (input.description || '').trim(),
    goal: (input.goal || '').trim(),
    status: 'draft',
    progress: 0,
    createdAt: new Date().toISOString(),
  }
  upsertProject(project)
  return project
}

export function updateProject(
  id: string,
  patch: Partial<Omit<IProject, 'id' | 'createdAt'>>,
): IProject | null {
  const cur = getProject(id)
  if (!cur) return null
  const next = { ...cur, ...patch }
  upsertProject(next)
  return next
}

export function deleteProject(id: string) {
  writeAll(readAll().filter((p) => p.id !== id))
  if (getLastProjectId() === id) {
    localStorage.removeItem(`${LAST_KEY}:${ownerKey()}`)
  }
}

export function setLastProjectId(id: string) {
  localStorage.setItem(`${LAST_KEY}:${ownerKey()}`, id)
}

export function getLastProjectId(): string | null {
  return localStorage.getItem(`${LAST_KEY}:${ownerKey()}`)
}

/** 打开工作流：优先上次项目，否则最新项目，都没有则 null */
export function resolveWorkflowPath(): string | null {
  const last = getLastProjectId()
  if (last && getProject(last)) return `/workflow/${last}`
  const first = listProjects()[0]
  return first ? `/workflow/${first.id}` : null
}

export function notifyProjectsOwnerChanged() {
  window.dispatchEvent(new Event('mawp-projects-change'))
}
