/** 账号切换后，把旧 owner 桶里的本机数据迁到当前用户 */

const DATA_KEYS = [
  'mawp-chat-history',
  'mawp-projects',
  'mawp-runs',
  'mawp-workflows',
  'mawp-agents-custom',
  'mawp-user-prefs',
] as const

const EXTRA_KEYS = ['mawp-last-project'] as const

/** 认领后必须清空，避免下一空账号再吃到同一份匿名/演示数据 */
const CLEAR_AFTER_CLAIM = new Set(['anonymous'])

function isEmptyPayload(raw: string | null): boolean {
  if (!raw) return true
  try {
    const v = JSON.parse(raw) as unknown
    if (Array.isArray(v)) return v.length === 0
    if (v && typeof v === 'object') return Object.keys(v as object).length === 0
    return false
  } catch {
    return false
  }
}

function clearOwnerBucket(ownerId: string) {
  for (const base of DATA_KEYS) {
    localStorage.removeItem(`${base}:${ownerId}`)
  }
  for (const base of EXTRA_KEYS) {
    localStorage.removeItem(`${base}:${ownerId}`)
  }
}

/**
 * 将 fromIds 下的本地数据复制到 toUserId（仅当目标为空时）。
 * 典型：旧密码账号 u-1 → 新 OTP 管理员；未登录 anonymous → 首次登录用户。
 * anonymous 认领成功后会清空源桶，防止下一账号串数据。
 */
export function migrateLocalOwnerData(
  toUserId: string,
  fromIds: string[] = ['u-1', 'anonymous'],
): { migrated: string[] } {
  const migrated: string[] = []
  if (!toUserId || typeof localStorage === 'undefined') {
    return { migrated }
  }

  for (const from of fromIds) {
    if (!from || from === toUserId) continue
    let claimedFromThis = false
    for (const base of DATA_KEYS) {
      const srcKey = `${base}:${from}`
      const dstKey = `${base}:${toUserId}`
      const src = localStorage.getItem(srcKey)
      if (!src || isEmptyPayload(src)) continue
      if (!isEmptyPayload(localStorage.getItem(dstKey))) continue
      localStorage.setItem(dstKey, src)
      migrated.push(dstKey)
      claimedFromThis = true
    }
    for (const base of EXTRA_KEYS) {
      const srcKey = `${base}:${from}`
      const dstKey = `${base}:${toUserId}`
      const src = localStorage.getItem(srcKey)
      if (!src) continue
      if (localStorage.getItem(dstKey)) continue
      localStorage.setItem(dstKey, src)
      migrated.push(dstKey)
      claimedFromThis = true
    }
    if (claimedFromThis && CLEAR_AFTER_CLAIM.has(from)) {
      clearOwnerBucket(from)
    }
  }

  return { migrated }
}

/** 常见旧管理员 / 演示账号 / 早期 OTP 管理员 ID */
export const LEGACY_OWNER_IDS = [
  'u-1',
  'u-2',
  'anonymous',
  'u-a1379ee07b',
] as const
