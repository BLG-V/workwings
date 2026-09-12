import { useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Sparkles,
  Wand2,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Loader2,
  Copy,
  Workflow,
  PlayCircle,
  Eraser,
  MonitorPlay,
  FolderDown,
  FolderOpen,
  X,
  RotateCcw,
  Activity,
  History,
  Archive,
} from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import ProjectFileTree from '@/components/ProjectFileTree'
import ProjectExplorer from '@/components/ProjectExplorer'
import ModelSwitcher from '@/components/ModelSwitcher'
import RunMonitor from '@/components/RunMonitor'
import VersionManager from '@/components/VersionManager'
import VersionPanel from '@/components/VersionPanel'
import {
  STUDIO_KERNEL_HINT,
  STUDIO_META,
  STUDIO_ORDER,
  extractTopic,
  getNextStudio,
  getPrevStudio,
  type StudioPageKind,
} from '@/lib/chat-intent'
import { buildResultForNode } from '@/lib/pipeline'
import { generateStudioOutput } from '@/lib/studio-generate'
import {
  clearPipelineSession,
  flowNavState,
  getPipelineTopic,
  isPipelineActive,
  markStageCompleted,
  readCompletedStages,
  readStudioDraft,
  resolveStagePrompt,
  startPipelineFlow,
  writeStudioDraft,
} from '@/lib/studio-session'
import {
  formatStageMarkdown,
  getActivePlatformRunId,
  hydrateAllStudioDraftsFromRun,
  runDeliverPipeline,
  studioKindFromNode,
} from '@/lib/studio-mawp'
import { probeMawp } from '@/lib/mawp-api'
import { createProject, resolveWorkflowPath, updateProject } from '@/lib/projects-store'
import type { NodeType } from '@/lib/workflow-types'
import PipelineFlowchart from '@/components/PipelineFlowchart'
import CoreFlowBar from '@/components/CoreFlowBar'
import ThinkingProcess from '@/components/ThinkingProcess'
import CodePreviewDialog from '@/components/CodePreviewDialog'
import FileDiffPreview, { FileChangesSummary } from '@/components/FileDiffPreview'
import { buildCodePreview } from '@/lib/code-preview'
import {
  previewProjectTree,
  saveProjectToLocal,
} from '@/lib/save-project-local'
import {
  listProjectFiles,
  readProjectFile,
} from '@/lib/mawp-api'

const KIND_TO_NODE: Record<StudioPageKind, NodeType> = {
  requirement: 'analysis',
  architecture: 'architecture',
  code: 'development',
  test: 'testing',
  deploy: 'deployment',
}

const NODE_TO_KIND: Partial<Record<NodeType, StudioPageKind>> = {
  analysis: 'requirement',
  architecture: 'architecture',
  development: 'code',
  testing: 'test',
  deployment: 'deploy',
}

function readCompleted(): StudioPageKind[] {
  return readCompletedStages()
}

function markCompleted(kind: StudioPageKind) {
  markStageCompleted(kind)
}

function buildStudioThinking(kind: StudioPageKind, source: string): string[] {
  const meta = STUDIO_META[kind]
  const brief = source.slice(0, 20) || '当前目标'
  return [
    `解析输入目标：「${brief}${source.length > 20 ? '…' : ''}」`,
    `定位阶段能力：${meta.title}`,
    ...meta.steps.map((s) => `执行子步骤：${s}`),
    '校验输出结构与可落地性',
    '汇总生成最终结果',
  ]
}

