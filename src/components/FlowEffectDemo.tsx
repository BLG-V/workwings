import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Play,
  CheckCircle2,
  Loader2,
  ExternalLink,
  FolderOpen,
  FileCode2,
  Activity,
} from 'lucide-react'
import { Progress } from '@/components/ui/progress'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import ChatMarkdown from '@/components/ChatMarkdown'
import { MOCK_RESULTS } from '@/data/results'
import { STUDIO_ORDER, STUDIO_META, type StudioPageKind } from '@/lib/chat-intent'

const KIND_PATH: Record<StudioPageKind, string> = {
  requirement: '/studio/requirement',
  architecture: '/studio/architecture',
  code: '/studio/code',
  test: '/studio/test',
  deploy: '/studio/deploy',
}

const RESULT_TYPE: Record<StudioPageKind, (typeof MOCK_RESULTS)[number]['type']> = {
  requirement: 'requirement',
  architecture: 'architecture',
  code: 'code',
  test: 'test',
  deploy: 'deployment',
}

function getDemoResult(kind: StudioPageKind) {
  return (
    MOCK_RESULTS.find((r) => r.type === RESULT_TYPE[kind]) ??
    MOCK_RESULTS.find((r) => r.type === 'requirement')!
  )
}

interface FlowEffectDemoProps {
  defaultKind?: StudioPageKind | null
}

