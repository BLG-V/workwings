import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { format } from 'date-fns'
import { zhCN } from 'date-fns/locale'
import {
  History,
  MessageSquare,
  Search,
  Trash2,
  ArrowRight,
} from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  deleteChatSession,
  useChatSessions,
} from '@/lib/chat-history'
import { clearPipelineSession } from '@/lib/studio-session'
import { toast } from 'sonner'

export default function HistoryPage() {
  const navigate = useNavigate()
  const [keyword, setKeyword] = useState('')
  const sessions = useChatSessions()

  const filtered = useMemo(() => {
    return sessions.filter((s) => {
      if (!keyword) return true
      const q = keyword.toLowerCase()
      return (
        s.title.toLowerCase().includes(q) ||
        s.messages.some((m) => m.content.toLowerCase().includes(q))
      )
    })
  }, [sessions, keyword])

  return (
    <div className="space-y-5 p-6 max-w-4xl mx-auto">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-display font-bold tracking-tight flex items-center gap-2">
            <History className="size-6 text-primary" />
            历史会话
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            查看并继续之前的对话，支持搜索与删除
          </p>
        </div>
        <Button
          className="pressable"
          onClick={() => {
            clearPipelineSession()
            navigate('/chat', { state: { newChat: Date.now() } })
          }}
        >
          <MessageSquare className="size-4 mr-2" />
          新建对话
        </Button>
      </div>

      <div className="relative max-w-md">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          className="pl-9"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          placeholder="搜索会话标题或内容"
        />
      </div>

      <div className="space-y-3">
        {filtered.map((session) => (
          <Card
            key={session.id}
            className="pressable cursor-pointer hover:border-primary/40 transition-colors"
            onClick={() => navigate('/chat', { state: { resumeSessionId: session.id } })}
          >
            <CardContent className="p-4 flex items-start gap-3">
              <div className="size-10 rounded-xl bg-accent text-primary flex items-center justify-center shrink-0">
                <MessageSquare className="size-4" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h3 className="font-medium text-sm truncate">{session.title}</h3>
                  <span className="text-[11px] text-muted-foreground shrink-0">
                    {session.messages.length} 条
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mt-1 line-clamp-1">
                  {session.messages[session.messages.length - 1]?.content || '空会话'}
                </p>
                <div className="text-[11px] text-muted-foreground mt-2">
                  {format(new Date(session.updatedAt), 'yyyy-MM-dd HH:mm', {
                    locale: zhCN,
                  })}
                  {session.model ? ` · ${session.model}` : ''}
                </div>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <Button
                  size="icon"
                  variant="ghost"
                  className="size-8"
                  onClick={(e) => {
                    e.stopPropagation()
                    deleteChatSession(session.id)
                    toast.success('会话已删除')
                  }}
                >
                  <Trash2 className="size-4 text-muted-foreground" />
                </Button>
                <ArrowRight className="size-4 text-muted-foreground" />
              </div>
            </CardContent>
          </Card>
        ))}

        {filtered.length === 0 && (
          <div className="rounded-2xl border border-dashed p-12 text-center text-sm text-muted-foreground">
            暂无历史会话，去智能对话里聊几句吧
          </div>
        )}
      </div>
    </div>
  )
}
