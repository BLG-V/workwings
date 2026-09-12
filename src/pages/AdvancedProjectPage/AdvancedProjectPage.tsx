import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Upload,
  Sparkles,
  FolderOpen,
  Play,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Loader2,
  FileText,
  Download,
  Copy,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { toast } from 'sonner'
import {
  createAdvancedProject,
  generateAdvancedPhase,
  generateAdvancedRemaining,
  listAdvancedProjects,
  advancedProjectExportUrl,
  copyAdvancedWorkspacePath,
  fetchAdvancedProjectTree,
  fetchAdvancedProjectFile,
  type AdvancedPhase,
  type AdvancedProject,
} from '@/lib/advanced-api'
import { probeMawp } from '@/lib/mawp-api'
import ProjectFileTree from '@/components/ProjectFileTree'
import PhaseDependencyGraph from '@/components/PhaseDependencyGraph'
import { buildLineDiff } from '@/lib/simple-diff'

export default function AdvancedProjectPage() {
  const [online, setOnline] = useState<boolean | null>(null)
  const [projects, setProjects] = useState<AdvancedProject[] | undefined>([])
  const [current, setCurrent] = useState<AdvancedProject | null>(null)
  const [title, setTitle] = useState('邻智云 AI 社区')
  const [busy, setBusy] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [batchGenerating, setBatchGenerating] = useState(false)
  const [lastGen, setLastGen] = useState<{
    phase_id: string
    written: string[]
    via?: string
    changed_files?: string[]
    task_runs?: AdvancedPhase['task_runs']
    testing?: AdvancedPhase['testing']
  } | null>(null)
  const [treePaths, setTreePaths] = useState<string[]>([])
  const [treeLoading, setTreeLoading] = useState(false)
  const [previewPath, setPreviewPath] = useState<string | null>(null)
  const [previewContent, setPreviewContent] = useState('')
  const [previewLoading, setPreviewLoading] = useState(false)
  const [diffMode, setDiffMode] = useState(false)
  const [prevSnapshots, setPrevSnapshots] = useState<Record<string, string>>({})
  const fileRef = useRef<HTMLInputElement>(null)

  const loadTree = async (projectId: string) => {
    setTreeLoading(true)
    try {
      const res = await fetchAdvancedProjectTree(projectId)
      setTreePaths(res.paths || [])
    } catch {
      setTreePaths([])
    } finally {
      setTreeLoading(false)
    }
  }

  const refresh = async () => {
    try {
      const { projects: list } = await listAdvancedProjects()
      setProjects(Array.isArray(list) ? list : [])
      if (current) {
        const found = list?.find((p) => p.id === current.id)
        if (found) setCurrent(found)
      }
    } catch {
      setProjects([])
    }
  }

  useEffect(() => {
    ;(async () => {
      const health = await probeMawp()
      setOnline(Boolean(health))
      if (health) await refresh()
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (current?.id && online) {
      void loadTree(current.id)
    } else {
      setTreePaths([])
    }
    setPreviewPath(null)
    setPreviewContent('')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current?.id, online])

  const deltaPaths = useMemo(() => {
    const fromGen = lastGen?.changed_files || lastGen?.written || []
    const fromPhases = current?.phases?.flatMap((p) => p.generated_files || []) || []
    return [...new Set([...fromGen, ...fromPhases])]
  }, [lastGen, current])

  const openWorkspaceFile = async (path: string) => {
    if (!current) return
    setPreviewPath(path)
    setPreviewLoading(true)
    try {
      const res = await fetchAdvancedProjectFile(current.id, path)
      const text = res.truncated
        ? `${res.content}\n\n…（已截断，完整文件请本地打开）`
        : res.content
      const baseline = prevSnapshots[path]
      if (baseline === undefined) {
        setPrevSnapshots((prev) => ({ ...prev, [path]: text }))
        setDiffMode(false)
      } else if (baseline !== text) {
        setDiffMode(true)
      } else {
        setDiffMode(false)
      }
      setPreviewContent(text)
    } catch (err) {
      setPreviewContent('')
      toast.error(err instanceof Error ? err.message : '读取文件失败')
    } finally {
      setPreviewLoading(false)
    }
  }

  const diffLines =
    previewPath && diffMode && prevSnapshots[previewPath] !== undefined
      ? buildLineDiff(prevSnapshots[previewPath], previewContent)
      : null

  const commitPreviewAsBaseline = () => {
    if (!previewPath) return
    setPrevSnapshots((prev) => ({ ...prev, [previewPath]: previewContent }))
    setDiffMode(false)
    toast.success('已将当前内容设为对照基线')
  }

  const onUpload = async (file: File | null) => {
    if (!file) return
    if (!online) {
      toast.error('请先启动后端：npm run backend:serve')
      return
    }
    setBusy(true)
    try {
      const { project } = await createAdvancedProject({
        title: title.trim() || file.name.replace(/\.docx$/i, ''),
        file,
      })
      setCurrent(project)
      toast.success(`已入库并拆分 ${(project.phases?.length ?? 0)} 个里程碑`)
      await refresh()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '创建失败')
    } finally {
      setBusy(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const onGenerate = async (verifyOnly = false) => {
    if (!current) return
    setGenerating(true)
    try {
      const result = await generateAdvancedPhase(current.id, {
        verifyOnly,
      })
      setCurrent(result.project)
      setLastGen({
        phase_id: result.phase_id,
        written: result.written || [],
        via: result.via,
        changed_files: result.changed_files,
        task_runs: result.task_runs,
        testing: result.testing,
      })
      await loadTree(current.id)
      const pass = result.testing?.passed
      toast.success(
        `${verifyOnly ? '已验收' : '已生成'} ${result.phase_id}（${result.via || 'deliver'}）${
          pass === undefined ? '' : pass ? ' · 冒烟通过' : ' · 冒烟未过'
        }`,
      )
      await refresh()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '生成失败')
    } finally {
      setGenerating(false)
    }
  }

  const remainingCount = useMemo(() => {
    if (!current?.phases?.length) return 0
    // 与后端 ready_pending 一致：partial/failed 不会被一键生成拾取
    return (
      current.phases?.filter(
        (p) => p.status !== 'done' && p.status !== 'partial' && p.status !== 'failed',
      ).length || 0
    )
  }, [current])

  const onGenerateRemaining = async () => {
    if (!current || remainingCount <= 0) return
    setBatchGenerating(true)
    try {
      const result = await generateAdvancedRemaining(current.id)
      setCurrent(result.project)
      const last = result.results?.[result.results.length - 1]
      if (last?.phase_id) {
        setLastGen({
          phase_id: last.phase_id,
          written: last.written || [],
          via: last.via,
          changed_files: last.changed_files,
          task_runs: last.task_runs,
          testing: last.testing,
        })
      }
      await loadTree(current.id)
      toast.success(
        `已生成 ${result.generated_count} 个里程碑${
          result.waves && result.waves.length > 1
            ? ` · ${result.waves.length} 个依赖波次`
            : ''
        }${result.stopped_early ? '（冒烟失败提前停止）' : ''}`,
      )
      await refresh()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '批量生成失败')
    } finally {
      setBatchGenerating(false)
    }
  }

  return (
    <div className="space-y-6 p-6 max-w-5xl">
      {/* 顶部标题 */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-display font-bold tracking-tight">
            高级项目 · 分期交付
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            上传 SRS/DOCX 后拆里程碑；「生成当前期」会调用 WorkWings 9 Agent 编排
            写入独立工作区（有 API Key 时走 LLM，否则多文件骨架兜底）。
          </p>
        </div>
        <Badge variant="outline" className="text-xs">
          {online === null
            ? '检测内核…'
            : online
              ? 'WorkWings 在线'
              : '内核离线'}
        </Badge>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">1. 导入需求规格</CardTitle>
          <CardDescription>
            支持 .docx / .md / .txt。建议直接上传《需求规格说明书》。
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="text-xs text-muted-foreground">项目标题</label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="邻智云 AI 社区"
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              className="pressable"
              disabled={busy || !online}
              onClick={() => fileRef.current?.click()}
            >
              {busy ? (
                <Loader2 className="size-4 mr-2 animate-spin" />
              ) : (
                <Upload className="size-4 mr-2" />
              )}
              上传 DOCX / MD
            </Button>
            <input
              ref={fileRef}
              type="file"
              accept=".docx,.md,.txt,.markdown"
              className="hidden"
              onChange={(e) => void onUpload(e.target.files?.[0] || null)}
            />
          </div>
        </CardContent>
      </Card>

      {current ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Sparkles className="size-4 text-primary" />
              {current.title}
            </CardTitle>
            <CardDescription className="space-y-1">
              <div>ID：{current.id}</div>
              <div className="flex items-start gap-1">
                <FolderOpen className="size-3.5 mt-0.5 shrink-0" />
                <span className="break-all">{current.workspace}</span>
              </div>
              <div className="flex flex-wrap gap-2 pt-1">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs pressable"
                  onClick={async () => {
                    try {
                      await copyAdvancedWorkspacePath(current.workspace)
                      toast.success('已复制工作区路径')
                    } catch {
                      toast.error('复制失败，请手动选择路径')
                    }
                  }}
                >
                  <Copy className="size-3 mr-1.5" />
                  复制路径
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs pressable"
                  asChild
                >
                  <a
                    href={advancedProjectExportUrl(current.id)}
                    download={`${current.id}.zip`}
                  >
                    <Download className="size-3 mr-1.5" />
                    导出 ZIP
                  </a>
                </Button>
              </div>
              <div>规格字符数：{current.srs_chars}</div>
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <PhaseDependencyGraph
              phases={current.phases}
              currentPhaseId={current.current_phase_id}
            />

            {current.gap_summary &&
            (current.gap_summary.missing?.length ||
              current.gap_summary.partial?.length ||
              current.gap_summary.completed?.length) ? (
              <div className="rounded-xl border border-border px-3 py-3 space-y-2 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <div className="font-medium text-sm">产物差距（对标 SRS）</div>
                  {current.gap_summary.files?.[0] ? (
                    <button
                      type="button"
                      className="text-[11px] text-primary hover:underline"
                      onClick={() =>
                        void openWorkspaceFile(current.gap_summary!.files![0])
                      }
                    >
                      打开 GAP_WITH_SRS.md
                    </button>
                  ) : null}
                </div>
                {current.gap_summary.completed?.length ? (
                  <p className="text-emerald-700">
                    已完成：{current.gap_summary.completed.join('、')}
                  </p>
                ) : null}
                {current.gap_summary.partial?.length ? (
                  <p className="text-amber-700">
                    部分占位：{current.gap_summary.partial.join('、')}
                  </p>
                ) : null}
                {current.gap_summary.missing?.length ? (
                  <p className="text-red-700">
                    未实现：{current.gap_summary.missing.join('、')}
                  </p>
                ) : null}
                {current.gap_summary.next_tasks?.length ? (
                  <div>
                    <div className="text-muted-foreground mb-1">建议下一步</div>
                    <ul className="list-disc pl-4 space-y-0.5">
                      {current.gap_summary.next_tasks.slice(0, 8).map((t) => (
                        <li key={`${t.capability_id}-${t.title}`}>
                          [{t.priority || 'P1'}] {t.title}
                          {t.suggested_phase
                            ? ` → ${String(t.suggested_phase).toUpperCase()}`
                            : ''}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            ) : null}

            <div className="grid gap-3 md:grid-cols-2">
              <ProjectFileTree
                paths={treePaths}
                title={treeLoading ? '工程树加载中…' : '工作区工程树'}
                emptyText="工作区尚无文件，生成一期后会出现目录结构"
                onOpenFile={(p) => void openWorkspaceFile(p)}
                activePath={previewPath}
              />
              <ProjectFileTree
                paths={deltaPaths}
                title="本期 / 最近变更"
                emptyText="生成后显示 changed_files"
                onOpenFile={(p) => void openWorkspaceFile(p)}
                activePath={previewPath}
              />
            </div>

            {previewPath ? (
              <div className="rounded-xl border border-border overflow-hidden">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/70 bg-muted/30 px-3 py-2">
                  <span className="truncate text-xs font-medium">{previewPath}</span>
                  <div className="flex items-center gap-1">
                    <Button
                      type="button"
                      variant={diffMode ? 'default' : 'outline'}
                      size="sm"
                      className="h-7 text-xs"
                      disabled={!prevSnapshots[previewPath]}
                      onClick={() => setDiffMode((v) => !v)}
                    >
                      {diffMode ? '对照中' : '与基线对照'}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={commitPreviewAsBaseline}
                    >
                      设为基线
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={() => {
                        setPreviewPath(null)
                        setPreviewContent('')
                        setDiffMode(false)
                      }}
                    >
                      关闭
                    </Button>
                  </div>
                </div>
                {previewLoading ? (
                  <pre className="max-h-72 overflow-auto p-3 text-[11px]">读取中…</pre>
                ) : diffMode && diffLines ? (
                  <div className="max-h-72 overflow-auto p-2 font-mono text-[11px] leading-relaxed">
                    {diffLines.map((line, idx) => (
                      <div
                        key={`${idx}-${line.type}`}
                        className={
                          line.type === 'add'
                            ? 'bg-emerald-500/10 text-emerald-800 dark:text-emerald-300'
                            : line.type === 'del'
                              ? 'bg-rose-500/10 text-rose-800 dark:text-rose-300'
                              : 'text-foreground/80'
                        }
                      >
                        <span className="inline-block w-4 opacity-60">
                          {line.type === 'add' ? '+' : line.type === 'del' ? '-' : ' '}
                        </span>
                        {line.text || ' '}
                      </div>
                    ))}
                  </div>
                ) : (
                  <pre className="max-h-72 overflow-auto p-3 text-[11px] leading-relaxed font-mono whitespace-pre-wrap break-all">
                    {previewContent || '（空文件）'}
                  </pre>
                )}
              </div>
            ) : null}

            <div className="space-y-2">
              {current.phases?.map((phase) => (
                <div
                  key={phase.id}
                  className={`rounded-xl border px-3 py-2.5 ${
                    phase.id === current.current_phase_id
                      ? 'border-primary/40 bg-primary/5'
                      : 'border-border'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="font-medium text-sm">
                      {phase.id.toUpperCase()} · {phase.title}
                    </div>
                    <Badge
                      variant="outline"
                      className={
                        phase.status === 'done'
                          ? 'text-emerald-600 border-emerald-500/30'
                          : phase.status === 'partial'
                            ? 'text-amber-700 border-amber-500/30'
                            : phase.status === 'failed'
                              ? 'text-red-600 border-red-500/30'
                              : ''
                      }
                    >
                      {phase.status === 'done' ? (
                        <span className="inline-flex items-center gap-1">
                          <CheckCircle2 className="size-3" /> 真正完成
                        </span>
                      ) : phase.status === 'partial' ? (
                        <span className="inline-flex items-center gap-1">
                          <AlertTriangle className="size-3" /> 部分完成
                        </span>
                      ) : phase.status === 'failed' ? (
                        <span className="inline-flex items-center gap-1">
                          <XCircle className="size-3" /> 失败
                        </span>
                      ) : phase.id === current.current_phase_id ? (
                        '当前期'
                      ) : (
                        phase.status
                      )}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">{phase.goal}</p>
                  {phase.degraded || phase.validation?.placeholder || phase.validation?.spec_gaps?.length ? (
                    <p className="text-[11px] text-amber-700 mt-1">
                      {phase.degraded ? '模板降级，未算真正完成。' : ''}
                      {phase.validation?.placeholder ? ' 检出通用占位条目。' : ''}
                      {phase.validation?.spec_gaps?.length
                        ? ` 缺口：${phase.validation.spec_gaps.join('、')}`
                        : ''}
                    </p>
                  ) : null}
                  {typeof phase.attempts === 'number' && phase.attempts > 1 ? (
                    <p className="text-[11px] text-muted-foreground mt-1">
                      重试 {phase.attempts} 次
                    </p>
                  ) : null}
                  {phase.generated_files?.length ? (
                    <p className="text-[11px] text-muted-foreground mt-1">
                      文件：{phase.generated_files.join(' · ')}
                    </p>
                  ) : null}
                  {phase.testing ? (
                    <p className="text-[11px] mt-1">
                      验收：
                      <span
                        className={
                          phase.testing.passed
                            ? 'text-emerald-600'
                            : 'text-amber-700'
                        }
                      >
                        {phase.testing.passed ? '通过' : '未过'}
                      </span>
                      {phase.testing.log_summary
                        ? ` · ${phase.testing.log_summary.slice(0, 120)}`
                        : ''}
                    </p>
                  ) : null}
                  {phase.task_runs?.length ? (
                    <p className="text-[11px] text-muted-foreground mt-1">
                      {phase.task_runs.length >= 2
                        ? `已拆成 ${phase.task_runs.length} 个子任务：`
                        : '任务循环：'}
                      {phase.task_runs
                        .map(
                          (t) =>
                            `${t.task_id || '?'}${
                              t.success === false ? '✗' : '✓'
                            }`,
                        )
                        .join(' · ')}
                    </p>
                  ) : null}
                </div>
              ))}
            </div>

            {lastGen ? (
              <div className="rounded-xl border border-border bg-muted/30 px-3 py-3 space-y-2 text-xs">
                <div className="font-medium text-sm">
                  最近生成 · {lastGen.phase_id}
                  {lastGen.via ? (
                    <span className="text-muted-foreground font-normal">
                      {' '}
                      · {lastGen.via}
                    </span>
                  ) : null}
                </div>
                {(lastGen.changed_files || lastGen.written)?.length ? (
                  <div>
                    <div className="text-muted-foreground mb-1">changed_files</div>
                    <ul className="list-disc pl-4 space-y-0.5 break-all">
                      {(lastGen.changed_files || lastGen.written)
                        .slice(0, 24)
                        .map((f) => (
                          <li key={f}>{f}</li>
                        ))}
                    </ul>
                  </div>
                ) : null}
                {lastGen.testing ? (
                  <div>
                    <div className="text-muted-foreground mb-1">冒烟验收</div>
                    <p>
                      {lastGen.testing.passed ? 'PASS' : 'FAIL'} ·{' '}
                      {lastGen.testing.metric_command || '—'}
                    </p>
                    {lastGen.testing.log_summary ? (
                      <p className="text-muted-foreground mt-1 break-all">
                        {lastGen.testing.log_summary}
                      </p>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ) : null}

            <div className="flex flex-wrap gap-2">
              <Button
                className="pressable"
                disabled={generating || batchGenerating}
                onClick={() => void onGenerate()}
              >
                {generating ? (
                  <Loader2 className="size-4 mr-2 animate-spin" />
                ) : (
                  <Play className="size-4 mr-2" />
                )}
                生成当前期（P1 全量 · 后期短链）
              </Button>
              <Button
                variant="outline"
                className="pressable"
                disabled={generating || batchGenerating || !current}
                onClick={() => void onGenerate(true)}
              >
                {generating ? (
                  <Loader2 className="size-4 mr-2 animate-spin" />
                ) : (
                  <CheckCircle2 className="size-4 mr-2" />
                )}
                只验收当前期
              </Button>
              <Button
                variant="secondary"
                className="pressable"
                disabled={
                  generating || batchGenerating || remainingCount <= 0
                }
                onClick={() => void onGenerateRemaining()}
              >
                {batchGenerating ? (
                  <Loader2 className="size-4 mr-2 animate-spin" />
                ) : (
                  <Sparkles className="size-4 mr-2" />
                )}
                一键生成剩余里程碑
                {remainingCount > 0 ? `（${remainingCount}）` : ''}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              「生成当前期」P1 走完整链，P2+ 只跑编码/前端/冒烟。已有代码请用「只验收」，不会再生成。冒烟失败可能提前停止。
              生成后请到工作区启动：
              <code className="mx-1">apps/api</code>
              uvicorn :8001 +
              <code className="mx-1">apps/web</code>
              静态页。
            </p>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">最近高级项目</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {(projects?.length ?? 0) === 0 ? (
            <p className="text-sm text-muted-foreground">暂无。请先上传需求文档。</p>
          ) : (
            (projects || []).map((p) => (
              <button
                key={p.id}
                type="button"
                className="w-full text-left rounded-xl border border-border px-3 py-2.5 hover:bg-muted/50 pressable"
                onClick={() => setCurrent(p)}
              >
                <div className="flex items-center gap-2 text-sm font-medium">
                  <FileText className="size-4 text-muted-foreground" />
                  {p.title}
                </div>
                <div className="text-[11px] text-muted-foreground mt-1">
                  {(p.phases?.length ?? 0)} 期 · {p.status} · {p.source_filename}
                </div>
              </button>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  )
}
