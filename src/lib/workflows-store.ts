import { getStoredUser } from '@/lib/auth'
import type { IResult } from '@/data/results'
import type { IWorkflowEdge, IWorkflowNode } from '@/lib/workflow-types'

export interface StoredWorkflowLog {
  id: string
  timestamp: string
  nodeId: string
  nodeName: string
  level: 'info' | 'success' | 'warn' | 'error'
  message: string
}

export interface StoredWorkflow {
  projectId: string
  nodes: IWorkflowNode[]
  edges: IWorkflowEdge[]
  zoom: number
  pan: { x: number; y: number }
  results: IResult[]
  updatedAt: string
  kernelRunId?: string | null
  logs?: StoredWorkflowLog[]
}

function ownerKey() {
  return getStoredUser()?.id || 'anonymous'
}

function storageKey(owner = ownerKey()) {
  return `mawp-workflows:${owner}`
}

function readMap(): Record<string, StoredWorkflow> {
  try {
    const raw = localStorage.getItem(storageKey())
    if (!raw) return {}
    const parsed = JSON.parse(raw) as Record<string, StoredWorkflow>
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

function writeMap(map: Record<string, StoredWorkflow>) {
  localStorage.setItem(storageKey(), JSON.stringify(map))
  window.dispatchEvent(new Event('mawp-workflows-change'))
}

export function getWorkflow(projectId: string): StoredWorkflow | null {
  return readMap()[projectId] ?? null
}

export function saveWorkflow(input: Omit<StoredWorkflow, 'updatedAt'>) {
  const map = readMap()
  const prev = map[input.projectId]
  map[input.projectId] = {
    ...prev,
    ...input,
    kernelRunId:
      input.kernelRunId !== undefined ? input.kernelRunId : prev?.kernelRunId,
    logs: input.logs !== undefined ? input.logs : prev?.logs,
    updatedAt: new Date().toISOString(),
  }
  writeMap(map)
}

export function deleteWorkflow(projectId: string) {
  const map = readMap()
  delete map[projectId]
  writeMap(map)
}

export function notifyWorkflowsOwnerChanged() {
  window.dispatchEvent(new Event('mawp-workflows-change'))
}
