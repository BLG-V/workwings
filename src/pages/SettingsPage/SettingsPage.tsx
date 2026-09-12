import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  User,
  Building,
  Palette,
  Bell,
  Save,
  Check,
  LogOut,
} from 'lucide-react'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/components/ui/select'
import { toast } from 'sonner'
import { useThemePalette, type ThemePaletteId } from '@/hooks/use-theme'
import { useAuth } from '@/hooks/use-auth'
import { getUserPrefs, saveUserPrefs } from '@/lib/user-prefs'
import { ROLE_LABEL } from '@/lib/roles'

function fileToCompressedAvatar(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error('读取失败'))
    reader.onload = () => {
      const img = new Image()
      img.onerror = () => reject(new Error('图片解析失败'))
      img.onload = () => {
        const max = 256
        const scale = Math.min(1, max / Math.max(img.width, img.height))
        const w = Math.max(1, Math.round(img.width * scale))
        const h = Math.max(1, Math.round(img.height * scale))
        const canvas = document.createElement('canvas')
        canvas.width = w
        canvas.height = h
        const ctx = canvas.getContext('2d')
        if (!ctx) {
          reject(new Error('无法压缩头像'))
          return
        }
        ctx.drawImage(img, 0, 0, w, h)
        resolve(canvas.toDataURL('image/jpeg', 0.82))
      }
      img.src = String(reader.result)
    }
    reader.readAsDataURL(file)
  })
}

