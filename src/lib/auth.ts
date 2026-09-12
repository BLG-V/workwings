import { LEGACY_OWNER_IDS, migrateLocalOwnerData } from '@/lib/migrate-owner-data'

export type AuthProvider =
  | 'password'
  | 'otp'
  | 'github'
  | 'google'
  | 'wechat'
  | 'guest'

export type AuthRole = 'user' | 'admin'

export interface AuthUser {
  id: string
  name: string
  username: string
  email: string
  phone?: string
  avatar?: string
  bio?: string
  provider?: AuthProvider
  /** 注册默认 user；管理员由服务端白名单授予 */
  role: AuthRole
}

export type ProfilePatch = Partial<
  Pick<AuthUser, 'name' | 'username' | 'email' | 'avatar' | 'bio'>
>

type StoredAccount = AuthUser & { password?: string }

const SESSION_KEY = 'mawp-auth-user'
const TOKEN_KEY = 'mawp-auth-token'
const ACCOUNTS_KEY = 'mawp-auth-accounts'

/** 管理员用户名白名单（小写）。可用 VITE_ADMIN_USERNAMES=wzt,admin 扩展 */
function adminUsernameSet(): Set<string> {
  const fromEnv = (import.meta.env.VITE_ADMIN_USERNAMES as string | undefined)
    ?.split(/[,，\s]+/)
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean)
  const base = ['wzt', ...(fromEnv || [])]
  return new Set(base)
}

export function resolveRoleForAccount(input: {
  username: string
  email?: string
  role?: AuthRole
}): AuthRole {
  const set = adminUsernameSet()
  const u = input.username.trim().toLowerCase()
  const e = (input.email || '').trim().toLowerCase()
  if (set.has(u) || (e && set.has(e.split('@')[0]))) {
    return 'admin'
  }
  // 白名单优先；非白名单即使旧数据写了 admin 也降为 user（防本地篡改冒充）
  // 但已在白名单的保持 admin
  if (input.role === 'admin' && set.has(u)) return 'admin'
  return 'user'
}

export function normalizeAuthUser(
  user: (Partial<AuthUser> & { id?: string }) | null,
): AuthUser | null {
  if (!user?.id || !user.username) return null
  // 验证码登录：角色以服务端为准，避免前端白名单误伤
  const role =
    user.provider === 'otp'
      ? user.role === 'admin'
        ? 'admin'
        : 'user'
      : resolveRoleForAccount({
          username: user.username,
          email: user.email,
          role: user.role,
        })
  return {
    id: user.id,
    name: user.name || user.username,
    username: user.username,
    email: user.email || '',
    phone: user.phone,
    avatar: user.avatar,
    bio: user.bio,
    provider: user.provider,
    role,
  }
}

const DEMO_USERS: StoredAccount[] = [
  {
    id: 'u-1',
    name: '王振同',
    username: 'wzt',
    email: 'wzt@example.com',
    password: '123456',
    provider: 'password',
    role: 'admin',
    avatar:
      'https://lf3-static.bytednsdoc.com/obj/eden-cn/ylcylz_fsph_ryhs/ljhwZthlaukjlkulzlp/feisuda/avatar/base/1.jpg',
  },
  {
    id: 'u-2',
    name: '演示账号',
    username: 'demo',
    email: 'demo@mawp.ai',
    password: 'demo',
    provider: 'password',
    role: 'user',
  },
]

export const OAUTH_PROVIDERS = [
  {
    id: 'github' as const,
    label: 'GitHub',
    desc: '使用 GitHub 账号继续',
    color: 'bg-[#24292f] text-white hover:bg-[#1b1f23]',
  },
  {
    id: 'google' as const,
    label: 'Google',
    desc: '使用 Google 账号继续',
    color: 'bg-white text-foreground border border-border hover:bg-muted',
  },
  {
    id: 'wechat' as const,
    label: '微信',
    desc: '使用微信扫码登录（演示）',
    color: 'bg-[#07c160] text-white hover:bg-[#06ad56]',
  },
]

