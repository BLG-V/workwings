import { Shield, Users, KeyRound, Sparkles } from 'lucide-react'
import { useEffect, useState } from 'react'
import { getAuthToken } from '@/lib/auth'
import { fetchAuthUsers, type OtpUser } from '@/lib/otp-auth'
import { ROLE_LABEL } from '@/lib/roles'
import { useAuth } from '@/hooks/use-auth'
import TechFrame from '@/components/TechFrame'

export default function AdminPage() {
  const { user } = useAuth()
  const [accounts, setAccounts] = useState<OtpUser[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    const token = getAuthToken()
    if (!token) {
      setError('会话令牌缺失，请重新登录')
      return
    }
    void fetchAuthUsers(token)
      .then(setAccounts)
      .catch((err) =>
        setError(err instanceof Error ? err.message : '加载用户失败'),
      )
  }, [user?.id])

  const adminCount = accounts.filter((a) => a.role === 'admin').length
  const userCount = accounts.filter((a) => a.role === 'user').length

  return (
    <div className="mx-auto w-full max-w-5xl space-y-6 px-4 py-6 md:px-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
          <Shield className="size-6 text-primary" />
          管理台
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          当前身份：{user?.name}（{ROLE_LABEL[user?.role || 'user']}）。注册用户默认为普通用户；管理员由邮箱/手机号白名单授予。
        </p>
      </div>

      {error ? (
        <div className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-3">
        <TechFrame intensity="panel" contentClassName="p-4">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Users className="size-3.5" />
            账号总数
          </div>
          <div className="mt-2 text-2xl font-semibold tabular-nums">
            {accounts.length}
          </div>
        </TechFrame>
        <TechFrame intensity="panel" contentClassName="p-4">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Shield className="size-3.5" />
            管理员
          </div>
          <div className="mt-2 text-2xl font-semibold tabular-nums">
            {adminCount}
          </div>
        </TechFrame>
        <TechFrame intensity="panel" contentClassName="p-4">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Sparkles className="size-3.5" />
            普通用户
          </div>
          <div className="mt-2 text-2xl font-semibold tabular-nums">
            {userCount}
          </div>
        </TechFrame>
      </div>

      <TechFrame intensity="panel" contentClassName="overflow-hidden">
        <div className="border-b border-border/70 px-4 py-3 text-sm font-medium">
          账号与角色
        </div>
        <div className="divide-y divide-border/60">
          {accounts.length === 0 && !error ? (
            <div className="px-4 py-6 text-sm text-muted-foreground">
              暂无注册用户
            </div>
          ) : null}
          {accounts.map((a) => (
            <div
              key={a.id}
              className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm"
            >
              <div className="min-w-0 flex-1">
                <div className="font-medium truncate">
                  {a.name}
                  <span className="ml-2 text-xs text-muted-foreground">
                    @{a.username}
                  </span>
                </div>
                <div className="text-xs text-muted-foreground truncate">
                  {[a.phone, a.email].filter(Boolean).join(' · ') || '—'}
                </div>
              </div>
              <span
                className={`shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-medium ${
                  a.role === 'admin'
                    ? 'bg-primary/15 text-primary'
                    : 'bg-muted text-muted-foreground'
                }`}
              >
                {ROLE_LABEL[a.role]}
              </span>
            </div>
          ))}
        </div>
      </TechFrame>

      <TechFrame intensity="panel" contentClassName="p-4 space-y-2">
        <div className="flex items-center gap-2 text-sm font-medium">
          <KeyRound className="size-4 text-primary" />
          权限说明
        </div>
        <ul className="list-disc space-y-1 pl-5 text-[13px] text-muted-foreground">
          <li>
            <strong className="text-foreground">普通用户</strong>
            ：智能对话、Studio、历史、项目/工作流、运行记录、高级项目、Agent
            市场、设置
          </li>
          <li>
            <strong className="text-foreground">管理员</strong>
            ：含以上全部，另可进入本管理台查看账号与角色
          </li>
          <li>
            在 <code className="text-foreground">backend/.env</code> 配置{' '}
            <code className="text-foreground">AUTH_ADMIN_EMAILS</code> /{' '}
            <code className="text-foreground">AUTH_ADMIN_PHONES</code>
          </li>
          <li>他人自行注册永远是普通用户，无法自助升为管理员</li>
        </ul>
      </TechFrame>
    </div>
  )
}