export default function SettingsPage() {
  const navigate = useNavigate()
  const { user, logout, updateProfile } = useAuth()
  const [activeTab, setActiveTab] = useState('profile')
  const { palette, setPalette, presets } = useThemePalette()
  const prefs = getUserPrefs()

  const [name, setName] = useState(user?.name || '')
  const [username, setUsername] = useState(user?.username || '')
  const [email, setEmail] = useState(user?.email || '')
  const [bio, setBio] = useState(
    user?.bio || '全栈开发工程师，专注于AI Agent与微服务架构。',
  )
  const [avatarUrl, setAvatarUrl] = useState(
    user?.avatar ||
      'https://lf3-static.bytednsdoc.com/obj/eden-cn/ylcylz_fsph_ryhs/ljhwZthlaukjlkulzlp/feisuda/avatar/base/1.jpg',
  )
  const [avatarDirty, setAvatarDirty] = useState(false)

  const [workspaceName, setWorkspaceName] = useState(prefs.workspace.name)
  const [defaultModel, setDefaultModel] = useState(prefs.workspace.defaultModel)
  const [apiKey, setApiKey] = useState(prefs.workspace.apiKey)
  const [animationOn, setAnimationOn] = useState(prefs.appearance.animationOn)
  const [notifs, setNotifs] = useState(prefs.notifications)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!user) return
    setName(user.name)
    setUsername(user.username)
    setEmail(user.email)
    setBio(user.bio || '全栈开发工程师，专注于AI Agent与微服务架构。')
    if (!avatarDirty) {
      setAvatarUrl(
        user.avatar ||
          'https://lf3-static.bytednsdoc.com/obj/eden-cn/ylcylz_fsph_ryhs/ljhwZthlaukjlkulzlp/feisuda/avatar/base/1.jpg',
      )
    }
  }, [user, avatarDirty])

  const handleLogout = () => {
    logout()
    toast.success('已退出登录')
    navigate('/login', { replace: true })
  }

  const saveProfile = async () => {
    const result = await updateProfile({
      name,
      username,
      email,
      bio,
      avatar: avatarUrl,
    })
    if (!result.ok) {
      toast.error(result.message)
      return
    }
    setAvatarDirty(false)
    if ('warning' in result && result.warning) {
      toast.message(result.warning)
    } else {
      toast.success('个人资料已保存，侧栏头像已同步')
    }
  }

  return (
    <div className="space-y-6 p-6 max-w-4xl">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-display font-bold tracking-tight">设置</h1>
          <p className="text-sm text-muted-foreground mt-1">
            管理你的个人资料、工作空间和偏好设置
          </p>
        </div>
        <Button
          variant="secondary"
          className="pressable text-muted-foreground hover:text-destructive"
          onClick={handleLogout}
        >
          <LogOut className="size-4 mr-2" />
          退出登录
        </Button>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="profile" className="gap-2">
            <User className="size-4" />
            个人资料
          </TabsTrigger>
          <TabsTrigger value="workspace" className="gap-2">
            <Building className="size-4" />
            工作空间
          </TabsTrigger>
          <TabsTrigger value="appearance" className="gap-2">
            <Palette className="size-4" />
            外观
          </TabsTrigger>
          <TabsTrigger value="notifications" className="gap-2">
            <Bell className="size-4" />
            通知
          </TabsTrigger>
        </TabsList>

        <TabsContent value="profile" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>个人资料</CardTitle>
              <CardDescription className="flex flex-wrap items-center gap-2">
                <span>更新你的个人信息和头像（保存后全站同步）</span>
                <span
                  className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                    user?.role === 'admin'
                      ? 'bg-primary/15 text-primary'
                      : 'bg-muted text-muted-foreground'
                  }`}
                >
                  {ROLE_LABEL[user?.role || 'user']}
                </span>
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center gap-4">
                <Avatar className="size-20">
                  <AvatarImage src={avatarUrl} />
                  <AvatarFallback>
                    {(name || user?.name || '智流').slice(0, 2)}
                  </AvatarFallback>
                </Avatar>
                <div>
                  <Button
                    variant="secondary"
                    size="sm"
                    className="pressable"
                    onClick={() => fileRef.current?.click()}
                  >
                    更换头像
                  </Button>
                  <p className="text-xs text-muted-foreground mt-2">
                    支持 JPG、PNG，最大 2MB；上传后会自动压缩并同步到云端
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="name">姓名</Label>
                  <Input
                    id="name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="username">用户名</Label>
                  <Input
                    id="username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="email">邮箱</Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="bio">个人简介</Label>
                <Textarea
                  id="bio"
                  rows={3}
                  value={bio}
                  onChange={(e) => setBio(e.target.value)}
                />
              </div>

              <div className="flex justify-end">
                <Button className="pressable" onClick={saveProfile}>
                  <Save className="size-4 mr-2" />
                  保存更改
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="workspace" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>工作空间</CardTitle>
              <CardDescription>配置工作空间名称和默认设置</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="workspace-name">工作空间名称</Label>
                <Input
                  id="workspace-name"
                  value={workspaceName}
                  onChange={(e) => setWorkspaceName(e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="default-model">默认模型</Label>
                <Select value={defaultModel} onValueChange={setDefaultModel}>
                  <SelectTrigger id="default-model">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="deepseek-v4-flash">DeepSeek V4 Flash</SelectItem>
                    <SelectItem value="deepseek-v4-pro">DeepSeek V4 Pro</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="api-key">API Key</Label>
                <Input
                  id="api-key"
                  type="password"
                  value={apiKey}
                  placeholder="sk-…"
                  onChange={(e) => setApiKey(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  仅保存在本机浏览器，不会上传到服务器
                </p>
              </div>

              <div className="flex justify-end">
                <Button
                  className="pressable"
                  onClick={() => {
                    saveUserPrefs({
                      workspace: {
                        name: workspaceName.trim() || '智流工作空间',
                        defaultModel,
                        apiKey: apiKey.trim(),
                      },
                    })
                    toast.success('工作空间设置已保存')
                  }}
                >
                  <Save className="size-4 mr-2" />
                  保存更改
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="appearance" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>外观与配色</CardTitle>
              <CardDescription>
                六套像素工作台主题：深色底、硬边界、单一主色和可读的执行状态。
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-3">
                <Label>配色方案</Label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {presets.map((preset) => {
                    const selected = palette === preset.id
                    const previewStyle = {
                      '--pixel-preview-rail': preset.swatch[0],
                      '--pixel-preview-surface': preset.swatch[1],
                      '--pixel-preview-primary': preset.swatch[2],
                      '--pixel-preview-secondary': preset.swatch[3],
                      '--pixel-preview-line': preset.swatch[3],
                    } as CSSProperties
                    return (
                      <button
                        key={preset.id}
                        type="button"
                        onClick={() => {
                          setPalette(preset.id as ThemePaletteId)
                          toast.success(`已切换为「${preset.label}」`)
                        }}
                        className={`pixel-theme-card pressable border-2 p-3 text-left transition-all tech-frame tech-frame--soft ${
                          selected
                            ? 'border-primary/70 bg-primary/10 glow-ring'
                            : 'border-border hover:border-primary/40'
                        }`}
                      >
                        {selected && <span className="tech-frame-trace" aria-hidden />}
                        <div className="relative z-[1]">
                        <div className="flex items-center justify-between gap-2 mb-2">
                          <div className="text-sm font-medium">
                            {preset.label}
                            <span className="ml-2 text-[10px] font-normal text-primary">
                              {preset.hue}
                            </span>
                          </div>
                          {selected && <Check className="size-4 text-primary" />}
                        </div>
                        <div className="pixel-theme-preview mb-2" style={previewStyle} aria-hidden>
                          <span className="pixel-theme-preview__rail" />
                          <span className="pixel-theme-preview__body">
                            <span className="pixel-theme-preview__top" />
                            <span className="pixel-theme-preview__blocks">
                              <span />
                              <span />
                              <span />
                            </span>
                            <span className="pixel-theme-preview__bottom" />
                          </span>
                        </div>
                        <div className="flex gap-1.5 mb-2">
                          {preset.swatch.map((c) => (
                            <span
                              key={c}
                              className="size-6 border border-black/15"
                              style={{ backgroundColor: c }}
                            />
                          ))}
                        </div>
                        <p className="text-[11px] text-muted-foreground leading-relaxed">
                          {preset.desc}
                        </p>
                        {preset.id === 'harbor' && (
                          <div className="pixel-theme-default mt-2 inline-flex bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
                            默认 · 参考图现场
                          </div>
                        )}
                        </div>
                      </button>
                    )
                  })}
                </div>
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm font-medium">动画效果</div>
                  <div className="text-xs text-muted-foreground">启用页面切换和交互动画</div>
                </div>
                <Switch
                  checked={animationOn}
                  onCheckedChange={setAnimationOn}
                />
              </div>

              <div className="flex justify-end">
                <Button
                  className="pressable"
                  onClick={() => {
                    saveUserPrefs({ appearance: { animationOn } })
                    toast.success(
                      `外观已保存：${presets.find((p) => p.id === palette)?.label}`,
                    )
                  }}
                >
                  <Save className="size-4 mr-2" />
                  保存更改
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="notifications" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>通知设置</CardTitle>
              <CardDescription>管理你接收的通知类型</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {(
                [
                  { key: 'done', title: '工作流完成通知', desc: '工作流执行完成时发送通知' },
                  { key: 'fail', title: '运行失败通知', desc: '工作流执行失败时发送通知' },
                  { key: 'agent', title: 'Agent消息通知', desc: 'Agent发送新消息时通知' },
                  { key: 'email', title: '邮件通知', desc: '通过邮件接收重要通知' },
                ] as const
              ).map((item) => (
                <div key={item.key} className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-medium">{item.title}</div>
                    <div className="text-xs text-muted-foreground">{item.desc}</div>
                  </div>
                  <Switch
                    checked={notifs[item.key]}
                    onCheckedChange={(v) =>
                      setNotifs((prev) => ({ ...prev, [item.key]: v }))
                    }
                  />
                </div>
              ))}

              <div className="flex justify-end">
                <Button
                  className="pressable"
                  onClick={() => {
                    saveUserPrefs({ notifications: notifs })
                    toast.success('通知设置已保存')
                  }}
                >
                  <Save className="size-4 mr-2" />
                  保存更改
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <input
        ref={fileRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/gif"
        className="hidden"
        onChange={async (e) => {
          const file = e.target.files?.[0]
          if (!file) return
          if (file.size > 2 * 1024 * 1024) {
            toast.error('头像不能超过 2MB')
            e.target.value = ''
            return
          }
          try {
            const dataUrl = await fileToCompressedAvatar(file)
            setAvatarUrl(dataUrl)
            setAvatarDirty(true)
            // 立即写入，侧栏立刻同步
            const result = await updateProfile({ avatar: dataUrl })
            if (!result.ok) {
              toast.error(result.message)
              return
            }
            setAvatarDirty(false)
            if ('warning' in result && result.warning) {
              toast.message(result.warning)
            } else {
              toast.success('头像已更新并同步')
            }
          } catch {
            toast.error('头像读取失败')
          }
          e.target.value = ''
        }}
      />
    </div>
  )
}
