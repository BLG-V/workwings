import { Navigate, useLocation } from 'react-router-dom'
import type { AuthUser } from '@/lib/auth'
import {
  getStoredUser,
  isAuthenticated,
  normalizeAuthUser,
} from '@/lib/auth'
import { canAccess, capabilityForPath } from '@/lib/roles'

/** 需登录的页面；未登录跳登录，并带回跳地址 */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  const user = normalizeAuthUser(getStoredUser())
  const need = capabilityForPath(location.pathname)
  if (need && user && !canAccess(user, need)) {
    return <Navigate to="/chat" replace />
  }

  return <>{children}</>
}

export function RequireAdmin({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  const user = normalizeAuthUser(getStoredUser()) as AuthUser | null
  if (!canAccess(user, 'admin')) {
    return <Navigate to="/chat" replace />
  }
  return <>{children}</>
}