function readLocalAccounts(): StoredAccount[] {
  try {
    const raw = localStorage.getItem(ACCOUNTS_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as StoredAccount[]
    if (!Array.isArray(parsed)) return []
    return parsed.map((a) => ({
      ...a,
      role: resolveRoleForAccount(a),
    }))
  } catch {
    return []
  }
}

function writeLocalAccounts(list: StoredAccount[]) {
  localStorage.setItem(ACCOUNTS_KEY, JSON.stringify(list))
}

function allAccounts(): StoredAccount[] {
  const local = readLocalAccounts()
  const map = new Map<string, StoredAccount>()
  for (const u of DEMO_USERS) {
    map.set(u.username.toLowerCase(), {
      ...u,
      role: resolveRoleForAccount(u),
    })
  }
  for (const u of local) {
    map.set(u.username.toLowerCase(), {
      ...u,
      role: resolveRoleForAccount(u),
    })
  }
  return [...map.values()]
}

function persistSession(user: AuthUser) {
  const normalized = normalizeAuthUser(user)!
  localStorage.setItem(SESSION_KEY, JSON.stringify(normalized))
}

function toPublicUser(account: StoredAccount): AuthUser {
  const { password: _pw, ...rest } = account
  return normalizeAuthUser(rest)!
}

export function getStoredUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY)
    if (!raw) return null
    return normalizeAuthUser(JSON.parse(raw) as AuthUser)
  } catch {
    return null
  }
}

export function isAuthenticated(): boolean {
  return Boolean(getStoredUser())
}

/** 从本机缓存找回头像/简介（后端尚未持久化时的兜底） */
function resolveLocalProfileExtras(raw: {
  id: string
  username: string
  avatar?: string
  bio?: string
}): { avatar?: string; bio?: string } {
  if (raw.avatar && raw.bio) return { avatar: raw.avatar, bio: raw.bio }
  const prev = getStoredUser()
  const local =
    allAccounts().find(
      (u) =>
        u.id === raw.id ||
        u.username.toLowerCase() === raw.username.toLowerCase(),
    ) || DEMO_USERS.find((u) => u.id === raw.id || u.username === raw.username)
  const sameUser =
    prev &&
    (prev.id === raw.id ||
      prev.username.toLowerCase() === raw.username.toLowerCase())
  return {
    avatar: raw.avatar || (sameUser ? prev?.avatar : undefined) || local?.avatar,
    bio: raw.bio || (sameUser ? prev?.bio : undefined) || local?.bio,
  }
}

/** 验证码 / 密码登录成功后写入会话 */
export function loginWithOtpSession(
  raw: {
    id: string
    name: string
    username: string
    email?: string
    phone?: string
    role?: AuthRole
    avatar?: string
    bio?: string
  },
  token: string,
): AuthUser {
  const extras = resolveLocalProfileExtras(raw)
  const user = normalizeAuthUser({
    ...raw,
    email: raw.email || '',
    phone: raw.phone,
    avatar: extras.avatar,
    bio: extras.bio,
    provider: 'otp',
    role: raw.role === 'admin' ? 'admin' : 'user',
  })!
  // 验证码登录换了新 id 时，把旧账号本机数据迁过来（对话/项目等）
  migrateLocalOwnerData(user.id, [...LEGACY_OWNER_IDS])
  // 对齐本机账号 id，避免保存资料时误报「已被占用」
  upsertLocalAccount(user, user)
  persistSession(user)
  localStorage.setItem(TOKEN_KEY, token)
  return user
}

export function getAuthToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function loginWithPassword(
  account: string,
  password: string,
): { ok: true; user: AuthUser } | { ok: false; message: string } {
  const key = account.trim().toLowerCase()
  if (!key || !password) {
    return { ok: false, message: '请输入账号和密码' }
  }

  const found = allAccounts().find(
    (u) =>
      (u.username.toLowerCase() === key || u.email.toLowerCase() === key) &&
      u.password === password,
  )

  if (!found) {
    return { ok: false, message: '账号或密码不正确' }
  }

  const user = {
    ...toPublicUser(found),
    provider: found.provider || 'password',
  }
  persistSession(user)
  return { ok: true, user }
}

