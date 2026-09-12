import { useState } from 'react'
import {
  MessageSquare,
  LayoutDashboard,
  Workflow,
  FolderKanban,
  Layers,
  Bot,
  PlayCircle,
  Settings,
  SquarePen,
  History,
  LogOut,
  LogIn,
  ChevronDown,
  Shield,
} from 'lucide-react'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { useAuth } from '@/hooks/use-auth'
import { useChatSessions } from '@/lib/chat-history'
import { toast } from 'sonner'
import BrandLogo from '@/components/BrandLogo'
import TechFrame from '@/components/TechFrame'
import ThemeSwitcher from '@/components/ThemeSwitcher'
import { clearPipelineSession, flowNavState } from '@/lib/studio-session'
import { createProject, resolveWorkflowPath } from '@/lib/projects-store'
import { canAccess, type AppCapability } from '@/lib/roles'

const primaryNav = [
  { title: '智能对话', url: '/chat', icon: MessageSquare, exact: true, cap: 'chat' as AppCapability },
  { title: '工作台', url: '/studio', icon: LayoutDashboard, cap: 'studio' as AppCapability },
]

const secondaryNav: Array<{
  title: string
  url: string
  icon: typeof Workflow
  workflow?: boolean
  cap: AppCapability
}> = [
  { title: '高级项目', url: '/advanced', icon: Layers, cap: 'advanced' },
  { title: '工作流编排', url: '/projects', icon: Workflow, workflow: true, cap: 'workflow' },
  { title: '项目管理', url: '/projects', icon: FolderKanban, cap: 'projects' },
  { title: '内核 Agent', url: '/agents', icon: Bot, cap: 'agents' },
  { title: '运行记录', url: '/runs', icon: PlayCircle, cap: 'runs' },
  { title: '管理台', url: '/admin', icon: Shield, cap: 'admin' },
  { title: '设置', url: '/settings', icon: Settings, cap: 'settings' },
]

const HISTORY_COLLAPSED_KEY = 'mawp.sidebar.historyCollapsed'

