import { useEffect, useState } from 'react'

import { Link, useLocation, useNavigate } from 'react-router-dom'

import { Eye, EyeOff, Loader2, UserPlus } from 'lucide-react'

import { Button } from '@/components/ui/button'

import { Input } from '@/components/ui/input'

import { Label } from '@/components/ui/label'

import { applyThemePalette, getStoredPalette } from '@/lib/theme'

import { isAuthenticated } from '@/lib/auth'

import { useAuth } from '@/hooks/use-auth'

import { sendOtpCode } from '@/lib/otp-auth'

import { toast } from 'sonner'

import AuthShell from '@/components/AuthShell'

import AuthTermsAgree from '@/components/AuthTermsAgree'



export default function RegisterPage() {

  const navigate = useNavigate()

  const location = useLocation()

  const { otpLogin } = useAuth()

  const [name, setName] = useState('')

  const [username, setUsername] = useState('')

  const [password, setPassword] = useState('')

  const [confirm, setConfirm] = useState('')

  const [showPwd, setShowPwd] = useState(false)

  const [email, setEmail] = useState('')

  const [emailCode, setEmailCode] = useState('')

  const [loading, setLoading] = useState(false)

  const [sendingEmail, setSendingEmail] = useState(false)

  const [emailCooldown, setEmailCooldown] = useState(0)

  const [agreed, setAgreed] = useState(false)



  const from =

    (location.state as { from?: string } | null)?.from &&

    (location.state as { from: string }).from !== '/login' &&

    (location.state as { from: string }).from !== '/register'

      ? (location.state as { from: string }).from

      : '/chat'



  useEffect(() => {

    applyThemePalette(getStoredPalette())

    if (isAuthenticated()) navigate(from, { replace: true })

  }, [from, navigate])



  useEffect(() => {

    if (emailCooldown <= 0) return

    const id = window.setTimeout(() => setEmailCooldown((c) => c - 1), 1000)

    return () => window.clearTimeout(id)

  }, [emailCooldown])



  const sendEmailCode = async () => {

    if (!email.trim()) {

      toast.error('请先填写邮箱')

      return

    }

    setSendingEmail(true)

    try {

      const res = await sendOtpCode({

        channel: 'email',

        target: email.trim(),

        purpose: 'register',

      })

      setEmailCooldown(res.cooldown || 60)

      if (res.devCode) {

        toast.success(`邮箱验证码（开发）：${res.devCode}`)

        setEmailCode(res.devCode)

      } else {

        toast.success(`邮箱验证码已发送至 ${res.targetMasked}`)

      }

      if (res.warning) toast.message(res.warning)

    } catch (err) {

      toast.error(err instanceof Error ? err.message : '发送失败')

    } finally {

      setSendingEmail(false)

    }

  }



  const submit = async (e: React.FormEvent) => {

    e.preventDefault()

    if (!agreed) {

      toast.error('请先阅读并同意《用户服务协议》和《隐私政策》')

      return

    }

    if (!name.trim()) {

      toast.error('请填写昵称')

      return

    }

    if (!/^[a-zA-Z0-9_]{3,20}$/.test(username.trim())) {

      toast.error('用户名需为 3–20 位字母/数字/下划线')

      return

    }

    if (password.length < 6) {

      toast.error('密码至少 6 位')

      return

    }

    if (password !== confirm) {

      toast.error('两次输入的密码不一致')

      return

    }

    if (!email.trim()) {

      toast.error('请填写邮箱')

      return

    }

    if (!emailCode.trim()) {

      toast.error('请填写邮箱验证码')

      return

    }

    setLoading(true)

    try {

      const result = await otpLogin({

        purpose: 'register',

        name: name.trim(),

        username: username.trim().toLowerCase(),

        password,

        email: email.trim(),

        emailCode: emailCode.trim(),

      })

      if (!result.ok) {

        toast.error(result.message)

        return

      }

      toast.success(`注册成功，欢迎 ${result.user.name}`)

      navigate(from, { replace: true })

    } finally {

      setLoading(false)

    }

  }



  return (

    <AuthShell

      title="创建账号，开始你的研发流水线"

      subtitle="设置用户名与密码，并用邮箱验证码完成注册。"

    >

      <form

        onSubmit={(e) => void submit(e)}

        className="rounded-3xl border border-border/80 bg-card/95 p-5 md:p-6 shadow-sm space-y-3.5 max-h-[min(82vh,760px)] overflow-y-auto"

      >

        <div className="grid gap-3 sm:grid-cols-2">

          <div className="space-y-1.5">

            <Label htmlFor="name">昵称</Label>

            <Input

              id="name"

              value={name}

              onChange={(e) => setName(e.target.value)}

              placeholder="怎么称呼你"

              className="h-11 rounded-xl"

              required

            />

          </div>

          <div className="space-y-1.5">

            <Label htmlFor="username">用户名</Label>

            <Input

              id="username"

              value={username}

              onChange={(e) => setUsername(e.target.value)}

              placeholder="字母数字下划线"

              className="h-11 rounded-xl"

              required

            />

          </div>

        </div>



        <div className="grid gap-3 sm:grid-cols-2">

          <div className="space-y-1.5">

            <Label htmlFor="password">密码</Label>

            <div className="relative">

              <Input

                id="password"

                type={showPwd ? 'text' : 'password'}

                value={password}

                onChange={(e) => setPassword(e.target.value)}

                placeholder="至少 6 位"

                className="h-11 rounded-xl pr-10"

                required

              />

              <button

                type="button"

                className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-muted-foreground hover:text-foreground pressable"

                onClick={() => setShowPwd((v) => !v)}

              >

                {showPwd ? <EyeOff className="size-4" /> : <Eye className="size-4" />}

              </button>

            </div>

          </div>

          <div className="space-y-1.5">

            <Label htmlFor="confirm">确认密码</Label>

            <Input

              id="confirm"

              type={showPwd ? 'text' : 'password'}

              value={confirm}

              onChange={(e) => setConfirm(e.target.value)}

              placeholder="再输入一次"

              className="h-11 rounded-xl"

              required

            />

          </div>

        </div>



        <div className="space-y-1.5">

          <Label htmlFor="email">邮箱</Label>

          <Input

            id="email"

            type="email"

            autoComplete="email"

            value={email}

            onChange={(e) => setEmail(e.target.value)}

            placeholder="you@example.com"

            className="h-11 rounded-xl"

            required

          />

        </div>



        <div className="space-y-1.5">

          <Label htmlFor="emailCode">邮箱验证码</Label>

          <div className="flex gap-2">

            <Input

              id="emailCode"

              inputMode="numeric"

              value={emailCode}

              onChange={(e) =>

                setEmailCode(e.target.value.replace(/\D/g, '').slice(0, 6))

              }

              placeholder="邮箱 6 位验证码"

              className="h-11 rounded-xl"

              required

            />

            <Button

              type="button"

              variant="secondary"

              className="h-11 shrink-0 rounded-xl px-3 pressable"

              disabled={sendingEmail || emailCooldown > 0}

              onClick={() => void sendEmailCode()}

            >

              {sendingEmail ? (

                <Loader2 className="size-4 animate-spin" />

              ) : emailCooldown > 0 ? (

                `${emailCooldown}s`

              ) : (

                '获取'

              )}

            </Button>

          </div>

        </div>



        <AuthTermsAgree checked={agreed} onCheckedChange={setAgreed} returnTo="/register" />



        <Button

          type="submit"

          className="w-full h-11 rounded-xl pressable"

          disabled={loading || !agreed}

        >

          {loading ? (

            <>

              <Loader2 className="size-4 mr-2 animate-spin" />

              创建中…

            </>

          ) : (

            <>

              <UserPlus className="size-4 mr-2" />

              创建账号

            </>

          )}

        </Button>



        <p className="text-center text-[12px] text-muted-foreground pt-1">

          已有账号？{' '}

          <Link

            to="/login"

            state={{ from }}

            className="text-primary font-medium hover:underline"

          >

            去登录

          </Link>

        </p>

      </form>

    </AuthShell>

  )

}