/** 本地测试账号登录：仅供前端开发/验收，不请求后端，也不创建数据库记录。 */
export function loginWithLocalTestAccount():
  | { ok: true; user: AuthUser }
  | { ok: false; message: string } {
  const result = loginWithPassword('demo', 'demo')
  if (result.ok) {
    // 本地测试会话不能携带此前真实登录留下的令牌。
    localStorage.removeItem(TOKEN_KEY)
  }
  return result
}
export function registerWithPassword(input: {
  name: string
  username: string
  email: string
  password: string
}): { ok: true; user: AuthUser } | { ok: false; message: string } {
  const name = input.name.trim()
  const username = input.username.trim().toLowerCase()
  const email = input.email.trim().toLowerCase()
  const password = input.password

  if (!name || !username || !email || !password) {
    return { ok: false, message: '请完整填写注册信息' }
  }
  if (!/^[a-z0-9_]{3,20}$/.test(username)) {
    return { ok: false, message: '用户名需为 3–20 位字母/数字/下划线' }
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return { ok: false, message: '邮箱格式不正确' }
  }
  if (password.length < 6) {
    return { ok: false, message: '密码至少 6 位' }
  }

  // 禁止注册占用管理员用户名
  if (adminUsernameSet().has(username)) {
    return { ok: false, message: '该用户名为系统保留，请换一个' }
  }

  const exists = allAccounts().some(
    (u) =>
      u.username.toLowerCase() === username || u.email.toLowerCase() === email,
  )
  if (exists) {
    return { ok: false, message: '用户名或邮箱已被注册' }
  }

  const account: StoredAccount = {
    id: `u-${Date.now()}`,
    name,
    username,
    email,
    password,
    provider: 'password',
    role: 'user',
  }
  const local = readLocalAccounts()
  local.push(account)
  writeLocalAccounts(local)

  const user = toPublicUser(account)
  persistSession(user)
  return { ok: true, user }
}

/** 第三方登录（演示）：授权成功后创建或复用本地账号；角色仍由白名单决定 */
export function loginWithOAuth(
  provider: 'github' | 'google' | 'wechat',
  profile?: { name?: string; email?: string },
): AuthUser {
  const stamp = Date.now().toString(36)
  const defaults = {
    github: {
      name: profile?.name || 'GitHub 用户',
      username: `gh_${stamp}`,
      email: profile?.email || `gh_${stamp}@users.noreply.github.com`,
      avatar: 'https://avatars.githubusercontent.com/u/9919?v=4',
    },
    google: {
      name: profile?.name || 'Google 用户',
      username: `gg_${stamp}`,
      email: profile?.email || `gg_${stamp}@gmail.com`,
      avatar:
        'https://www.gstatic.com/images/branding/product/1x/googleg_48dp.png',
    },
    wechat: {
      name: profile?.name || '微信用户',
      username: `wx_${stamp}`,
      email: profile?.email || `wx_${stamp}@wechat.local`,
    },
  }[provider]

  const local = readLocalAccounts()
  let account = local.find(
    (u) =>
      u.provider === provider &&
      (profile?.email
        ? u.email.toLowerCase() === profile.email.toLowerCase()
        : false),
  )

  if (!account) {
    account = {
      id: `${provider}-${Date.now()}`,
      name: defaults.name,
      username: defaults.username,
      email: defaults.email,
      avatar: defaults.avatar,
      provider,
      role: 'user',
    }
    account.role = resolveRoleForAccount(account)
    local.push(account)
    writeLocalAccounts(local)
  }

  const user = toPublicUser({
    ...account,
    role: resolveRoleForAccount(account),
  })
  persistSession(user)
  return user
}

/** 快速体验：访客恒为普通用户 */
export function loginAsGuest(name = '访客'): AuthUser {
  const user: AuthUser = {
    id: `guest-${Date.now()}`,
    name,
    username: 'guest',
    email: 'guest@mawp.local',
    provider: 'guest',
    role: 'user',
  }
  persistSession(user)
  return user
}

export function logout() {
  localStorage.removeItem(SESSION_KEY)
  localStorage.removeItem(TOKEN_KEY)
}