export default function StudioPage() {
  const { kind } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const studioKind: StudioPageKind = STUDIO_ORDER.includes(kind as StudioPageKind)
    ? (kind as StudioPageKind)
    : 'requirement'
  const meta = STUDIO_META[studioKind]
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const state = (location.state || {}) as {
    prompt?: string
    topic?: string
    fromChat?: boolean
    continueFlow?: boolean
    clearFlow?: boolean
  }

  const chatSeedRef = useRef(state.prompt || '')
  const abortRef = useRef<AbortController | null>(null)
  const [prompt, setPrompt] = useState('')
  const [projectMode, setProjectMode] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [progress, setProgress] = useState(0)
  const [activeStep, setActiveStep] = useState(-1)
  const [output, setOutput] = useState('')
  const [done, setDone] = useState(false)
  const [demoOpen, setDemoOpen] = useState(false)
  const [demoContent, setDemoContent] = useState('')
  const [previewOpen, setPreviewOpen] = useState(false)
  const [savingProject, setSavingProject] = useState(false)
  const [exportOpen, setExportOpen] = useState(false)
  const [exportTree, setExportTree] = useState('')
  const [exportTitle, setExportTitle] = useState('')
  const [isDemo, setIsDemo] = useState(false)
  const [thinkingSteps, setThinkingSteps] = useState<string[]>([])
  const [thinkingDone, setThinkingDone] = useState(false)
  const [completed, setCompleted] = useState<StudioPageKind[]>(() => readCompleted())
  const [deliverPaths, setDeliverPaths] = useState<string[]>([])
  const [deliverRoot, setDeliverRoot] = useState<string | null>(null)
  const [showExplorer, setShowExplorer] = useState(false)
  const [showMonitor, setShowMonitor] = useState(false)
  const [showVersions, setShowVersions] = useState(false)
  const [projectFiles, setProjectFiles] = useState<string[]>([])
  const [diffOpen, setDiffOpen] = useState(false)
  const [diffPath, setDiffPath] = useState<string>('')
  const [diffOldContent, setDiffOldContent] = useState<string>('')
  const [fileChanges, setFileChanges] = useState<{path: string; has_diff: boolean; old_size: number; new_size: number}[]>([])
  const [loadingFiles, setLoadingFiles] = useState(false)

  const resetRuntime = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    abortRef.current?.abort()
    abortRef.current = null
    setGenerating(false)
    setProgress(0)
    setActiveStep(-1)
  }

  // 仅「一轮完整流程」内保留各页内容；侧栏直进 / 清空标记时重置
  useEffect(() => {
    resetRuntime()
    setCompleted(readCompleted())

    const fromChat = Boolean(state.fromChat && state.prompt?.trim())
    if (fromChat) {
      // 从对话点「前往」进来：只预填目标，不自动开跑，避免用户还没看完回答就被流水线带走
      startPipelineFlow(state.prompt!, state.topic)
      chatSeedRef.current = state.prompt!.trim()
      setPrompt(chatSeedRef.current)
      setOutput('')
      setDone(false)
      setIsDemo(false)
      setThinkingSteps([])
      setThinkingDone(false)
      toast.message('已带入对话目标', {
        description: '确认后启动 WorkWings Agent 编排即可',
      })
      return
    }

    if (state.clearFlow || !isPipelineActive()) {
      clearPipelineSession()
      chatSeedRef.current = ''
      setPrompt('')
      setOutput('')
      setDone(false)
      setIsDemo(false)
      setThinkingSteps([])
      setThinkingDone(false)
      setProgress(0)
      setActiveStep(-1)
      setCompleted([])
      return
    }

    // 流程进行中：恢复本阶段草稿
    const draft = readStudioDraft(studioKind)
    const restoredPrompt = resolveStagePrompt(studioKind)
    chatSeedRef.current = restoredPrompt
    setPrompt(restoredPrompt)
    setOutput(draft?.output || '')
    setDone(Boolean(draft?.done && draft?.output))
    setIsDemo(Boolean(draft?.isDemo))
    setThinkingSteps(draft?.thinkingSteps || [])
    setThinkingDone(Boolean(draft?.thinkingDone))
    setProgress(draft?.done && draft?.output ? 100 : 0)
    setActiveStep(draft?.done ? (meta?.steps.length ?? 1) - 1 : -1)
    const runId = getActivePlatformRunId()
    if (runId && !draft?.output && restoredPrompt) {
      void hydrateAllStudioDraftsFromRun(runId, restoredPrompt)
        .then(() => {
          const next = readStudioDraft(studioKind)
          if (!next?.output) return
          setOutput(next.output)
          setDone(true)
          setIsDemo(false)
          setThinkingSteps(next.thinkingSteps || [])
          setThinkingDone(true)
          setProgress(100)
          setActiveStep((meta?.steps.length ?? 1) - 1)
          for (const k of STUDIO_ORDER) markCompleted(k)
          setCompleted(readCompleted())
        })
        .catch(() => {
          /* 保留空结果，让用户手动刷新 */
        })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [studioKind, location.key])

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
      abortRef.current?.abort()
    }
  }, [])

  const nodeType = KIND_TO_NODE[studioKind]
  const nextKind = getNextStudio(studioKind)
  const prevKind = getPrevStudio(studioKind)

  const fakeNodes = useMemo(
    () =>
      STUDIO_ORDER.map((k) => {
        const nType = KIND_TO_NODE[k]
        let status: 'waiting' | 'running' | 'completed' = 'waiting'
        const currentIdx = STUDIO_ORDER.indexOf(studioKind)
        const thisIdx = STUDIO_ORDER.indexOf(k)
        const wasDone = completed.includes(k)
        if (k === studioKind) {
          status = done ? 'completed' : generating ? 'running' : 'waiting'
        } else if (wasDone || thisIdx < currentIdx) {
          status = 'completed'
        }
        return {
          id: `n-${k}`,
          agentId: '1',
          type: nType,
          label: STUDIO_META[k].title,
          icon: '✨',
          position: { x: 0, y: 0 },
          config: {
            model: 'WorkWings 配置',
            prompt: '',
            inputSource: '',
            outputTarget: '',
          },
          status,
        }
      }),
    [studioKind, done, generating, completed],
  )

  if (!meta) {
    return (
      <div className="p-8">
        <p>未知工作台</p>
        <Button className="mt-4" onClick={() => navigate('/chat')}>
          返回对话
        </Button>
      </div>
    )
  }

  const handleGenerate = async (auto = false, seed?: string) => {
    const source = (seed ?? prompt).trim()
    if (!source) {
      toast.error('请先在「输入目标」中填写内容')
      return
    }
    if (timerRef.current) clearInterval(timerRef.current)
    abortRef.current?.abort()
    const abort = new AbortController()
    abortRef.current = abort

    const topic =
      state.topic?.trim() ||
      getPipelineTopic() ||
      extractTopic(source) ||
      source.slice(0, 24)

    // 在工作台手动开跑也视为开启一轮流程
    if (!isPipelineActive()) {
      startPipelineFlow(source, topic)
    }
    const allThinking = buildStudioThinking(studioKind, source)
    setGenerating(true)
    setDone(false)
    setIsDemo(false)
    setOutput('')
    setProgress(8)
    setActiveStep(0)
    setThinkingDone(false)
    setThinkingSteps([allThinking[0]])

    const steps = meta.steps
    let step = 0
    timerRef.current = setInterval(() => {
      step += 1
      setActiveStep(Math.min(step, steps.length - 1))
      setProgress(Math.min(30, 5 + step * 3))
      setThinkingSteps(allThinking.slice(0, Math.min(allThinking.length, step + 2)))
      if (step >= steps.length && timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
    }, 450)

    try {
      const mawpOnline = Boolean(await probeMawp())
      let content = ''
      let thinking = allThinking
      let fromPlatform = false

      if (mawpOnline) {
        const runId = getActivePlatformRunId()
        const refreshOnly = studioKind !== 'requirement'

        if (refreshOnly && !runId) {
          throw new Error('NO_ACTIVE_RUN')
        }

        if (refreshOnly && runId) {
          const { stages } = await hydrateAllStudioDraftsFromRun(runId, source)
          if (abort.signal.aborted) return
          content = formatStageMarkdown(studioKind, stages, source)
          thinking = [
            ...allThinking,
            `复用平台 Run ${runId}`,
            '本阶段已由 WorkWings Agent 主链产出，未新开一轮',
          ]
          fromPlatform = true
          for (const k of STUDIO_ORDER) markCompleted(k)
          setCompleted(readCompleted())
        } else {
          const delivered = await runDeliverPipeline({
            goal: source,
            topic,
            projectName: topic,
            projectMode,
            signal: abort.signal,
            onProgress: ({ currentNode, run, event, statusEvent }) => {
              // SSE 事件：更精细的实时反馈
              if (event) {
                const evtType = event.type || ''
                const nodeId = event.node_id || currentNode || ''
                const mapped = studioKindFromNode(nodeId)
                const statusText = event.status || ''
                const agentName = event.agent || ''

                setThinkingSteps((prev) => {
                  let tip = ''
                  if (evtType === 'node_start') {
                    tip = `▶ 节点启动：${nodeId}${agentName ? `（${agentName}）` : ''}${mapped ? ` → ${STUDIO_META[mapped].title}` : ''}`
                  } else if (evtType === 'node_end') {
                    tip = `✓ 节点完成：${nodeId}${statusText ? ` · ${statusText}` : ''}`
                  } else if (evtType === 'node_retry') {
                    tip = `↻ 重试 ${event.attempt}/${event.max_retries}：${nodeId}（${event.error?.slice(0, 80) || ''}）`
                  } else if (evtType === 'heal_attempt') {
                    tip = `↻ 自愈 ${event.round}/${event.max_rounds}：${event.reason || ''} ${event.from || nodeId}→${event.to || ''}${event.selected_model ? ` · ${event.selected_model}` : ''}`
                  } else if (evtType === 'heal_handoff') {
                    tip = `⚑ 自愈轮次用尽，等待确认：${event.reason || ''}`
                  } else if (evtType === 'run_start') {
                    tip = `🚀 工作流启动：${run.run_id}`
                  } else {
                    tip = `${evtType}：${nodeId}`
                  }
                  if (prev.includes(tip)) return prev
                  return [...prev.slice(0, 12), tip]
                })
                return
              }

              // 状态快照：更新进度条
              if (statusEvent) {
                const completed = statusEvent.completed_nodes || 0
                const total = statusEvent.total_nodes || 8
                const pct = Math.min(95, 10 + Math.round((completed / total) * 80))
                setProgress(pct)

                const mapped = studioKindFromNode(currentNode)
                setThinkingSteps((prev) => {
                  const tip = `MAWP · ${run.status} · 节点 ${currentNode || '…'}${
                    mapped ? `（${STUDIO_META[mapped].title}）` : ''
                  } · ${completed}/${total}`
                  if (prev.some((s) => s.includes(currentNode || '___'))) return prev
                  return [...prev.slice(0, 12), tip]
                })

                const idx = STUDIO_ORDER.indexOf(mapped || studioKind)
                if (idx >= 0) {
                  setActiveStep(Math.min(idx, steps.length - 1))
                }
                return
              }

              // 降级轮询的回调
              const mapped = studioKindFromNode(currentNode)
              setThinkingSteps((prev) => {
                const tip = `MAWP · ${run.status} · 节点 ${currentNode || '…'}${
                  mapped ? `（${STUDIO_META[mapped].title}）` : ''
                }`
                if (prev.includes(tip)) return prev
                return [...prev.slice(0, 12), tip]
              })
              const idx = STUDIO_ORDER.indexOf(mapped || studioKind)
              if (idx >= 0) {
                setActiveStep(Math.min(idx, steps.length - 1))
                setProgress(Math.min(92, 12 + idx * 16))
              }
            },
          })
          if (delivered.projectRoot) {
            toast.success(`工程写入：${delivered.projectRoot}`)
            setDeliverRoot(delivered.projectRoot)
          }
          if (abort.signal.aborted) return
          content = formatStageMarkdown(studioKind, delivered.stages, source)
          const codeStage = (delivered.stages?.code || {}) as Record<string, unknown>
          const frontend = (codeStage.frontend || {}) as Record<string, unknown>
          const paths = [
            ...((codeStage.changed_files as string[]) || []),
            ...((frontend.artifacts as string[]) || []),
          ].filter(Boolean)
          setDeliverPaths([...new Set(paths)])
          thinking = [
            ...allThinking,
            `平台 Run ${delivered.run.run_id}`,
            delivered.projectRoot
              ? `大项目工作区 ${delivered.projectRoot}`
              : 'WorkWings 9 Agent 编排已完成，五阶段草稿已写入',
          ]
          fromPlatform = true
          for (const k of STUDIO_ORDER) markCompleted(k)
          setCompleted(readCompleted())
        }
      } else {
        const generated = await generateStudioOutput({
          kind: studioKind,
          source,
          topic,
          signal: abort.signal,
        })
        if (abort.signal.aborted) return
        content = generated.content
        thinking = [
          ...allThinking,
          ...generated.thinking.filter((t) => !allThinking.includes(t)),
          'WorkWings 离线，已回退 DeepSeek 单阶段生成',
        ]
      }

      if (abort.signal.aborted) return
      if (timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
      setOutput(content)
      setThinkingSteps(thinking)
      setThinkingDone(true)
      setProgress(100)
      setActiveStep(steps.length - 1)
      setGenerating(false)
      setDone(true)
      writeStudioDraft(studioKind, {
        prompt: source,
        output: content,
        done: true,
        isDemo: false,
        thinkingSteps: thinking,
        thinkingDone: true,
      })
      markCompleted(studioKind)
      setCompleted(readCompleted())
      toast.success(
        auto
          ? `${meta.title}已完成`
          : fromPlatform
            ? studioKind === 'requirement'
              ? 'WorkWings Agent 编排已完成'
              : '已从本次 Run 刷新本页'
            : '生成完成',
      )
    } catch (err) {
      if ((err as Error)?.name === 'AbortError') return
      if ((err as Error)?.message === 'ABORTED') return
      if ((err as Error)?.message === 'NO_ACTIVE_RUN') {
        if (timerRef.current) {
          clearInterval(timerRef.current)
          timerRef.current = null
        }
        setGenerating(false)
        setProgress(0)
        setActiveStep(-1)
        toast.info('请先在需求分析启动 WorkWings Agent 编排', {
          description: '五阶段共用同一次 Run，本页不新开一轮',
        })
        return
      }
      if (timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }

      // 平台失败则再试 DeepSeek；再失败才本地草案
      const offlineOrFail = err instanceof Error ? err.message : '生成失败'
      try {
        if (offlineOrFail !== 'MAWP_OFFLINE') {
          toast.message('平台执行异常，改用 DeepSeek…', {
            description: offlineOrFail,
          })
        }
        const generated = await generateStudioOutput({
          kind: studioKind,
          source,
          topic,
          signal: abort.signal,
        })
        if (abort.signal.aborted) return
        const thinking = [
          ...allThinking,
          ...generated.thinking.filter((t) => !allThinking.includes(t)),
        ]
        setOutput(generated.content)
        setThinkingSteps(thinking)
        setThinkingDone(true)
        setProgress(100)
        setActiveStep(steps.length - 1)
        setGenerating(false)
        setDone(true)
        writeStudioDraft(studioKind, {
          prompt: source,
          output: generated.content,
          done: true,
          isDemo: false,
          thinkingSteps: thinking,
          thinkingDone: true,
        })
        markCompleted(studioKind)
        setCompleted(readCompleted())
        toast.success(auto ? `${meta.title}已完成` : '生成完成')
        return
      } catch (inner) {
        if ((inner as Error)?.name === 'AbortError') return
      }

      // API 失败时仍按用户主题出本地结果，绝不回落到电商样例
      const fallback = buildResultForNode(
        'studio',
        KIND_TO_NODE[studioKind],
        topic,
        source,
      )
      const fallbackContent =
        fallback?.content ||
        `# ${topic}\n\n基于输入已完成生成。\n\n> ${source}`
      const fallbackThinking = [
        ...allThinking,
        `模型调用失败，已按「${topic}」生成本地结构化草案`,
      ]
      setOutput(fallbackContent)
      setThinkingSteps(fallbackThinking)
      setThinkingDone(true)
      setProgress(100)
      setActiveStep(steps.length - 1)
      setGenerating(false)
      setDone(true)
      writeStudioDraft(studioKind, {
        prompt: source,
        output: fallbackContent,
        done: true,
        isDemo: false,
        thinkingSteps: fallbackThinking,
        thinkingDone: true,
      })
      markCompleted(studioKind)
      setCompleted(readCompleted())
      toast.message(auto ? `${meta.title}已用本地草案完成` : '已用本地草案完成', {
        description: offlineOrFail,
      })
    } finally {
      if (abortRef.current === abort) abortRef.current = null
    }
  }

  const showDemo = () => {
    const result = buildResultForNode(
      'studio',
      KIND_TO_NODE[studioKind],
      '智流演示项目',
    )
    const content =
      result?.content ||
      `# ${meta.demoTitle}\n\n这是「${meta.title}」的效果演示示例。`
    setDemoContent(content)
    setDemoOpen(true)
  }

  const applyDemoToResult = () => {
    setOutput(demoContent)
    setDone(true)
    setProgress(100)
    setIsDemo(true)
    setActiveStep(meta.steps.length - 1)
    const steps = [
      '载入效果演示样例',
      `应用阶段模板：${meta.title}`,
      '填充演示结果到输出区',
    ]
    setThinkingSteps(steps)
    setThinkingDone(true)
    writeStudioDraft(studioKind, {
      prompt,
      output: demoContent,
      done: true,
      isDemo: true,
      thinkingSteps: steps,
      thinkingDone: true,
    })
    markCompleted(studioKind)
    setCompleted(readCompleted())
    setDemoOpen(false)
    toast.success('已载入效果演示')
  }

  const goNext = () => {
    if (!nextKind) {
      toast.info('已经是最后一个功能阶段')
      return
    }
    writeStudioDraft(studioKind, { prompt })
    navigate(`/studio/${nextKind}`, { state: flowNavState() })
    toast.success(`进入下一阶段：${STUDIO_META[nextKind].title}`)
  }

  const goPrev = () => {
    if (!prevKind) return
    writeStudioDraft(studioKind, { prompt })
    navigate(`/studio/${prevKind}`, { state: flowNavState() })
  }

  const copyOutput = async () => {
    await navigator.clipboard.writeText(output)
    toast.success('已复制到剪贴板')
  }

  const openCodePreview = () => {
    const built = buildCodePreview(output)
    if (!built.ok) {
      toast.message('暂不能直接预览', { description: built.reason })
      setPreviewOpen(true)
      return
    }
    setPreviewOpen(true)
  }

  const canExportProject =
    (studioKind === 'test' || studioKind === 'deploy') && done

  const handleSaveProject = async (preferZip = false) => {
    setSavingProject(true)
    try {
      const result = await saveProjectToLocal({ preferZip })
      setExportTitle(
        result.mode === 'folder'
          ? `已写入本地文件夹「${result.rootName}」`
          : `已下载 ${result.fileName}`,
      )
      setExportTree(result.tree)
      setExportOpen(true)
      toast.success(
        result.mode === 'folder'
          ? `已创建项目：${result.rootName}（${result.fileCount} 个文件）`
          : `已下载压缩包：${result.fileName}`,
      )
    } catch (err) {
      if ((err as Error)?.name === 'AbortError') {
        toast.message('已取消保存')
      } else {
        toast.error(err instanceof Error ? err.message : '保存项目失败')
      }
    } finally {
      setSavingProject(false)
    }
  }

  const showExportPreview = () => {
    const preview = previewProjectTree()
    setExportTitle(
      `预览：${preview.projectName}（${preview.fileCount} 个文件）`,
    )
    setExportTree(preview.tree)
    setExportOpen(true)
  }

  const handleRetryLastRun = async () => {
    const { retryRun } = await import('@/lib/mawp-api')
    const runId = getActivePlatformRunId()
    if (!runId) {
      toast.message('没有可重试的运行记录')
      return
    }
    try {
      toast.message('正在重试失败的运行…')
      const resumed = await retryRun(runId)
      if (resumed?.run) {
        toast.success('已重新触发运行')
        setDeliverRoot((resumed.run.params?.project_root as string | undefined) || deliverRoot)
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '重试失败')
    }
  }

  const loadProjectFiles = async (root: string) => {
    setLoadingFiles(true)
    try {
      const res = await listProjectFiles(root)
      setProjectFiles(res.paths)
    } catch {
      setProjectFiles([])
    } finally {
      setLoadingFiles(false)
    }
  }

  const openFileDiff = async (path: string) => {
    if (!deliverRoot) return
    try {
      const file = await readProjectFile(deliverRoot, path)
      setDiffPath(path)
      setDiffOldContent(file.content)
      setDiffOpen(true)
    } catch {
      setDiffPath(path)
      setDiffOldContent('')
      setDiffOpen(true)
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-5 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-start gap-3">
          <Button
            variant="ghost"
            size="icon"
            className="mt-0.5 pressable"
            onClick={() => navigate('/chat')}
          >
            <ArrowLeft className="size-4" />
          </Button>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="font-display text-2xl font-semibold tracking-tight">
                {meta.title}
              </h1>
              {state.fromChat && (
                <Badge className="bg-primary/10 text-primary border-primary/20">
                  来自智能对话
                </Badge>
              )}
              {isDemo && (
                <Badge
                  variant="outline"
                  className="text-amber-700 border-amber-300 bg-amber-50"
                >
                  演示结果
                </Badge>
              )}
            </div>
            <p className="text-sm text-muted-foreground mt-1">{meta.subtitle}</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" className="pressable" onClick={showDemo}>
            <PlayCircle className="size-4 mr-2" />
            效果演示查看
          </Button>
          <Button
            variant="secondary"
            className="pressable"
            onClick={() => {
              const goal = prompt.trim()
              const path = resolveWorkflowPath()
              if (path) {
                const id = path.split('/').pop()
                if (id && goal) updateProject(id, { goal })
                navigate(path, { state: { goal, selectAgent: 'requirement' } })
                return
              }
              const project = createProject({
                name: meta.title,
                description: goal.slice(0, 80) || meta.subtitle,
                goal,
              })
              navigate(`/workflow/${project.id}`, {
                state: { goal, selectAgent: 'requirement' },
              })
            }}
          >
            <Workflow className="size-4 mr-2" />
            放入全流程编排
          </Button>
        </div>
      </div>

      <CoreFlowBar active={studioKind} completed={completed} showDemo={false} />

      <div className="rounded-2xl border border-border bg-card/80 p-4">
        <div className="flex items-center justify-between gap-2 mb-1 px-1">
          <p className="text-xs text-muted-foreground">
            点击阶段可跳转；WorkWings Agent 生成完成后可进入下一功能
          </p>
          <div className="flex gap-2">
            <ModelSwitcher />
            <Button
              size="sm"
              variant="ghost"
              className="h-8 gap-1.5 text-xs text-muted-foreground"
              onClick={() => setShowVersions(true)}
              disabled={!deliverRoot}
            >
              <History className="size-3.5" />
              <span className="hidden sm:inline">版本</span>
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="h-8 gap-1.5 text-xs text-muted-foreground"
              onClick={() => setShowMonitor(true)}
              disabled={!Boolean(getActivePlatformRunId())}
            >
              <Activity className="size-3.5" />
              <span className="hidden sm:inline">监控</span>
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="pressable h-8"
              disabled={!prevKind}
              onClick={goPrev}
            >
              <ArrowLeft className="size-3.5 mr-1" />
              上一阶段
            </Button>
            <Button
              size="sm"
              className="pressable h-8"
              disabled={!nextKind || !done}
              onClick={goNext}
            >
              下一阶段
              <ArrowRight className="size-3.5 ml-1" />
            </Button>
          </div>
        </div>
        <PipelineFlowchart
          nodes={fakeNodes}
          activeType={generating ? nodeType : done ? null : nodeType}
          compact
          variant="studio"
          onStageClick={(type) => {
            const target = NODE_TO_KIND[type]
            if (!target) {
              toast.info('文档阶段可在工作流编排中查看')
              return
            }
            if (target === studioKind) return
            navigate(`/studio/${target}`, { state: flowNavState() })
          }}
        />
        <p className="mt-2 px-1 text-[11px] text-muted-foreground">
          本页对应 WorkWings Agent：{STUDIO_KERNEL_HINT[studioKind].agents} ·{' '}
          {STUDIO_KERNEL_HINT[studioKind].note}
        </p>
      </div>

      <div className="grid gap-5 lg:grid-cols-[1fr_1.1fr]">
        <motion.div
          layout
          className="rounded-2xl border border-border bg-card p-5 shadow-sm space-y-4"
        >
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-sm font-medium">
              <div
                className={`size-8 rounded-xl bg-gradient-to-br ${meta.accent} text-white flex items-center justify-center`}
              >
                <Wand2 className="size-4" />
              </div>
              输入目标
            </div>
            <Button
              size="sm"
              variant="ghost"
              className="h-8 pressable text-muted-foreground"
              onClick={() => {
                setPrompt('')
                writeStudioDraft(studioKind, { prompt: '' })
                toast.success('本阶段输入目标已清空')
              }}
            >
              <Eraser className="size-3.5 mr-1" />
              清空
            </Button>
          </div>
          <Textarea
            value={prompt}
            onChange={(e) => {
              const next = e.target.value
              setPrompt(next)
              writeStudioDraft(studioKind, { prompt: next })
            }}
            rows={8}
            placeholder={meta.placeholder}
            className="text-sm"
          />
          <label className="flex items-start gap-2 rounded-xl border border-border/80 bg-muted/30 px-3 py-2 text-xs cursor-pointer select-none">
            <input
              type="checkbox"
              className="mt-0.5"
              checked={projectMode}
              onChange={(e) => setProjectMode(e.target.checked)}
            />
            <span>
              <span className="font-medium text-foreground">WorkWings 工程编排模式</span>
              <span className="block text-muted-foreground mt-0.5">
                开启后 WorkWings 9 Agent 写入独立 workspaces/ 工程目录（API+Web），用于支撑高级大项目生成，而不是改平台自身代码。
              </span>
            </span>
          </label>
          <p className="text-[11px] text-muted-foreground leading-relaxed">
            {STUDIO_KERNEL_HINT[studioKind].note}
          </p>
          <div className="flex flex-wrap gap-2">
            {meta.steps.map((step, i) => (
              <span
                key={step}
                className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                  activeStep === i
                    ? 'border-primary bg-primary/10 text-primary'
                    : activeStep > i
                      ? 'border-emerald-300/80 bg-emerald-50 text-emerald-800'
                      : 'border-border bg-muted/40 text-muted-foreground'
                }`}
              >
                {i + 1}. {step}
              </span>
            ))}
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>生成进度</span>
              <span className="tabular-nums">{progress}%</span>
            </div>
            <Progress value={progress} className="h-1.5" />
          </div>
          <Button
            className="w-full pressable"
            disabled={generating}
            onClick={() => void handleGenerate(false)}
          >
            {generating ? (
              <>
                <Loader2 className="size-4 mr-2 animate-spin" />
                {studioKind === 'requirement' ? 'WorkWings Agent 编排执行中…' : '正在读取本次 WorkWings Run…'}
              </>
            ) : studioKind === 'requirement' ? (
              <>
                <Sparkles className="size-4 mr-2" />
                {done && !isDemo && getActivePlatformRunId()
                  ? '用当前目标重新跑'
                  : '启动 WorkWings Agent 编排'}
              </>
            ) : (
              <>
                <Sparkles className="size-4 mr-2" />
                从本次 Run 刷新本页
              </>
            )}
          </Button>
          {getActivePlatformRunId() ? (
            <p className="text-[10px] font-mono text-muted-foreground truncate" title={getActivePlatformRunId() || ''}>
              本次 Run {getActivePlatformRunId()}
            </p>
          ) : studioKind !== 'requirement' ? (
            <p className="text-[11px] text-muted-foreground">
              还没有 WorkWings Agent Run。请先从需求分析启动 9 Agent 编排。
            </p>
          ) : null}
          {done && nextKind && (
            <Button
              variant="secondary"
              className="w-full pressable"
              onClick={goNext}
            >
              进入下一阶段：{STUDIO_META[nextKind].title}
              <ArrowRight className="size-4 ml-2" />
            </Button>
          )}
          {done && !nextKind && Boolean(getActivePlatformRunId()) && (
            <Button
              variant="secondary"
              className="w-full pressable"
              onClick={() => void handleRetryLastRun()}
            >
              <RotateCcw className="size-3.5 mr-2" />
              重试上次平台运行
            </Button>
          )}
          {canExportProject && (
            <div className="rounded-xl border border-emerald-200 bg-emerald-50/70 p-3 space-y-2">
              <div className="text-xs font-medium text-emerald-900">
                测试完成后可保存完整项目到本地
              </div>
              <p className="text-[11px] text-emerald-800/80 leading-relaxed">
                自动汇总需求 / 架构 / 代码 / 测试文档，并按目录创建源码结构（Chrome/Edge
                可选文件夹写入，其他浏览器下载 ZIP）。
              </p>
              <div className="flex flex-col gap-2">
                <Button
                  className="w-full pressable"
                  disabled={savingProject}
                  onClick={() => void handleSaveProject(false)}
                >
                  {savingProject ? (
                    <>
                      <Loader2 className="size-4 mr-2 animate-spin" />
                      正在保存…
                    </>
                  ) : (
                    <>
                      <FolderDown className="size-4 mr-2" />
                      一键保存项目到本地
                    </>
                  )}
                </Button>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    className="flex-1 pressable"
                    disabled={savingProject}
                    onClick={showExportPreview}
                  >
                    预览目录结构
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    className="flex-1 pressable"
                    disabled={savingProject}
                    onClick={() => void handleSaveProject(true)}
                  >
                    下载 ZIP
                  </Button>
                </div>
              </div>
            </div>
          )}
        </motion.div>

        <motion.div
          layout
          className="rounded-2xl border border-border bg-card p-5 shadow-sm min-h-[420px] flex flex-col"
        >
          <div className="flex items-center justify-between mb-3 gap-2">
            <div className="flex items-center gap-2 text-sm font-medium">
              {done ? (
                <CheckCircle2 className="size-4 text-emerald-500" />
              ) : (
                <Sparkles className="size-4 text-primary" />
              )}
              生成结果
            </div>
            <div className="flex gap-2">
              {studioKind === 'code' && output && (
                <Button
                  size="sm"
                  className="pressable"
                  onClick={openCodePreview}
                >
                  <MonitorPlay className="size-3.5 mr-1.5" />
                  运行预览
                </Button>
              )}
              <Button
                size="sm"
                variant="secondary"
                className="pressable"
                onClick={showDemo}
              >
                <PlayCircle className="size-3.5 mr-1.5" />
                演示
              </Button>
              {output && (
                <Button
                  size="sm"
                  variant="secondary"
                  className="pressable"
                  onClick={copyOutput}
                >
                  <Copy className="size-3.5 mr-1.5" />
                  复制
                </Button>
              )}
            </div>
          </div>

          {(generating || thinkingSteps.length > 0) && (
            <ThinkingProcess
              steps={thinkingSteps}
              done={thinkingDone}
              defaultOpen={generating || !done}
            />
          )}

          {deliverPaths.length > 0 && (
            <div className="mb-3 space-y-1.5">
              {deliverRoot ? (
                <div className="flex items-center justify-between gap-2 px-0.5">
                  <p className="text-[11px] text-muted-foreground truncate">
                    工作区：{deliverRoot}
                  </p>
                  <Button
                    size="sm"
                    variant="secondary"
                    className="h-6 px-2 text-[10px] pressable"
                    onClick={() => setShowExplorer(true)}
                  >
                    <FolderOpen className="size-3 mr-1" />
                    打开文件浏览器
                  </Button>
                </div>
              ) : null}
              <ProjectFileTree
                paths={deliverPaths}
                title="WorkWings 变更工程树"
                emptyText="暂无 changed_files"
                onOpenFile={async (path) => {
                  if (!deliverRoot) return
                  setShowExplorer(true)
                }}
              />
            </div>
          )}

          <div className="flex-1 overflow-y-auto rounded-xl border border-border/70 bg-muted/30 p-4">
            {output ? (
              <div className="prose prose-sm max-w-none prose-pre:bg-card prose-pre:border prose-pre:border-border">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{output}</ReactMarkdown>
              </div>
            ) : generating ? (
              <div className="h-full min-h-[200px] flex flex-col items-center justify-center text-center text-muted-foreground">
                <Loader2 className="size-7 mb-3 animate-spin text-primary" />
                <p className="text-sm">正在根据思考过程生成结果…</p>
              </div>
            ) : (
              <div className="h-full min-h-[280px] flex flex-col items-center justify-center text-center text-muted-foreground">
                <Sparkles className="size-8 mb-3 text-primary/70" />
                <p className="text-sm">输入目标后点击生成</p>
                <p className="text-xs mt-1">
                  生成时会展示思考过程；也可先点「效果演示查看」
                </p>
                <Button
                  size="sm"
                  variant="secondary"
                  className="mt-4 pressable"
                  onClick={showDemo}
                >
                  <PlayCircle className="size-3.5 mr-1.5" />
                  效果演示查看
                </Button>
              </div>
            )}
          </div>
        </motion.div>
      </div>

      <Dialog open={demoOpen} onOpenChange={setDemoOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="font-display">{meta.demoTitle}</DialogTitle>
            <DialogDescription>
              本地能力样例，与当前输入和本次 Run 无关。有真实产出时不要用它覆盖结果。
            </DialogDescription>
          </DialogHeader>
          <div className="flex-1 overflow-y-auto rounded-xl border border-border bg-muted/30 p-4 max-h-[50vh]">
            <div className="prose prose-sm max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{demoContent}</ReactMarkdown>
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setDemoOpen(false)}>
              关闭
            </Button>
            {done && !isDemo ? (
              <Button variant="outline" disabled>
                已有本次 Run 结果
              </Button>
            ) : (
              <Button className="pressable" onClick={applyDemoToResult}>
                载入到结果区（样例）
              </Button>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {studioKind === 'code' && (
        <CodePreviewDialog
          open={previewOpen}
          onOpenChange={setPreviewOpen}
          markdown={output}
        />
      )}

      <Dialog open={exportOpen} onOpenChange={setExportOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="font-display">项目目录结构</DialogTitle>
            <DialogDescription>{exportTitle || '导出预览'}</DialogDescription>
          </DialogHeader>
          <pre className="max-h-[50vh] overflow-auto rounded-xl border border-border bg-muted/40 p-3 text-[11px] leading-relaxed font-mono whitespace-pre">
            {exportTree || '暂无文件'}
          </pre>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setExportOpen(false)}>
              关闭
            </Button>
            {!exportTitle.includes('已') && (
              <Button
                className="pressable"
                disabled={savingProject}
                onClick={() => void handleSaveProject(false)}
              >
                <FolderDown className="size-3.5 mr-1.5" />
                确认保存
              </Button>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {showExplorer && deliverRoot && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="h-[80vh] w-full max-w-5xl">
            <ProjectExplorer
              projectRoot={deliverRoot}
              onClose={() => setShowExplorer(false)}
            />
          </div>
        </div>
      )}

      <RunMonitor
        runId={getActivePlatformRunId()}
        open={showMonitor}
        onOpenChange={setShowMonitor}
      />

      {showVersions && deliverRoot && (
        <VersionPanel
          projectRoot={deliverRoot}
          onClose={() => setShowVersions(false)}
        />
      )}
    </div>
  )
}
