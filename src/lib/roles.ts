import type { AuthRole, AuthUser } from '@/lib/auth'

/** 侧栏/路由能力键 */
export type AppCapability =
  | 'chat'
  | 'studio'
  | 'history'
  | 'settings'
  | 'projects'
  | 'workflow'
  | 'runs'
  | 'advanced'
  | 'agents'
  | 'admin'

const USER_CAPS: AppCapability[] = [
  'chat',
  'studio',
  'history',
  'settings',
  'projects',
  'workflow',
  'runs',
  'advanced',
  'agents',
]

const ADMIN_CAPS: AppCapability[] = [...USER_CAPS, 'admin']

export function capabilitiesFor(role: AuthRole | undefined | null): AppCapability[] {
  return role === 'admin' ? ADMIN_CAPS : USER_CAPS
}

export function canAccess(
  user: Pick<AuthUser, 'role'> | null | undefined,
  cap: AppCapability,
): boolean {
  return capabilitiesFor(user?.role).includes(cap)
}

export function isAdminUser(
  user: Pick<AuthUser, 'role'> | null | undefined,
): boolean {
  return user?.role === 'admin'
}

/** 路径 → 所需能力（未列出的登录即可） */
export function capabilityForPath(pathname: string): AppCapability | null {
  if (pathname === '/chat' || pathname === '/') return 'chat'
  if (pathname.startsWith('/studio')) return 'studio'
  if (pathname.startsWith('/history')) return 'history'
  if (pathname.startsWith('/settings')) return 'settings'
  if (pathname.startsWith('/projects')) return 'projects'
  if (pathname.startsWith('/workflow')) return 'workflow'
  if (pathname.startsWith('/runs')) return 'runs'
  if (pathname.startsWith('/advanced')) return 'advanced'
  if (pathname.startsWith('/agents')) return 'agents'
  if (pathname.startsWith('/admin')) return 'admin'
  return null
}

export const ROLE_LABEL: Record<AuthRole, string> = {
  user: '普通用户',
  admin: '管理员',
}
