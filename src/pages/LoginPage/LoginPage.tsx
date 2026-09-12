import { useCallback, useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Eye, EyeOff, Loader2, LogIn, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { applyThemePalette, getStoredPalette } from '@/lib/theme'
import { isAuthenticated } from '@/lib/auth'
import { useAuth } from '@/hooks/use-auth'
import { fetchCaptcha, sendOtpCode } from '@/lib/otp-auth'
import { toast } from 'sonner'
import AuthShell from '@/components/AuthShell'
import AuthTermsAgree from '@/components/AuthTermsAgree'

type LoginTab = 'password' | 'email'

export default function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { otpLogin, passwordLogin, localTestLogin } = useAuth()
  const [tab, setTab] = useState<LoginTab>('password')
  const [agreed, setAgreed] = useState(false)

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPwd, setShowPwd] = useState(false)
  const [captchaId, setCaptchaId] = useState('')
  const [captchaSvg, setCaptchaSvg] = useState('')
  const [captchaCode, setCaptchaCode] = useState('')

  const [target, setTarget] = useState('')
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [sending, setSending] = useState(false)
  const [cooldown, setCooldown] = useState(0)

  const localTestLoginEnabled =
    import.meta.env.DEV || import.meta.env.VITE_ENABLE_LOCAL_TEST_LOGIN === 'true'

  const from =
    (location.state as { from?: string } | null)?.from &&
    (location.state as { from: string }).from !== '/login'
      ? (location.state as { from: string }).from
      : '/chat'

  const refreshCaptcha = useCallback(async () => {
    try {
      const c = await fetchCaptcha()
      setCaptchaId(c.captchaId)
      setCaptchaSvg(c.imageSvg)
      setCaptchaCode('')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '验证码加载失败')
    }
  }, [])

  useEffect(() => {
    applyThemePalette(getStoredPalette())
    if (isAuthenticated()) {
      navigate(from, { replace: true })
    }
  }, [from, navigate])

  useEffect(() => {
    if (tab === 'password') void refreshCaptcha()
  }, [tab, refreshCaptcha])

  useEffect(() => {
    if (cooldown <= 0) return
    const id = window.setTimeout(() => setCooldown((c) => c - 1), 1000)
    return () => window.clearTimeout(id)
  }, [cooldown])

  const sendCode = async () => {
    if (!target.trim()) {
      toast.error('请输入邮箱')
      return
    }
    setSending(true)
    try {
      const res = await sendOtpCode({
        channel: 'email',
        target: target.trim(),
        purpose: 'login',
      })
      setCooldown(res.cooldown || 60)
      if (res.devCode) {
        toast.success(`验证码（开发模式）：${res.devCode}`)
        setCode(res.devCode)
      } else {
        toast.success(`验证码已发送至 ${res.targetMasked}`)
        if (res.warning) toast.message(res.warning)
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '发送失败')
    } finally {
      setSending(false)
    }
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!agreed) {
      toast.error('请先阅读并同意《用户服务协议》和《隐私政策》')
      return
    }
    setLoading(true)
    try {
      if (tab === 'password') {
        if (!username.trim() || !password || !captchaCode.trim()) {
          toast.error('请填写用户名、密码与图形验证码')
          return
        }
        const result = await passwordLogin({
          username: username.trim(),
          password,
          captchaId,
          captchaCode: captchaCode.trim(),
        })
        if (!result.ok) {
          toast.error(result.message)
          void refreshCaptcha()
          return
        }
        toast.success(`欢迎回来，${result.user.name}`)
        navigate(from, { replace: true })
        return
      }

      if (!target.trim() || !code.trim()) {
        toast.error('请填写账号与验证码')
        return
      }
      const result = await otpLogin({
        channel: 'email',
        target: target.trim(),
        code: code.trim(),
        purpose: 'login',
      })
      if (!result.ok) {
        toast.error(result.message)
        return
      }
      toast.success(`欢迎回来，${result.user.name}`)
      navigate(from, { replace: true })
    } finally {
      setLoading(false)
    }
  }

  const enterWithLocalTestAccount = () => {
    const result = localTestLogin()
    if (!result.ok) {
      toast.error(result.message)
      return
    }
    toast.success('测试账号已登录，正在进入 WorkWings 工作台')
    navigate('/studio', { replace: true })
  }

 return (
    <AuthShell
      title="登录后继续你的多 Agent 研发流程"
      subtitle="支持用户名密码（含图形验证码），或邮箱验证码登录。"
    >
      <form
        onSubmit={(e) => void submit(e)}
        className="rounded-3xl border border-border/80 bg-card/95 p-5 md:p-6 shadow-sm space-y-4"
      >
        <div className="flex rounded-xl bg-muted/60 p-1">
          {(
            [
              { id: 'password' as const, label: '账号密码' },
              { id: 'email' as const, label: '邮箱' },
            ] as const
          ).map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => {
                setTab(item.id)
                setTarget('')
                setCode('')
              }}
              className={`flex-1 rounded-lg py-2 text-[13px] pressable ${
                tab === item.id
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>

        {tab === 'password' ? (
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="username">用户名</Label>
              <Input
                id="username"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="用户名"
                className="h-11 rounded-xl"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">密码</Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPwd ? 'text' : 'password'}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="请输入密码"
                  className="h-11 rounded-xl pr-10"
                />
                <button
                  type="button"
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-muted-foreground hover:text-foreground pressable"
                  onClick={() => setShowPwd((v) => !v)}
                  aria-label={showPwd ? '隐藏密码' : '显示密码'}
                >
                  {showPwd ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="captcha">图形验证码</Label>
              <div className="flex gap-2">
                <Input
                  id="captcha"
                  value={captchaCode}
                  onChange={(e) => setCaptchaCode(e.target.value.toUpperCase())}
                  placeholder="不区分大小写"
                  className="h-11 rounded-xl"
                  autoComplete="off"
                />
                <button
                  type="button"
                  title="点击刷新"
                  onClick={() => void refreshCaptcha()}
                  className="relative h-11 w-[120px] shrink-0 overflow-hidden rounded-xl border border-border bg-muted pressable"
                >
                  {captchaSvg ? (
                    <span
                      className="block h-full w-full"
                      dangerouslySetInnerHTML={{ __html: captchaSvg }}
                    />
                  ) : (
                    <RefreshCw className="mx-auto size-4 animate-spin text-muted-foreground" />
                  )}
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="target">邮箱</Label>
              <Input
                id="target"
                autoComplete="email"
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                placeholder="you@example.com"
                className="h-11 rounded-xl"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="code">验证码</Label>
              <div className="flex gap-2">
                <Input
                  id="code"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  value={code}
                  onChange={(e) =>
                    setCode(e.target.value.replace(/\D/g, '').slice(0, 6))
                  }
                  placeholder="6 位验证码"
                  className="h-11 rounded-xl"
                />
                <Button
                  type="button"
                  variant="secondary"
                  className="h-11 shrink-0 rounded-xl px-3 pressable"
                  disabled={sending || cooldown > 0}
                  onClick={() => void sendCode()}
                >
                  {sending ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : cooldown > 0 ? (
                    `${cooldown}s`
                  ) : (
                    '获取验证码'
                  )}
                </Button>
              </div>
            </div>
          </div>
        )}

        <AuthTermsAgree checked={agreed} onCheckedChange={setAgreed} returnTo="/login" />

        <Button
          type="submit"
          className="w-full h-11 rounded-xl pressable"
          disabled={loading || !agreed}
        >
          {loading ? (
            <>
              <Loader2 className="size-4 mr-2 animate-spin" />
              登录中…
            </>
          ) : (
            <>
              <LogIn className="size-4 mr-2" />
              登录
            </>
          )}
        </Button>

        {localTestLoginEnabled ? (
          <div className="space-y-2 border-t border-border/60 pt-3">
            <Button
              type="button"
              variant="outline"
              className="w-full h-10 rounded-xl pressable"
              onClick={enterWithLocalTestAccount}
              disabled={loading}
            >
              使用本地测试账号进入工作台
            </Button>
            <p className="text-center text-[11px] text-muted-foreground">
              仅前端本地测试，不调用登录接口，不写入 WorkWings 数据库
            </p>
          </div>
        ) : null}

        <p className="text-center text-[12px] text-muted-foreground pt-1">
          没有账号？{' '}
          <Link
            to="/register"
            state={{ from }}
            className="text-primary font-medium hover:underline"
          >
            注册
          </Link>
        </p>
      </form>
    </AuthShell>
  )
}
