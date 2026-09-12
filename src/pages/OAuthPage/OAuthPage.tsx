import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { CheckCircle2, Loader2, Shield } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { applyThemePalette, getStoredPalette } from '@/lib/theme'
import { getOAuthProvider, isAuthenticated } from '@/lib/auth'
import { useAuth } from '@/hooks/use-auth'
import { toast } from 'sonner'
import BrandLogo from '@/components/BrandLogo'

export default function OAuthPage() {
  const { provider = '' } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const { oauthLogin } = useAuth()
  const meta = useMemo(() => getOAuthProvider(provider), [provider])
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)

  const from =
    (location.state as { from?: string } | null)?.from &&
    (location.state as { from: string }).from !== '/login'
      ? (location.state as { from: string }).from
      : '/chat'

  useEffect(() => {
    applyThemePalette(getStoredPalette())
    if (isAuthenticated()) navigate(from, { replace: true })
  }, [from, navigate])

  useEffect(() => {
    if (!meta) return
    if (meta.id === 'github') {
      setName('Octo Dev')
      setEmail('octo@users.noreply.github.com')
    } else if (meta.id === 'google') {
      setName('Google User')
      setEmail('user@gmail.com')
    } else {
      setName('微信用户')
      setEmail('')
    }
  }, [meta])

  if (!meta) {
    return (
      <div className="min-h-svh flex flex-col items-center justify-center gap-3 p-6">
        <p className="text-sm text-muted-foreground">未知的登录方式</p>
        <Button asChild>
          <Link to="/login">返回登录</Link>
        </Button>
      </div>
    )
  }

  const authorize = async () => {
    setLoading(true)
    await new Promise((r) => setTimeout(r, 700))
    const user = oauthLogin(meta.id, {
      name: name.trim() || undefined,
      email: email.trim() || undefined,
    })
    setLoading(false)
    toast.success(`已通过 ${meta.label} 登录：${user.name}`)
    navigate(from, { replace: true })
  }

  return (
    <div className="relative min-h-svh overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage:
            'radial-gradient(ellipse 50% 40% at 50% 0%, hsl(var(--primary) / 0.12), transparent 60%), linear-gradient(180deg, hsl(var(--background)), hsl(var(--muted)))',
        }}
      />
      <div className="relative z-10 mx-auto flex min-h-svh max-w-lg flex-col justify-center px-6 py-12">
        <BrandLogo size={56} className="mb-8 justify-center" />
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          className="surface-panel glow-ring rounded-3xl p-6 md:p-7 space-y-5"
        >
          <div className="flex items-start gap-3">
            <div className="size-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center">
              <Shield className="size-5" />
            </div>
            <div>
              <h1 className="font-display text-xl font-semibold">
                {meta.label} 授权登录
              </h1>
              <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                演示 OAuth：不会跳转真实 {meta.label}。确认后将在本机创建/登录智流账号。
              </p>
            </div>
          </div>

          <div className="rounded-2xl border border-border bg-muted/40 p-3 text-xs space-y-2">
            <div className="flex items-center gap-2 text-foreground">
              <CheckCircle2 className="size-3.5 text-emerald-500" />
              读取公开昵称与头像
            </div>
            <div className="flex items-center gap-2 text-foreground">
              <CheckCircle2 className="size-3.5 text-emerald-500" />
              用于智流工作台登录态
            </div>
          </div>

          <div className="space-y-3">
            <div className="space-y-2">
              <Label htmlFor="oauth-name">授权昵称</Label>
              <Input
                id="oauth-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="h-11 rounded-xl"
              />
            </div>
            {meta.id !== 'wechat' && (
              <div className="space-y-2">
                <Label htmlFor="oauth-email">授权邮箱</Label>
                <Input
                  id="oauth-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="h-11 rounded-xl"
                />
              </div>
            )}
          </div>

          <Button
            className="w-full h-11 rounded-xl pressable"
            disabled={loading}
            onClick={() => void authorize()}
          >
            {loading ? (
              <>
                <Loader2 className="size-4 mr-2 animate-spin" />
                授权中…
              </>
            ) : (
              `授权并登录智流`
            )}
          </Button>

          <Button
            variant="secondary"
            className="w-full h-10 rounded-xl pressable"
            asChild
          >
            <Link to="/login" state={{ from }}>
              取消，返回登录
            </Link>
          </Button>
        </motion.div>
      </div>
    </div>
  )
}
