import { memo, useRef, useEffect, useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Play,
  Pause,
  Loader2,
  FileText,
  Code,
  Layout,
  TestTube,
  BookOpen,
  Rocket,
  ExternalLink,
  ShieldCheck,
  Check,
  X,
  RefreshCw,
  Terminal,
  MessageSquare,
  User,
  Bot,
  GitBranch,
  CheckCircle2,
  AlertTriangle,
  FileArchive,
  Send,
  CircleDot,
} from 'lucide-react';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import type { IResult } from '@/data/results';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { NODE_META, type IWorkflowNode, type NodeType } from '@/lib/workflow-types';
import { format } from 'date-fns';
import { labelErrorCategory } from '@/lib/run-labels';
import type { JsonValue, WorkWingsApprovalRequest } from '@/integrations/workwings/types';

interface ExecutionPanelProps {
  nodes: IWorkflowNode[]
  isRunning: boolean
  overallProgress: number
  logs: LogEntry[]
  onRun: () => void
  onStop: () => void
  activeTab: string
  onTabChange: (tab: string) => void
  chatMessages: ChatMessage[]
  onSendChat: (msg: string) => void
  projectId: string
  results: IResult[]
  kernelOnline?: boolean | null
  validating?: boolean
  kernelRunId?: string | null
  waitingUser?: boolean
  pendingApproval?: WorkWingsApprovalRequest | null
  onValidate?: () => void
  onApprove?: () => void
  onReject?: () => void
  errorCategory?: string | null
  runError?: string | null
  onOpenRuns?: () => void
  /** 用已有 Run 重排智能产物，不新开工作流 */
  onRefreshArtifacts?: () => void
}

export interface LogEntry {
  id: string;
  timestamp: string;
  nodeId: string;
  nodeName: string;
  level: 'info' | 'success' | 'warn' | 'error';
  message: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'agent' | 'tool' | 'approval' | 'artifact' | 'system' | 'error';
  agentId?: string;
  title?: string;
  content: string;
  timestamp: string;
  eventType?: string;
  status?: string;
  sequenceNo?: number;
  toolExecutionId?: string;
  command?: string;
  toolName?: string;
  payloadPreview?: string;
}

const resultTypeIcon = {
  requirement: FileText,
  architecture: Layout,
  code: Code,
  test: TestTube,
  document: BookOpen,
  deployment: Rocket,
} as const;

const resultTypeLabel = {
  requirement: '需求文档',
  architecture: '任务规划',
  code: '代码文件',
  test: '测试报告',
  document: '项目文档',
  deployment: '审查交付',
} as const;

type ResultType = keyof typeof resultTypeLabel;

const timelineMeta = {
  user: {
    label: '用户',
    Icon: User,
    dot: 'bg-sky-500',
    panel: 'border-sky-500/20 bg-sky-500/[0.06]',
    title: 'text-sky-700 dark:text-sky-300',
  },
  agent: {
    label: 'Agent',
    Icon: Bot,
    dot: 'bg-emerald-500',
    panel: 'border-border/70 bg-background/65',
    title: 'text-emerald-700 dark:text-emerald-300',
  },
  tool: {
    label: '命令',
    Icon: Terminal,
    dot: 'bg-amber-500',
    panel: 'border-amber-500/20 bg-amber-500/[0.06]',
    title: 'text-amber-700 dark:text-amber-300',
  },
  approval: {
    label: '审批',
    Icon: CheckCircle2,
    dot: 'bg-violet-500',
    panel: 'border-violet-500/20 bg-violet-500/[0.06]',
    title: 'text-violet-700 dark:text-violet-300',
  },
  artifact: {
    label: '产物',
    Icon: FileArchive,
    dot: 'bg-cyan-500',
    panel: 'border-cyan-500/20 bg-cyan-500/[0.06]',
    title: 'text-cyan-700 dark:text-cyan-300',
  },
  system: {
    label: '系统',
    Icon: GitBranch,
    dot: 'bg-muted-foreground',
    panel: 'border-border/60 bg-muted/20',
    title: 'text-muted-foreground',
  },
  error: {
    label: '错误',
    Icon: AlertTriangle,
    dot: 'bg-red-500',
    panel: 'border-red-500/25 bg-red-500/[0.08]',
    title: 'text-red-700 dark:text-red-300',
  },
} as const;

function formatTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return format(date, 'HH:mm:ss');
}

function formatApprovalContext(context?: Record<string, JsonValue>): string | null {
  if (!context || Object.keys(context).length === 0) return null;
  return JSON.stringify(context, null, 2);
}

const ExecutionPanel = memo(function ExecutionPanel({
  nodes,
  isRunning,
  overallProgress,
  logs,
  onRun,
  onStop,
  activeTab,
  onTabChange,
  chatMessages,
  onSendChat,
  results,
  kernelOnline = null,
  validating = false,
  kernelRunId = null,
  waitingUser = false,
  pendingApproval = null,
  onValidate,
  onApprove,
  onReject,
  errorCategory = null,
  runError = null,
  onOpenRuns,
  onRefreshArtifacts,
}: ExecutionPanelProps) {
  const logContainerRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const [chatInput, setChatInput] = useState('');
  const [selectedFile, setSelectedFile] = useState(0);
  const [selectedResultType, setSelectedResultType] =
    useState<ResultType>('requirement');

  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs]);

  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [chatMessages]);

  useEffect(() => {
    const preferred: ResultType[] = [
      'requirement',
      'architecture',
      'code',
      'test',
      'deployment',
      'document',
    ];
    const first = preferred.find((t) => results.some((r) => r.type === t));
    if (first) setSelectedResultType(first);
  }, [results]);

  const handleSendChat = () => {
    if (!chatInput.trim()) return;
    onSendChat(chatInput);
    setChatInput('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendChat();
    }
  };

  const logLevelColor: Record<string, string> = {
    info: 'text-muted-foreground',
    success: 'text-emerald-400',
    warn: 'text-amber-400',
    error: 'text-red-400',
  };

  const resultTypes = (Object.keys(resultTypeLabel) as ResultType[]).filter(
    (type) => type !== 'document' || results.some((r) => r.type === 'document'),
  );
  const codeResult = results.find((r) => r.type === 'code');
  const hasCodeTree = Boolean(codeResult?.fileTree?.length);
  const panelTab =
    activeTab === 'results' || activeTab === 'chat' ? activeTab : 'logs';
  const nodeStats = useMemo(
    () => ({
      completed: nodes.filter((node) => node.status === 'completed').length,
      running: nodes.filter((node) => node.status === 'running').length,
      failed: nodes.filter((node) => node.status === 'failed').length,
      total: nodes.length,
    }),
    [nodes],
  );
  const nodeById = useMemo(() => {
    const byId = new Map<string, IWorkflowNode>();
    nodes.forEach((node) => {
      byId.set(node.id, node);
      byId.set(node.agentId, node);
    });
    return byId;
  }, [nodes]);
  const approvalContext = formatApprovalContext(pendingApproval?.context);

  return (
    <div className="pixel-execution-panel h-full flex flex-col border-t border-border/50 bg-card/40 backdrop-blur-sm">
      <div className="pixel-execution-toolbar flex items-center justify-between gap-3 px-4 py-2.5 border-b border-border/50">
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <Button
            size="sm"
            onClick={isRunning ? onStop : onRun}
            disabled={waitingUser || validating || (!isRunning && kernelOnline === false)}
            className={isRunning ? 'bg-red-500 hover:bg-red-600 text-white' : ''}
          >
            {isRunning ? (
              <>
                <Pause className="size-4 mr-1.5" />
                停止
              </>
            ) : (
              <>
                <Play className="size-4 mr-1.5" />
                运行全流程
              </>
            )}
          </Button>
          {onRefreshArtifacts && kernelRunId ? (
            <Button
              size="sm"
              variant="outline"
              disabled={isRunning || validating}
              onClick={onRefreshArtifacts}
              title="从已有 Run 重排智能产物，不调用 LLM"
            >
              <RefreshCw className="size-3.5 mr-1.5" />
              刷新产物
            </Button>
          ) : null}
          {onValidate ? (
            <Button
              size="sm"
              variant="secondary"
              disabled={isRunning || validating}
              onClick={onValidate}
            >
              {validating ? (
                <Loader2 className="size-3.5 mr-1.5 animate-spin" />
              ) : (
                <ShieldCheck className="size-3.5 mr-1.5" />
              )}
              校验后端
            </Button>
          ) : null}
          {waitingUser ? (
            <div className="flex items-center gap-1.5">
              <Button size="sm" onClick={onApprove} className="h-8">
                <Check className="size-3.5 mr-1" />
                通过
              </Button>
              <Button size="sm" variant="secondary" onClick={onReject} className="h-8">
                <X className="size-3.5 mr-1" />
                驳回
              </Button>
            </div>
          ) : null}
          <div className="flex items-center gap-2 w-36 shrink-0">
            <Progress value={overallProgress} className="h-1.5" />
            <span className="text-xs tabular-nums text-muted-foreground shrink-0 w-9">
              {Math.round(overallProgress)}%
            </span>
          </div>
          <Badge variant="outline" className="hidden lg:inline-flex text-[10px] shrink-0">
            {nodeStats.completed}/{nodeStats.total} 完成
            {nodeStats.running > 0 ? ` · ${nodeStats.running} 执行中` : ''}
            {nodeStats.failed > 0 ? ` · ${nodeStats.failed} 失败` : ''}
          </Badge>
          {kernelOnline != null ? (
            <Badge
              variant="outline"
              className={`text-[10px] shrink-0 ${
                kernelOnline
                  ? 'border-emerald-500/30 text-emerald-600'
                  : 'border-amber-500/30 text-amber-700'
              }`}
            >
              {kernelOnline ? 'WorkWings 在线' : 'WorkWings 离线'}
            </Badge>
          ) : null}
          {waitingUser ? (
            <Badge variant="outline" className="text-[10px] border-amber-500/40 text-amber-700 shrink-0">
              待审批
            </Badge>
          ) : null}
          {errorCategory ? (
            <Badge variant="outline" className="text-[10px] border-red-500/40 text-red-400 shrink-0">
              {labelErrorCategory(errorCategory)}
            </Badge>
          ) : null}
          {onOpenRuns && kernelRunId ? (
            <Button
              size="sm"
              variant="ghost"
              className="h-7 px-2 text-[11px] shrink-0"
              onClick={onOpenRuns}
              title={runError || kernelRunId}
            >
              <ExternalLink className="size-3.5 mr-1" />
              运行记录
            </Button>
          ) : null}
        </div>

        <Tabs value={panelTab} onValueChange={onTabChange} className="h-auto shrink-0">
          <TabsList className="h-8">
            <TabsTrigger value="logs" className="h-7 text-xs px-2.5">
              执行日志
            </TabsTrigger>
            <TabsTrigger value="results" className="h-7 text-xs px-2.5">
              智能产物
            </TabsTrigger>
            <TabsTrigger value="chat" className="h-7 text-xs px-2.5">
              协作对话
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      <div className="flex-1 overflow-hidden">
        <AnimatePresence mode="wait">
          {panelTab === 'logs' && (
            <motion.div
              key="logs"
              initial={{ opacity: 0, y: 5 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -5 }}
              transition={{ duration: 0.15 }}
              className="h-full flex flex-col"
            >
              <div
                ref={logContainerRef}
                className="flex-1 overflow-y-auto p-3 font-mono text-xs space-y-1"
              >
                {logs.length === 0 ? (
                  <div className="h-full flex items-center justify-center text-muted-foreground/60">
                    运行工作流后，Agent 执行日志将实时输出
                  </div>
                ) : (
                  logs.map((log) => (
                    <div key={log.id} className="flex gap-2 leading-relaxed">
                      <span className="text-muted-foreground/60 shrink-0">
                        {log.timestamp}
                      </span>
                      <span
                        className={`shrink-0 font-semibold ${
                          log.level === 'error'
                            ? 'text-red-400'
                            : log.level === 'success'
                              ? 'text-emerald-400'
                              : 'text-primary/90'
                        }`}
                      >
                        [{log.nodeName}]
                      </span>
                      <span className={logLevelColor[log.level]}>{log.message}</span>
                    </div>
                  ))
                )}
              </div>
            </motion.div>
          )}

          {panelTab === 'results' && (
            <motion.div
              key="results"
              initial={{ opacity: 0, y: 5 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -5 }}
              transition={{ duration: 0.15 }}
              className="h-full flex"
            >
              <div className="w-44 border-r border-border/50 p-2 space-y-1 overflow-y-auto">
                {resultTypes.map((type) => {
                  const Icon = resultTypeIcon[type];
                  const count = results.filter((r) => r.type === type).length;
                  return (
                    <button
                      key={type}
                      onClick={() => setSelectedResultType(type)}
                      className={`w-full text-left px-2.5 py-2 rounded-lg text-xs flex items-center gap-2 transition-colors ${
                        selectedResultType === type
                          ? 'bg-accent text-foreground'
                          : 'text-muted-foreground hover:bg-accent/50 hover:text-foreground'
                      }`}
                    >
                      <Icon className="size-3.5 shrink-0" />
                      <span className="flex-1 truncate">{resultTypeLabel[type]}</span>
                      {count > 0 && (
                        <Badge
                          variant="outline"
                          className="h-4 text-[10px] px-1 font-normal"
                        >
                          {count}
                        </Badge>
                      )}
                    </button>
                  );
                })}
              </div>

              <div className="flex-1 flex flex-col overflow-hidden">
                {selectedResultType === 'code' ? (
                  <div className="flex-1 flex overflow-hidden">
                    {hasCodeTree ? (
                      <div className="w-40 border-r border-border/50 p-2 space-y-0.5 overflow-y-auto text-xs font-mono">
                        {codeResult?.fileTree?.map((item) => (
                          <div key={item.name}>
                            <div className="px-2 py-1 text-muted-foreground">
                              📁 {item.name}
                            </div>
                            {item.children?.map((child, idx) => (
                              <div
                                key={child.name}
                                onClick={() => setSelectedFile(idx)}
                                className={`pl-6 py-1 cursor-pointer rounded hover:bg-accent/50 ${
                                  selectedFile === idx ? 'bg-accent/70' : ''
                                }`}
                              >
                                📄 {child.name}
                              </div>
                            ))}
                          </div>
                        ))}
                      </div>
                    ) : null}
                    <div className="flex-1 overflow-auto p-4 font-mono text-xs bg-background/50">
                      {codeResult?.content ? (
                        <div className="prose prose-sm max-w-none font-sans">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {codeResult.content}
                          </ReactMarkdown>
                        </div>
                      ) : (
                        <pre className="text-muted-foreground whitespace-pre-wrap leading-relaxed">
                          暂无代码产物。点「刷新产物」可从已有 Run 重排；或先「运行全流程」。
                        </pre>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="flex-1 overflow-y-auto p-4">
                    {results
                      .filter((r) => r.type === selectedResultType)
                      .map((result) => (
                        <article key={result.id} className="space-y-4">
                          <div>
                            <h3 className="text-base font-display font-semibold mb-1">
                              {result.title}
                            </h3>
                            <p className="text-sm text-muted-foreground">
                              {result.summary}
                            </p>
                            {result.stats && (
                              <div className="flex gap-3 mt-3">
                                <Badge variant="outline">
                                  总计 {result.stats.total}
                                </Badge>
                                <Badge className="bg-emerald-500/20 text-emerald-300 border-emerald-500/30">
                                  通过 {result.stats.passed}
                                </Badge>
                                <Badge className="bg-red-500/20 text-red-300 border-red-500/30">
                                  失败 {result.stats.failed}
                                </Badge>
                              </div>
                            )}
                            {result.deployMeta && (
                              <div className="mt-3 flex flex-wrap gap-2 items-center">
                                <Badge variant="outline">
                                  v{result.deployMeta.version}
                                </Badge>
                                <Badge className="bg-sky-500/15 text-sky-300 border-sky-500/30">
                                  {result.deployMeta.env}
                                </Badge>
                                <Badge className="bg-emerald-500/15 text-emerald-300 border-emerald-500/30">
                                  {result.deployMeta.health}
                                </Badge>
                                <a
                                  href={result.deployMeta.url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                                >
                                  打开环境
                                  <ExternalLink className="size-3" />
                                </a>
                              </div>
                            )}
                          </div>
                          <div className="prose prose-sm max-w-none prose-pre:bg-slate-50 prose-pre:border prose-pre:border-border/60">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {result.content}
                            </ReactMarkdown>
                          </div>
                        </article>
                      ))}
                    {results.filter((r) => r.type === selectedResultType).length ===
                      0 && (
                      <div className="h-full flex items-center justify-center text-muted-foreground/60 text-sm px-6 text-center leading-relaxed">
                        {selectedResultType === 'architecture' ? (
                          <>
                            暂无任务规划。跑完「运行全流程」后，这里会显示 Planner
                            的任务表与依赖（不是系统架构图）。
                          </>
                        ) : selectedResultType === 'document' ? (
                          <>暂无单独项目文档 Tab；说明一般在「审查交付」里。</>
                        ) : (
                          <>
                            暂无{resultTypeLabel[selectedResultType]}。请先点「运行全流程」，产物来自本次
                            WorkWings 工作流，不是单独点某个 Tab。
                          </>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </motion.div>
          )}

          {panelTab === 'chat' && (
            <motion.div
              key="chat"
              initial={{ opacity: 0, y: 5 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -5 }}
              transition={{ duration: 0.15 }}
              className="h-full flex flex-col"
            >
              <div
                ref={chatContainerRef}
                className="flex-1 overflow-y-auto px-4 py-3"
              >
                {chatMessages.length === 0 && !waitingUser ? (
                  <div className="h-full flex flex-col items-center justify-center text-center text-muted-foreground/60">
                    <MessageSquare className="size-8 mb-2 text-primary/70" />
                    <p className="text-sm">启动后展示 WorkWings 实时事件流</p>
                    <p className="text-xs mt-1 max-w-md leading-relaxed">
                      这里会输出模型消息、节点计划、工具命令、审批暂停、产物写入和异常状态。
                    </p>
                  </div>
                ) : null}
                <div className="mx-auto max-w-4xl space-y-3">
                  {chatMessages.map((msg) => {
                    const node = msg.agentId ? nodeById.get(msg.agentId) : null;
                    const typeMeta =
                      node && node.type in NODE_META ? NODE_META[node.type as NodeType] : null;
                    const tone = timelineMeta[msg.role];
                    const Icon = tone.Icon;
                    return (
                      <article key={msg.id} className="grid grid-cols-[82px_18px_minmax(0,1fr)] gap-2">
                        <div className="pt-2 text-right text-[10px] font-mono tabular-nums text-muted-foreground">
                          {formatTime(msg.timestamp)}
                          {typeof msg.sequenceNo === 'number' ? (
                            <div className="mt-0.5 text-[9px] opacity-60">
                              #{msg.sequenceNo}
                            </div>
                          ) : null}
                        </div>
                        <div className="relative flex justify-center">
                          <span className={`mt-2 size-2.5 rounded-full ${tone.dot}`} />
                          <span className="absolute top-5 bottom-[-14px] w-px bg-border/60" />
                        </div>
                        <div className={`rounded-lg border px-3 py-2.5 shadow-sm ${tone.panel}`}>
                          <div className="flex items-center justify-between gap-3">
                            <div className="flex min-w-0 items-center gap-2">
                              <Icon className={`size-3.5 shrink-0 ${tone.title}`} />
                              <span className={`truncate text-xs font-semibold ${tone.title}`}>
                                {typeMeta?.label || node?.label || msg.title || tone.label}
                              </span>
                              <Badge variant="outline" className="h-5 shrink-0 px-1.5 text-[10px] font-normal">
                                {msg.eventType || tone.label}
                              </Badge>
                            </div>
                            {msg.status ? (
                              <span className="shrink-0 text-[10px] font-mono text-muted-foreground">
                                {msg.status}
                              </span>
                            ) : null}
                          </div>
                          {msg.command ? (
                            <pre className="mt-2 overflow-x-auto rounded-md border border-border/60 bg-background/80 px-2.5 py-2 text-[11px] leading-relaxed text-foreground">
                              <code>{msg.command}</code>
                            </pre>
                          ) : null}
                          <div className="prose prose-sm mt-2 max-w-none text-sm leading-relaxed prose-pre:bg-background/80 prose-pre:border prose-pre:border-border/60">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {msg.content}
                            </ReactMarkdown>
                          </div>
                          {msg.toolName || msg.toolExecutionId ? (
                            <div className="mt-2 flex flex-wrap gap-1.5 text-[10px] text-muted-foreground">
                              {msg.toolName ? <Badge variant="outline">tool: {msg.toolName}</Badge> : null}
                              {msg.toolExecutionId ? (
                                <Badge variant="outline" className="font-mono">
                                  {msg.toolExecutionId}
                                </Badge>
                              ) : null}
                            </div>
                          ) : null}
                          {!msg.command && msg.payloadPreview && msg.role === 'tool' ? (
                            <details className="mt-2 text-xs text-muted-foreground">
                              <summary className="cursor-pointer select-none">查看工具载荷</summary>
                              <pre className="mt-2 max-h-36 overflow-auto rounded-md bg-background/70 p-2 text-[10px] leading-relaxed">
                                {msg.payloadPreview}
                              </pre>
                            </details>
                          ) : null}
                        </div>
                      </article>
                    );
                  })}

                  {waitingUser ? (
                    <article className="grid grid-cols-[82px_18px_minmax(0,1fr)] gap-2">
                      <div className="pt-2 text-right text-[10px] font-mono text-muted-foreground">
                        pause
                      </div>
                      <div className="relative flex justify-center">
                        <span className="mt-2 size-2.5 rounded-full bg-violet-500" />
                      </div>
                      <div className="rounded-lg border border-violet-500/30 bg-violet-500/[0.08] px-3 py-3 shadow-sm">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="flex items-center gap-2 text-sm font-semibold text-violet-700 dark:text-violet-300">
                              <CheckCircle2 className="size-4" />
                              等待人工审批
                            </div>
                            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                              {pendingApproval?.reason ||
                                'WorkWings 已暂停在人工确认节点，通过后会从检查点继续执行。'}
                            </p>
                          </div>
                          <Badge variant="outline" className="shrink-0 text-[10px]">
                            {pendingApproval?.approval_type || 'approval'}
                          </Badge>
                        </div>
                        {approvalContext ? (
                          <details className="mt-2 text-xs text-muted-foreground">
                            <summary className="cursor-pointer select-none">查看审批上下文</summary>
                            <pre className="mt-2 max-h-32 overflow-auto rounded-md bg-background/70 p-2 text-[10px] leading-relaxed">
                              {approvalContext}
                            </pre>
                          </details>
                        ) : null}
                        <div className="mt-3 flex items-center gap-2">
                          <Button size="sm" onClick={onApprove} className="h-8">
                            <Check className="size-3.5 mr-1" />
                            通过并继续
                          </Button>
                          <Button size="sm" variant="secondary" onClick={onReject} className="h-8">
                            <X className="size-3.5 mr-1" />
                            驳回
                          </Button>
                        </div>
                      </div>
                    </article>
                  ) : null}
                </div>
                {isRunning && (
                  <div className="mx-auto mt-3 max-w-4xl rounded-lg border border-border/60 bg-background/55 px-3 py-2">
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <CircleDot className="size-3 text-emerald-500" />
                      <span>流式连接已建立</span>
                      <span className="text-muted-foreground/50">·</span>
                      <span className="flex items-center gap-1.5">
                        <Loader2 className="size-3 animate-spin" />
                        WorkWings 正在执行节点与工具
                      </span>
                    </div>
                  </div>
                )}
              </div>
              <div className="p-3 border-t border-border/50">
                <div className="flex gap-2">
                  <input
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="向本次 WorkWings Run 发送反馈..."
                    className="flex-1 h-9 px-3 text-sm bg-background border border-border rounded-md focus:outline-none focus:ring-2 focus:ring-primary/50"
                  />
                  <Button size="sm" onClick={handleSendChat}>
                    <Send className="size-3.5 mr-1.5" />
                    发送
                  </Button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
});

export default ExecutionPanel;
