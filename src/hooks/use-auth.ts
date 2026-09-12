import { useCallback, useEffect, useState } from 'react'
import {
  getAuthToken,
  getStoredUser,
  loginWithLocalTestAccount,
  loginWithOtpSession,
  logout as clearSession,
  updateUserProfile,
  type AuthUser,
  type ProfilePatch,
} from '@/lib/auth'
import { LEGACY_OWNER_IDS, migrateLocalOwnerData } from '@/lib/migrate-owner-data'
import {
  loginWithPassword as apiLoginPassword,
  updateRemoteProfile,
  verifyOtpCode,
  type OtpChannel,
  type OtpPurpose,
} from '@/lib/otp-auth'
import { notifyChatOwnerChanged } from '@/lib/chat-history'
import { clearPipelineSession } from '@/lib/studio-session'
import { notifyProjectsOwnerChanged } from '@/lib/projects-store'
import { notifyRunsOwnerChanged } from '@/lib/runs-store'
import { notifyWorkflowsOwnerChanged } from '@/lib/workflows-store'
import { notifyAgentsOwnerChanged } from '@/lib/agents-store'

export function useAuth() {
  const [user, setUser] = useState<AuthUser | null>(() => getStoredUser())

  useEffect(() => {
    const sync = () => setUser(getStoredUser())
    window.addEventListener('storage', sync)
    window.addEventListener('mawp-auth-change', sync)
    return () => {
      window.removeEventListener('storage', sync)
      window.removeEventListener('mawp-auth-change', sync)
    }
  }, [])

  // 已登录用户：把旧密码账号 u-1 等本机数据迁到当前 id（只迁空桶）
  useEffect(() => {
    if (!user?.id) return
    const { migrated } = migrateLocalOwnerData(user.id, [...LEGACY_OWNER_IDS])
    if (migrated.length) {
      notifyChatOwnerChanged()
      notifyProjectsOwnerChanged()
      notifyRunsOwnerChanged()
      notifyWorkflowsOwnerChanged()
      notifyAgentsOwnerChanged()
    }
  }, [user?.id])

  // 会话缺头像时：从本机账号表或管理员默认图补回
  useEffect(() => {
    if (!user?.id || user.avatar) return
    let fromAccounts: string | undefined
    try {
      const raw = localStorage.getItem('mawp-auth-accounts')
      if (raw) {
        const list = JSON.parse(raw) as Array<{
          id?: string
          username?: string
          avatar?: string
        }>
        fromAccounts = list.find(
          (u) =>
            u.id === user.id ||
            u.username?.toLowerCase() === user.username.toLowerCase(),
        )?.avatar
      }
    } catch {
      /* ignore */
    }
    const fallback =
      fromAccounts ||
      ((user.username === 'wzt' || user.id === 'u-1')
        ? 'https://lf3-static.bytednsdoc.com/obj/eden-cn/ylcylz_fsph_ryhs/ljhwZthlaukjlkulzlp/feisuda/avatar/base/1.jpg'
        : undefined)
    if (!fallback) return
    const saved = updateUserProfile({ avatar: fallback })
    if (!saved.ok) return
    setUser(saved.user)
    const token = getAuthToken()
    if (token) {
      void updateRemoteProfile(token, { avatar: fallback }).catch(() => undefined)
    }
    window.dispatchEvent(new Event('mawp-auth-change'))
  }, [user?.id, user?.avatar, user?.username])

  const notifyOwnerSwitch = () => {
    window.dispatchEvent(new Event('mawp-auth-change'))
    clearPipelineSession()
    notifyChatOwnerChanged()
    notifyProjectsOwnerChanged()
    notifyRunsOwnerChanged()
    notifyWorkflowsOwnerChanged()
    notifyAgentsOwnerChanged()
  }

  const notifyProfile = () => {
    window.dispatchEvent(new Event('mawp-auth-change'))
  }

  const otpLogin = useCallback(
    async (input: {
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
    }) => {
      try {
        const { token, user: remote } = await verifyOtpCode(input)
        const next = loginWithOtpSession(remote, token)
        setUser(next)
        notifyOwnerSwitch()
        return { ok: true as const, user: next }
      } catch (err) {
        return {
          ok: false as const,
          message: err instanceof Error ? err.message : '验证失败',
        }
      }
    },
    [],
  )

  const passwordLogin = useCallback(
    async (input: {
      username: string
      password: string
      captchaId: string
      captchaCode: string
    }) => {
      try {
        const { token, user: remote } = await apiLoginPassword(input)
        const next = loginWithOtpSession(remote, token)
        setUser(next)
        notifyOwnerSwitch()
        return { ok: true as const, user: next }
      } catch (err) {
        return {
          ok: false as const,
          message: err instanceof Error ? err.message : '登录失败',
        }
      }
    },
    [],
  )

  const localTestLogin = useCallback(() => {
    const result = loginWithLocalTestAccount()
    if (!result.ok) return result
    setUser(result.user)
    notifyOwnerSwitch()
    return result
  }, [])

  const logout = useCallback(() => {
    clearSession()
    setUser(null)
    notifyOwnerSwitch()
  }, [])

  const updateProfile = useCallback(async (patch: ProfilePatch) => {
    const result = updateUserProfile(patch)
    if (!result.ok) return result

    const token = getAuthToken()
    if (token) {
      try {
        const remote = await updateRemoteProfile(token, {
          name: result.user.name,
          username: result.user.username,
          email: result.user.email,
          avatar: result.user.avatar,
          bio: result.user.bio,
        })
        const merged = loginWithOtpSession(remote, token)
        setUser(merged)
        notifyProfile()
        return { ok: true as const, user: merged }
      } catch (err) {
        // 本机已保存；后端未就绪时仍提示成功，但带回警告信息
        setUser(result.user)
        notifyProfile()
        return {
          ok: true as const,
          user: result.user,
          warning:
            err instanceof Error
              ? `本机已保存，云端同步失败：${err.message}`
              : '本机已保存，云端同步失败',
        }
      }
    }

    setUser(result.user)
    notifyProfile()
    return result
  }, [])

  return {
    user,
    isLoggedIn: Boolean(user),
    isAdmin: user?.role === 'admin',
    otpLogin,
    passwordLogin,
    localTestLogin,
    logout,
    updateProfile,
  }
}
