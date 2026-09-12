/** 手机号 / 邮箱验证码（走 MAWP 后端） */

export type OtpChannel = 'phone' | 'email'
export type OtpPurpose = 'login' | 'register'

export interface OtpUser {
  id: string
  name: string
  username: string
  email?: string
  phone?: string
  role: 'user' | 'admin'
  provider?: string
  avatar?: string
  bio?: string
}

/** 经 Vite 代理 /api/mawp → 后端 /api */
const API = '/api/mawp/auth'

async function parseError(res: Response): Promise<string> {
  try {
    const data = (await res.json()) as { detail?: string | { msg?: string }[] }
    if (typeof data.detail === 'string') return data.detail
    if (Array.isArray(data.detail) && data.detail[0]?.msg) return data.detail[0].msg
  } catch {
    /* ignore */
  }
  return `请求失败（HTTP ${res.status}）`
}

export async function sendOtpCode(input: {
  channel: OtpChannel
  target: string
  purpose: OtpPurpose
}): Promise<{ ok: true; cooldown: number; targetMasked: string; devCode?: string; warning?: string }> {
  const res = await fetch(`${API}/send-code`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
  if (!res.ok) throw new Error(await parseError(res))
  const data = (await res.json()) as {
    cooldown?: number
    targetMasked?: string
    devCode?: string
    warning?: string
  }
  return {
    ok: true,
    cooldown: data.cooldown ?? 60,
    targetMasked: data.targetMasked || input.target,
    devCode: data.devCode,
    warning: data.warning,
  }
}

export async function verifyOtpCode(input: {
  channel?: OtpChannel
  target?: string
  code?: string
  purpose: OtpPurpose
  name?: string
  username?: string
  password?: string
  email?: string
  phone?: string
  emailCode?: string
  phoneCode?: string
}): Promise<{ token: string; user: OtpUser }> {
  const res = await fetch(`${API}/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      channel: input.channel,
      target: input.target,
      code: input.code,
      purpose: input.purpose,
      name: input.name,
      username: input.username,
      password: input.password,
      email: input.email,
      phone: input.phone,
      email_code: input.emailCode,
      phone_code: input.phoneCode,
    }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  const data = (await res.json()) as { token?: string; user?: OtpUser }
  if (!data.token || !data.user) throw new Error('登录响应无效')
  return { token: data.token, user: data.user }
}

export async function fetchCaptcha(): Promise<{
  captchaId: string
  imageSvg: string
}> {
  const res = await fetch(`${API}/captcha`)
  if (!res.ok) throw new Error(await parseError(res))
  const data = (await res.json()) as { captchaId?: string; imageSvg?: string }
  if (!data.captchaId || !data.imageSvg) throw new Error('验证码加载失败')
  return { captchaId: data.captchaId, imageSvg: data.imageSvg }
}

export async function loginWithPassword(input: {
  username: string
  password: string
  captchaId: string
  captchaCode: string
}): Promise<{ token: string; user: OtpUser }> {
  const res = await fetch(`${API}/login-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      username: input.username,
      password: input.password,
      captcha_id: input.captchaId,
      captcha_code: input.captchaCode,
    }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  const data = (await res.json()) as { token?: string; user?: OtpUser }
  if (!data.token || !data.user) throw new Error('登录响应无效')
  return { token: data.token, user: data.user }
}

export async function updateRemoteProfile(
  token: string,
  patch: {
    name?: string
    username?: string
    email?: string
    avatar?: string
    bio?: string
  },
): Promise<OtpUser> {
  const res = await fetch(`${API}/me`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(patch),
  })
  if (!res.ok) throw new Error(await parseError(res))
  const data = (await res.json()) as { user?: OtpUser }
  if (!data.user) throw new Error('资料更新响应无效')
  return data.user
}

export async function fetchAuthUsers(token: string): Promise<OtpUser[]> {
  const res = await fetch(`${API}/users`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error(await parseError(res))
  const data = (await res.json()) as { users?: OtpUser[] }
  return data.users || []
}