export default function FlowEffectDemo({ defaultKind = 'requirement' }: FlowEffectDemoProps) {
  const initial = defaultKind && STUDIO_ORDER.includes(defaultKind)
    ? defaultKind
    : 'requirement'
  const [kind, setKind] = useState<StudioPageKind>(initial)
  const [playing, setPlaying] = useState(false)
  const [progress, setProgress] = useState(0)
  const [revealed, setRevealed] = useState(true)
  const [activeFile, setActiveFile] = useState(0)

  useEffect(() => {
    if (defaultKind && STUDIO_ORDER.includes(defaultKind)) {
      setKind(defaultKind)
      setRevealed(true)
      setProgress(100)
      setPlaying(false)
      setActiveFile(0)
    }
  }, [defaultKind])

  const result = useMemo(() => getDemoResult(kind), [kind])
  const meta = STUDIO_META[kind]

  const play = () => {
    if (playing) return
    setPlaying(true)
    setRevealed(false)
    setProgress(0)
    let p = 0
    const timer = window.setInterval(() => {
      p += 8 + Math.random() * 10
      if (p >= 100) {
        p = 100
        window.clearInterval(timer)
        setProgress(100)
        setPlaying(false)
        setRevealed(true)
      } else {
        setProgress(Math.floor(p))
      }
    }, 180)
  }

  const switchKind = (k: StudioPageKind) => {
    setKind(k)
    setActiveFile(0)
    setRevealed(true)
    setProgress(100)
    setPlaying(false)
  }

  return (
    <div className="mt-3 rounded-xl border border-border/80 bg-muted/20 overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/70 px-3 py-2">
        <div>
          <div className="flex items-center gap-2">
            <div className="text-xs font-medium text-foreground">效果演示区</div>
            <Badge
              variant="outline"
              className="text-[10px] border-amber-300 bg-amber-50 text-amber-800"
            >
              通用样例 · 电商后台
            </Badge>
          </div>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            仅用于展示各阶段产物形态，与你在对话里输入的具体需求无关
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="secondary"
            className="h-8 pressable"
            disabled={playing}
            onClick={play}
          >
            {playing ? (
              <>
                <Loader2 className="size-3.5 mr-1.5 animate-spin" />
                演示中…
              </>
            ) : (
              <>
                <Play className="size-3.5 mr-1.5" />
                播放演示
              </>
            )}
          </Button>
          <Button size="sm" className="h-8 pressable" asChild>
            <Link to={KIND_PATH[kind]} state={{ clearFlow: true }}>
              进入工作台
            </Link>
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5 px-3 py-2 border-b border-border/60">
        {STUDIO_ORDER.map((k) => (
          <button
            key={k}
            type="button"
            onClick={() => switchKind(k)}
            className={`pressable rounded-full border px-2.5 py-1 text-[11px] transition-colors ${
              kind === k
                ? 'border-primary bg-primary/10 text-primary'
                : 'border-border bg-card text-muted-foreground hover:border-primary/40 hover:text-foreground'
            }`}
          >
            {STUDIO_META[k].title.replace(/生成|验证|上线/g, '')}
          </button>
        ))}
      </div>

      {(playing || (!revealed && progress > 0)) && (
        <div className="px-3 py-2 space-y-1.5 border-b border-border/60">
          <div className="flex items-center justify-between text-[11px] text-muted-foreground">
            <span>正在演示「{meta.title}」…</span>
            <span className="tabular-nums">{progress}%</span>
          </div>
          <Progress value={progress} className="h-1.5" />
        </div>
      )}

      <div className="max-h-[360px] overflow-y-auto p-3">
        {!revealed && playing ? (
          <div className="flex min-h-[180px] flex-col items-center justify-center text-muted-foreground">
            <Loader2 className="size-7 animate-spin text-primary mb-3" />
            <p className="text-sm">正在生成可预览产物…</p>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-semibold text-foreground">
                    {result.title}
                  </h3>
                  <Badge
                    variant="outline"
                    className="text-[10px] border-emerald-300 bg-emerald-50 text-emerald-700"
                  >
                    <CheckCircle2 className="size-3 mr-1" />
                    演示产物
                  </Badge>
                </div>
                <p className="text-[11px] text-muted-foreground mt-1">
                  {result.summary}
                </p>
              </div>
            </div>

            {kind === 'test' && result.stats && (
              <div className="grid grid-cols-3 gap-2">
                {(
                  [
                    ['用例总数', result.stats.total, 'text-foreground'],
                    ['通过', result.stats.passed, 'text-emerald-600'],
                    ['失败', result.stats.failed, 'text-rose-600'],
                  ] as const
                ).map(([label, value, color]) => (
                  <div
                    key={label}
                    className="rounded-xl border border-border bg-card px-3 py-2"
                  >
                    <div className="text-[10px] text-muted-foreground">{label}</div>
                    <div className={`text-lg font-semibold tabular-nums ${color}`}>
                      {value}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {kind === 'deploy' && result.deployMeta && (
              <div className="rounded-xl border border-border bg-card p-3 space-y-2">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Activity className="size-4 text-emerald-500" />
                  部署环境健康
                </div>
                <div className="grid grid-cols-2 gap-2 text-[12px]">
                  <div>
                    <span className="text-muted-foreground">版本</span>
                    <div className="font-mono">{result.deployMeta.version}</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">环境</span>
                    <div>{result.deployMeta.env}</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">健康状态</span>
                    <div className="text-emerald-600 font-medium">
                      {result.deployMeta.health}
                    </div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">访问地址</span>
                    <a
                      href={result.deployMeta.url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-primary hover:underline break-all"
                    >
                      {result.deployMeta.url}
                      <ExternalLink className="size-3 shrink-0" />
                    </a>
                  </div>
                </div>
              </div>
            )}

            {kind === 'code' && result.fileTree && (
              <div className="grid gap-2 sm:grid-cols-[140px_1fr]">
                <div className="rounded-xl border border-border bg-card p-2 space-y-1">
                  <div className="flex items-center gap-1 px-1 pb-1 text-[10px] text-muted-foreground">
                    <FolderOpen className="size-3" />
                    文件树
                  </div>
                  {result.fileTree.flatMap((dir, di) =>
                    (dir.children || [{ name: dir.name }]).map((f, fi) => {
                      const idx =
                        result.fileTree!.slice(0, di).reduce(
                          (n, d) => n + (d.children?.length || 1),
                          0,
                        ) + fi
                      return (
                        <button
                          key={`${dir.name}-${f.name}`}
                          type="button"
                          onClick={() => setActiveFile(idx)}
                          className={`flex w-full items-center gap-1 rounded-md px-1.5 py-1 text-left text-[11px] pressable ${
                            activeFile === idx
                              ? 'bg-primary/10 text-primary'
                              : 'text-muted-foreground hover:bg-muted'
                          }`}
                        >
                          <FileCode2 className="size-3 shrink-0" />
                          <span className="truncate">{f.name}</span>
                        </button>
                      )
                    }),
                  )}
                </div>
                <div className="rounded-xl border border-border bg-[#0f1115] p-3 overflow-x-auto">
                  <pre className="text-[11px] leading-relaxed text-[#e8eaed] font-mono whitespace-pre-wrap">
                    {result.content.split('\n\n// ')[activeFile]
                      ? activeFile === 0
                        ? result.content.split('\n\n// ')[0]
                        : `// ${result.content.split('\n\n// ')[activeFile]}`
                      : result.content.slice(0, 1200)}
                  </pre>
                </div>
              </div>
            )}

            {kind !== 'code' && (
              <div className="rounded-xl border border-border bg-card p-3">
                <ChatMarkdown content={result.content} />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
