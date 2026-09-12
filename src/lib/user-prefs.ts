import { getStoredUser } from '@/lib/auth'

export interface WorkspacePrefs {
  name: string
  defaultModel: string
  apiKey: string
}

export interface NotificationPrefs {
  done: boolean
  fail: boolean
  agent: boolean
  email: boolean
}

export interface AppearancePrefs {
  animationOn: boolean
}

export interface UserPrefs {
  workspace: WorkspacePrefs
  notifications: NotificationPrefs
  appearance: AppearancePrefs
}

const DEFAULTS: UserPrefs = {
  workspace: {
    name: '智流工作空间',
    defaultModel: 'deepseek-v4-flash',
    apiKey: '',
  },
  notifications: {
    done: true,
    fail: true,
    agent: false,
    email: true,
  },
  appearance: {
    animationOn: true,
  },
}

function ownerKey() {
  return getStoredUser()?.id || 'anonymous'
}

function storageKey(owner = ownerKey()) {
  return `mawp-user-prefs:${owner}`
}

export function getUserPrefs(): UserPrefs {
  try {
    const raw = localStorage.getItem(storageKey())
    if (!raw) return structuredClone(DEFAULTS)
    const parsed = JSON.parse(raw) as Partial<UserPrefs>
    return {
      workspace: { ...DEFAULTS.workspace, ...parsed.workspace },
      notifications: { ...DEFAULTS.notifications, ...parsed.notifications },
      appearance: { ...DEFAULTS.appearance, ...parsed.appearance },
    }
  } catch {
    return structuredClone(DEFAULTS)
  }
}

export function saveUserPrefs(patch: Partial<UserPrefs>): UserPrefs {
  const current = getUserPrefs()
  const next: UserPrefs = {
    workspace: { ...current.workspace, ...patch.workspace },
    notifications: { ...current.notifications, ...patch.notifications },
    appearance: { ...current.appearance, ...patch.appearance },
  }
  localStorage.setItem(storageKey(), JSON.stringify(next))
  window.dispatchEvent(new Event('mawp-prefs-change'))
  return next
}
