import { getAuthToken, getStoredUser } from '@/lib/auth'

export const WORKWINGS_BASE = '/api/v1'

export function getWorkWingsActorId(): string {
  return (
    import.meta.env.VITE_WORKWINGS_ACTOR_ID ||
    getStoredUser()?.id ||
    'local_dev_actor'
  )
}

export function getWorkWingsActorRoles(): string {
  const configured = import.meta.env.VITE_WORKWINGS_ACTOR_ROLES as string | undefined
  if (configured?.trim()) return configured.trim()
  return getStoredUser()?.role === 'admin'
    ? 'admin,developer,approver,release_manager'
    : 'developer,approver'
}

export function getWorkWingsHeaders(init?: HeadersInit): Headers {
  const headers = new Headers(init)
  if (!headers.has('Accept')) headers.set('Accept', 'application/json')
  headers.set('X-Actor-Id', getWorkWingsActorId())
  headers.set('X-Actor-Roles', getWorkWingsActorRoles())

  const token = getAuthToken()
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  return headers
}