/** 更新当前登录用户资料（不可改 role） */
export function updateUserProfile(
  patch: ProfilePatch,
): { ok: true; user: AuthUser } | { ok: false; message: string } {
  const current = getStoredUser()
  if (!current) return { ok: false, message: '未登录' }

  const name = patch.name !== undefined ? patch.name.trim() : current.name
  const username =
    patch.username !== undefined
      ? patch.username.trim().toLowerCase()
      : current.username
  const email =
    patch.email !== undefined ? patch.email.trim().toLowerCase() : current.email
  const avatar = patch.avatar !== undefined ? patch.avatar : current.avatar
  const bio = patch.bio !== undefined ? patch.bio.trim() : current.bio

  if (!name) return { ok: false, message: '姓名不能为空' }
  if (!/^[a-z0-9_]{3,20}$/.test(username)) {
    return { ok: false, message: '用户名需为 3–20 位字母/数字/下划线' }
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return { ok: false, message: '邮箱格式不正确' }
  }

  // 非管理员改成管理员保留名则拒绝
  if (
    current.role !== 'admin' &&
    adminUsernameSet().has(username) &&
    username !== current.username.toLowerCase()
  ) {
    return { ok: false, message: '该用户名为系统保留，请换一个' }
  }

  // 本机可能同时有「旧本地 id」和「后端 u-1」两份同一人账号，不能当占用
  const conflict = allAccounts().find((u) => {
    if (u.id === current.id) return false
    const samePerson =
      u.username.toLowerCase() === current.username.toLowerCase() ||
      (!!u.email &&
        !!current.email &&
        u.email.toLowerCase() === current.email.toLowerCase())
    if (samePerson) return false
    return (
      u.username.toLowerCase() === username ||
      (!!u.email && u.email.toLowerCase() === email)
    )
  })
  if (conflict) {
    return { ok: false, message: '用户名或邮箱已被占用' }
  }

  const next: AuthUser = normalizeAuthUser({
    ...current,
    name,
    username,
    email,
    avatar,
    bio: bio || undefined,
  })!

  upsertLocalAccount(next, current)
  persistSession(next)
  return { ok: true, user: next }
}

/** 按 id / 用户名 / 邮箱合并本机账号，消掉与后端 id 漂移的重复项 */
function upsertLocalAccount(next: AuthUser, previous: AuthUser) {
  const local = readLocalAccounts()
  const demo = DEMO_USERS.find(
    (u) =>
      u.id === next.id ||
      u.username.toLowerCase() === next.username.toLowerCase(),
  )
  const prior = local.find(
    (u) =>
      u.id === previous.id ||
      u.id === next.id ||
      u.username.toLowerCase() === previous.username.toLowerCase() ||
      u.username.toLowerCase() === next.username.toLowerCase() ||
      (!!u.email &&
        !!previous.email &&
        u.email.toLowerCase() === previous.email.toLowerCase()),
  )
  const merged: StoredAccount = {
    ...demo,
    ...prior,
    ...next,
    role: next.role,
    password: prior?.password || demo?.password,
    provider: next.provider || prior?.provider || demo?.provider || previous.provider,
  }

  const filtered = local.filter((u) => {
    if (u.id === previous.id || u.id === next.id) return false
    if (u.username.toLowerCase() === next.username.toLowerCase()) return false
    if (
      u.username.toLowerCase() === previous.username.toLowerCase() &&
      previous.username.toLowerCase() !== next.username.toLowerCase()
    ) {
      return false
    }
    if (
      u.email &&
      next.email &&
      u.email.toLowerCase() === next.email.toLowerCase()
    ) {
      return false
    }
    return true
  })
  filtered.push(merged)
  writeLocalAccounts(filtered)
}

/** 管理台：列出全部账号（无密码） */
export function listPublicAccounts(): AuthUser[] {
  return allAccounts()
    .map((a) => toPublicUser(a))
    .sort((a, b) => {
      if (a.role !== b.role) return a.role === 'admin' ? -1 : 1
      return a.username.localeCompare(b.username)
    })
}

export function getDemoHints() {
  return DEMO_USERS.map((u) => ({
    account: u.username,
    password: u.password || '',
    label: u.name,
    role: resolveRoleForAccount(u),
  }))
}

export function getOAuthProvider(id: string) {
  return OAUTH_PROVIDERS.find((p) => p.id === id) || null
}
