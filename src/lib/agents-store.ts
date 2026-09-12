import { getStoredUser } from '@/lib/auth'
import { MOCK_AGENTS, type IAgent } from '@/data/agents'

function ownerKey() {
  return getStoredUser()?.id || 'anonymous'
}

function storageKey(owner = ownerKey()) {
  return `mawp-agents-custom:${owner}`
}

function readCustom(): IAgent[] {
  try {
    const raw = localStorage.getItem(storageKey())
    if (!raw) return []
    const parsed = JSON.parse(raw) as IAgent[]
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function writeCustom(list: IAgent[]) {
  localStorage.setItem(storageKey(), JSON.stringify(list))
  window.dispatchEvent(new Event('mawp-agents-change'))
}

export function listAgents(): IAgent[] {
  return [...MOCK_AGENTS, ...readCustom()]
}

export function listCustomAgents(): IAgent[] {
  return readCustom()
}

export function upsertCustomAgent(agent: IAgent) {
  const all = readCustom().filter((a) => a.id !== agent.id)
  all.unshift(agent)
  writeCustom(all)
}

export function deleteCustomAgent(id: string) {
  writeCustom(readCustom().filter((a) => a.id !== id))
}

export function getAgent(id: string): IAgent | null {
  return listAgents().find((a) => a.id === id) ?? null
}

export function notifyAgentsOwnerChanged() {
  window.dispatchEvent(new Event('mawp-agents-change'))
}