export function AppSidebar() {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, logout, isLoggedIn } = useAuth()
  const recent = useChatSessions().slice(0, 40)
  const [historyOpen, setHistoryOpen] = useState(() => {
    try {
      return localStorage.getItem(HISTORY_COLLAPSED_KEY) !== '1'
    } catch {
      return true
    }
  })

  const toggleHistory = () => {
    setHistoryOpen((prev) => {
      const next = !prev
      try {
        localStorage.setItem(HISTORY_COLLAPSED_KEY, next ? '0' : '1')
      } catch {
        /* ignore */
      }
      return next
    })
  }

  const isActive = (url: string, exact?: boolean) => {
    if (exact) return location.pathname === url
    if (url.startsWith('/workflow')) return location.pathname.startsWith('/workflow')
    if (url === '/studio' || url.startsWith('/studio')) {
      return location.pathname.startsWith('/studio')
    }
    return location.pathname === url || location.pathname.startsWith(`${url}/`)
  }

  const handleLogout = () => {
    logout()
    toast.success('已退出登录')
    navigate('/login', { replace: true })
  }

  const initials =
    user?.name?.slice(0, 2) || user?.username?.slice(0, 2)?.toUpperCase() || '智'

  return (
    <Sidebar className="pixel-sidebar border-r-0 bg-sidebar">
      <SidebarHeader className="pb-1 gap-2.5 px-2 pt-2">
        <TechFrame
          intensity="panel"
          delaySec={0}
          className="mx-0"
          contentClassName="overflow-visible"
        >
          <Link
            to="/chat"
            className="sidebar-nav-item pixel-brand-link flex items-center rounded-xl px-2.5 py-3 pressable"
          >
            <BrandLogo size={44} />
          </Link>
        </TechFrame>

        <TechFrame
          intensity="panel"
          delaySec={1.4}
          contentClassName="overflow-hidden p-2 space-y-2"
        >
          <Button
            variant="secondary"
            size="sm"
            className="sidebar-nav-item w-full justify-start pressable rounded-xl border-0 bg-sidebar-accent/70"
            onClick={() => {
              clearPipelineSession()
              navigate('/chat', { state: { newChat: Date.now() } })
            }}
          >
            <SquarePen className="size-3.5 mr-2" />
            新建对话
          </Button>

          <div className="rounded-lg bg-background/40 overflow-hidden">
            <div className="flex items-center gap-1 px-1.5 pt-1.5 pb-1">
              <button
                type="button"
                onClick={toggleHistory}
                aria-expanded={historyOpen}
                className="flex min-w-0 flex-1 items-center gap-1 rounded-md px-1 py-0.5 text-[11px] font-medium text-muted-foreground pressable hover:bg-muted/50 hover:text-foreground"
              >
                <History className="size-3 shrink-0" />
                <span className="truncate">历史对话</span>
                <ChevronDown
                  className={`size-3 shrink-0 opacity-70 transition-transform ${
                    historyOpen ? '' : '-rotate-90'
                  }`}
                />
              </button>
              <button
                type="button"
                className="shrink-0 rounded-md px-1.5 py-0.5 text-[10px] text-primary pressable hover:bg-muted/50 hover:underline"
                onClick={() => navigate('/history')}
              >
                全部
              </button>
            </div>
            {historyOpen &&
              (recent.length === 0 ? (
                <p className="px-2.5 pb-2.5 text-[11px] text-muted-foreground">
                  暂无历史，开始第一句吧
                </p>
              ) : (
                <div
                  className="max-h-[180px] space-y-0.5 overflow-y-auto overscroll-contain px-1.5 pb-1.5"
                  onWheel={(e) => e.stopPropagation()}
                >
                  {recent.map((s) => (
                    <button
                      key={s.id}
                      type="button"
                      title={s.title}
                      onClick={() =>
                        navigate('/chat', { state: { resumeSessionId: s.id } })
                      }
                      className="sidebar-nav-item w-full truncate rounded-lg px-2 py-1.5 text-left text-[11px] text-foreground/85 pressable"
                    >
                      {s.title}
                    </button>
                  ))}
                </div>
              ))}
          </div>
        </TechFrame>
      </SidebarHeader>

      <SidebarContent className="px-2 gap-2.5">
        <TechFrame intensity="panel" delaySec={2.8} contentClassName="overflow-hidden py-1">
          <SidebarGroup className="p-0">
            <SidebarGroupLabel className="px-3">能力分区</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {primaryNav
                  .filter((item) => canAccess(user, item.cap))
                  .map((item, index) => (
                  <SidebarMenuItem key={item.url} data-pixel-index={String(index + 1).padStart(2, '0')}>
                    <SidebarMenuButton
                      asChild
                      isActive={isActive(item.url, item.exact)}
                      className="sidebar-nav-item pressable"
                    >
                      <Link
                        to={
                          item.url === '/studio' &&
                          location.pathname.startsWith('/studio')
                            ? location.pathname
                            : item.url
                        }
                        state={
                          item.url.startsWith('/studio')
                            ? location.pathname.startsWith('/studio')
                              ? flowNavState()
                              : { clearFlow: true }
                            : undefined
                        }
                      >
                        <item.icon className="size-4" />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </TechFrame>

        <TechFrame intensity="panel" delaySec={4.2} contentClassName="overflow-hidden py-1">
          <SidebarGroup className="p-0">
            <SidebarGroupLabel className="px-3">更多</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {secondaryNav
                  .filter((item) => canAccess(user, item.cap))
                  .map((item, index) => (
                  <SidebarMenuItem key={item.title} data-pixel-index={String(index + 3).padStart(2, '0')}>
                    <SidebarMenuButton
                      asChild={!item.workflow}
                      isActive={
                        item.workflow
                          ? location.pathname.startsWith('/workflow')
                          : isActive(item.url)
                      }
                      className="sidebar-nav-item pressable"
                      onClick={
                        item.workflow
                          ? () => {
                              const path = resolveWorkflowPath()
                              if (path) {
                                navigate(path)
                                return
                              }
                              const project = createProject({
                                name: '新工作流项目',
                                description: '从侧栏创建',
                                goal: '',
                              })
                              navigate(`/workflow/${project.id}`)
                            }
                          : undefined
                      }
                    >
                      {item.workflow ? (
                        <>
                          <item.icon className="size-4" />
                          <span>{item.title}</span>
                        </>
                      ) : (
                        <Link to={item.url}>
                          <item.icon className="size-4" />
                          <span>{item.title}</span>
                        </Link>
                      )}
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </TechFrame>
      </SidebarContent>

      <SidebarFooter className="px-2 pb-2">
        <TechFrame
          intensity="panel"
          delaySec={5.6}
          contentClassName="overflow-visible px-3 py-2.5 space-y-2.5"
        >
          <div className="flex items-center justify-between gap-2">
            <span className="text-[10px] text-muted-foreground px-0.5">外观</span>
            <ThemeSwitcher />
          </div>
          <button
            type="button"
            className="sidebar-nav-item flex w-full items-center gap-2.5 text-left pressable rounded-lg -mx-0.5 px-0.5 py-0.5"
            onClick={() =>
              navigate(isLoggedIn ? '/settings' : '/login', {
                state: isLoggedIn ? undefined : { from: location.pathname },
              })
            }
          >
            <Avatar className="size-8" key={user?.avatar || user?.id || 'anon'}>
              {user?.avatar ? <AvatarImage src={user.avatar} alt={user.name} /> : null}
              <AvatarFallback className="text-[10px] bg-accent text-primary">
                {initials}
              </AvatarFallback>
            </Avatar>
            <div className="min-w-0 flex-1">
              <div className="truncate text-xs font-medium">
                {user?.name || '访客'}
              </div>
              <div className="truncate text-[10px] text-muted-foreground">
                {isLoggedIn
                  ? `@${user?.username || '—'} · ${
                      user?.role === 'admin' ? '管理员' : '用户'
                    }`
                  : '未登录 · 发消息需登录'}
              </div>
            </div>
          </button>
          {isLoggedIn ? (
            <Button
              variant="ghost"
              size="sm"
              className="sidebar-nav-item w-full justify-start h-8 text-xs text-muted-foreground hover:text-destructive pressable"
              onClick={handleLogout}
            >
              <LogOut className="size-3.5 mr-2" />
              退出登录
            </Button>
          ) : (
            <Button
              variant="secondary"
              size="sm"
              className="sidebar-nav-item w-full justify-start h-8 text-xs pressable rounded-xl"
              onClick={() =>
                navigate('/login', { state: { from: location.pathname } })
              }
            >
              <LogIn className="size-3.5 mr-2" />
              登录 / 注册
            </Button>
          )}
        </TechFrame>
      </SidebarFooter>
    </Sidebar>
  )
}
