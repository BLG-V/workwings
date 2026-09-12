import { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import {
  Save,
  Cloud,
  ChevronLeft,
  Sparkles,
  Wand2,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import type { IResult } from '@/data/results';
import {
  type IWorkflowNode,
  type IWorkflowEdge,
  type NodeType,
} from '@/lib/workflow-types';
import type { IProject } from '@/data/projects';
import {
  createProject,
  getProject,
  setLastProjectId,
  updateProject,
} from '@/lib/projects-store';
import { getWorkflow, saveWorkflow } from '@/lib/workflows-store';
import type { RunObserve } from '@/lib/mawp-api';
import {
  approveRequest,
  cancelWorkflowRun,
  createProject as createWorkWingsProject,
  getProject as getWorkWingsProject,
  getArtifactContent,
  getRuntimeConfig,
  getWorkflowRun,
  listApprovals,
  listArtifacts,
  listNodes,
  probeWorkWings,
  rejectRequest,
  startWorkflowRun,
} from '@/integrations/workwings/client';
import {
  artifactToResult,
  buildWorkWingsWorkflow,
  eventToChatMessage,
  eventToLog,
  groupWorkWingsNodes,
  isRunActive,
  isRunWaitingApproval,
  mapNodeExecutions,
  mapRunStatusToProjectStatus,
  mapRunToNodes,
  WORKWINGS_NODE_ORDER,
  workWingsAgentModel,
  workWingsAgentTypeForNode,
  workflowProgress,
} from '@/integrations/workwings/mappers';
import { streamWorkflowRun } from '@/integrations/workwings/sse';
import type {
  WorkWingsApprovalRequest,
  WorkWingsRun,
  WorkWingsStreamEvent,
} from '@/integrations/workwings/types';
import NodePalette from './sections/NodePalette';
import WorkflowCanvas from './sections/WorkflowCanvas';
import PropertyPanel from './sections/PropertyPanel';
import ExecutionPanel, { type LogEntry, type ChatMessage } from './sections/ExecutionPanel';

type WorkflowNavState = {
  selectAgent?: string
  goal?: string
  kernelRunId?: string
}

export default function WorkflowEditorPage() {
  const { projectId: routeProjectId = '' } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const navState = location.state as WorkflowNavState | null;
  const pendingSelectRef = useRef<string | null>(navState?.selectAgent ?? null);
  const pendingGoalRef = useRef<string | null>(navState?.goal?.trim() || null);
  const pendingRunIdRef = useRef<string | null>(navState?.kernelRunId ?? null);

  const [project, setProject] = useState<IProject | null>(null);
  const defaultWorkflow = useMemo(() => buildWorkWingsWorkflow(), []);
  const [nodes, setNodes] = useState<IWorkflowNode[]>(defaultWorkflow.nodes);
  const [edges, setEdges] = useState<IWorkflowEdge[]>(defaultWorkflow.edges);
  const [zoom, setZoom] = useState(0.85);
  const [pan, setPan] = useState({ x: 20, y: 20 });
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [isSaved, setIsSaved] = useState(true);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [executionTab, setExecutionTab] = useState('logs');
  const [bottomPanelOpen, setBottomPanelOpen] = useState(true);
  const [aiOpen, setAiOpen] = useState(false);
  const [requirementDraft, setRequirementDraft] = useState('');
  const [generatedResults, setGeneratedResults] = useState<IResult[]>([]);
  const [projectStatus, setProjectStatus] = useState<IProject['status']>('draft');
  const [projectProgress, setProjectProgress] = useState(0);
  const [kernelOnline, setKernelOnline] = useState<boolean | null>(null);
  const [validating, setValidating] = useState(false);
  const [waitingUser, setWaitingUser] = useState(false);
  const [kernelRunId, setKernelRunId] = useState<string | null>(null);
  const [agentModels, setAgentModels] = useState<Record<string, string>>({});
  const [kernelObserve] = useState<RunObserve | null>(null);
  const [kernelError, setKernelError] = useState<string | null>(null);
  const [focusNonce, setFocusNonce] = useState(0);
  const [pendingApproval, setPendingApproval] =
    useState<WorkWingsApprovalRequest | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const nodesRef = useRef(nodes);
  const logsRef = useRef(logs);
  const resultsRef = useRef(generatedResults);
  const runMetaRef = useRef<{ id: string; startedAt: number } | null>(null);
  const watchingRunRef = useRef<string | null>(null);
  const attachAndWatchRef = useRef<
    (runId: string, selectHint?: string | null) => Promise<void>
  >(async () => {});
  const workwingsProjectIdRef = useRef<string | null>(null);
  const lastStreamSequenceRef = useRef(0);
  nodesRef.current = nodes;
  logsRef.current = logs;
  resultsRef.current = generatedResults;

  useEffect(() => {
    let p = routeProjectId ? getProject(routeProjectId) : null;
    if (!p) {
      p = createProject({
        name: '未命名项目',
        description: '由工作流编辑器自动创建',
        goal: '',
      });
      navigate(`/workflow/${p.id}`, { replace: true });
    } else {
      setLastProjectId(p.id);
    }
    setProject(p);
    setProjectStatus(p.status);
    setProjectProgress(p.progress);
    const incomingGoal =
      pendingGoalRef.current ||
      (location.state as WorkflowNavState | null)?.goal?.trim() ||
      '';
    pendingGoalRef.current = null;
    if (incomingGoal) {
      setRequirementDraft(incomingGoal);
      updateProject(p.id, { goal: incomingGoal });
    } else {
      setRequirementDraft(p.goal || p.description || '');
    }
    const wf = getWorkflow(p.id);
    const fallback = buildWorkWingsWorkflow();
    const savedNodes = wf?.nodes ?? [];
    const savedIds = new Set(savedNodes.map((node) => node.id));
    const useSaved =
      savedNodes.length > 0 &&
      WORKWINGS_NODE_ORDER.every((nodeId) => savedIds.has(nodeId));
    setNodes(useSaved ? savedNodes : fallback.nodes);
    setEdges(useSaved && wf?.edges ? wf.edges : fallback.edges);
    setZoom(wf?.zoom ?? 0.85);
    setPan(wf?.pan ?? { x: 20, y: 20 });
    setGeneratedResults(wf?.results ?? []);
    setIsSaved(true);
    const savedLogs = Array.isArray(wf?.logs) ? (wf.logs as LogEntry[]) : [];
    setLogs(savedLogs);
    const pick =
      pendingSelectRef.current ||
      (location.state as WorkflowNavState | null)?.selectAgent ||
      null;
    const nextNodes = useSaved ? savedNodes : fallback.nodes;
    const node = pick
      ? nextNodes.find((n) => n.type === pick || n.id === pick)
      : undefined;
    setSelectedNodeId(
      workWingsAgentTypeForNode(pick) ??
        workWingsAgentTypeForNode(node?.id) ??
        null,
    );
    const incomingRun =
      pendingRunIdRef.current ||
      (location.state as WorkflowNavState | null)?.kernelRunId ||
      wf?.kernelRunId ||
      p.kernelRunId ||
      null;
    if (incomingRun) {
      pendingRunIdRef.current = incomingRun;
      setKernelRunId(incomingRun);
    } else {
      setKernelRunId(null);
    }
  }, [routeProjectId, navigate]);

  useEffect(() => {
    const st = location.state as WorkflowNavState | null;
    const pick = st?.selectAgent;
    const goal = st?.goal?.trim();
    const runId = st?.kernelRunId;
    if (!pick && !goal && !runId) return;
    if (pick) {
      pendingSelectRef.current = pick;
      const node = nodesRef.current.find((n) => n.type === pick || n.id === pick);
      setSelectedNodeId(
        workWingsAgentTypeForNode(pick) ??
          workWingsAgentTypeForNode(node?.id) ??
          null,
      );
    }
    if (goal) {
      pendingGoalRef.current = goal;
      setRequirementDraft(goal);
      if (routeProjectId) updateProject(routeProjectId, { goal });
    }
    if (runId) {
      pendingRunIdRef.current = runId;
      void attachAndWatchRef.current(runId, pick);
    }
    navigate(location.pathname, { replace: true, state: {} });
  }, [location.state, location.pathname, navigate, routeProjectId]);

  useEffect(() => {
    void (async () => {
      const health = await probeWorkWings();
      setKernelOnline(Boolean(health));
      if (!health) return;
      try {
        const runtime = await getRuntimeConfig();
        setAgentModels(
          Object.fromEntries(
            runtime.model_route_defaults.map((route) => [
              route.agent_name,
              route.model_name,
            ]),
          ),
        );
      } catch {
        /* Auto 模型展示会回退到本地默认选型 */
      }
    })();
  }, []);

  const projectId = project?.id ?? '';
  const projectName = project?.name ?? '未命名项目';
  const agentGroups = useMemo(() => groupWorkWingsNodes(nodes), [nodes]);
  const agentNodes = useMemo<IWorkflowNode[]>(() => {
    return agentGroups.map((group, index) => {
      const failed = group.nodes.some((item) => item.status === 'failed');
      const running = group.nodes.some((item) => item.status === 'running');
      const completed =
        group.nodes.length > 0 &&
        group.nodes.every((item) => item.status === 'completed');
      return {
        id: group.type,
        agentId: group.agentId,
        type: group.type,
        label: group.label,
        icon: group.icon,
        position: {
          x: 56 + (index % 3) * 300,
          y: 72 + Math.floor(index / 3) * 190,
        },
        config: {
          model: `Auto · ${workWingsAgentModel(group.type, agentModels)}`,
          prompt: group.description,
          inputSource: `${group.agentId} · 包含 ${group.nodes.length} 个 WorkWings 节点`,
          outputTarget: group.nodes.map((item) => item.label).join(' / '),
        },
        status: failed
          ? 'failed'
          : running
            ? 'running'
            : completed
              ? 'completed'
              : 'waiting',
      };
    });
  }, [agentGroups, agentModels]);
  const agentEdges = useMemo<IWorkflowEdge[]>(() => {
    return agentNodes.slice(1).map((target, index) => ({
      id: `agent-edge-${agentNodes[index].id}-${target.id}`,
      source: agentNodes[index].id,
      target: target.id,
    }));
  }, [agentNodes]);
  const selectedAgentGroup = useMemo(() => {
    const selectedType = workWingsAgentTypeForNode(selectedNodeId);
    return agentGroups.find((group) => group.type === selectedType) ?? null;
  }, [agentGroups, selectedNodeId]);

  const persistCanvas = useCallback(
    (patch?: { results?: IResult[]; runId?: string | null }) => {
      if (!projectId) return;
      const runId = patch?.runId;
      saveWorkflow({
        projectId,
        nodes: nodesRef.current,
        edges,
        zoom,
        pan,
        results: patch?.results ?? resultsRef.current,
        ...(runId !== undefined ? { kernelRunId: runId } : {}),
        logs: logsRef.current.slice(-200),
      });
      if (runId) {
        updateProject(projectId, { kernelRunId: runId });
      }
    },
    [projectId, edges, zoom, pan],
  );

  const loadArtifacts = useCallback(async (runId: string) => {
    try {
      const artifacts = await listArtifacts(runId);
      const results = await Promise.all(
        artifacts.map(async (artifact) => {
          try {
            const content = await getArtifactContent(artifact.artifact_id);
            return artifactToResult(projectId, artifact, content);
          } catch {
            return artifactToResult(projectId, artifact);
          }
        }),
      );
      setGeneratedResults(results);
      persistCanvas({ results, runId });
    } catch {
      /* Artifact 尚未持久化时保留当前面板状态 */
    }
  }, [persistCanvas, projectId]);

  const hydrateFromRun = useCallback(
    async (runId: string, selectHint?: string | null) => {
      try {
        const [run, executions, approvals] = await Promise.all([
          getWorkflowRun(runId),
          listNodes(runId),
          listApprovals(runId),
        ]);
        setKernelRunId(run.workflow_run_id);
        setWaitingUser(isRunWaitingApproval(run.status));
        setPendingApproval(
          approvals.requests.find((request) => request.status === 'pending') || null,
        );
        setIsRunning(isRunActive(run.status));
        setProjectStatus(mapRunStatusToProjectStatus(run.status));
        setProjectProgress(workflowProgress(run));
        const next = mapNodeExecutions(executions, mapRunToNodes(run, nodesRef.current));
        setNodes(next);
        const node = selectHint
          ? next.find((item) => item.id === selectHint || item.agentId === selectHint)
          : next.find((item) => item.id === run.current_node_id);
        setSelectedNodeId(
          workWingsAgentTypeForNode(selectHint) ??
            workWingsAgentTypeForNode(run.current_node_id) ??
            workWingsAgentTypeForNode(node?.id) ??
            null,
        );
        setFocusNonce((nonce) => nonce + 1);
        updateProject(projectId, {
          status: mapRunStatusToProjectStatus(run.status),
          progress: workflowProgress(run),
          kernelRunId: run.workflow_run_id,
          workwingsProjectId: run.project_id,
        });
        await loadArtifacts(run.workflow_run_id);
      } catch {
        toast.error('无法把 WorkWings Run 同步到画布');
      }
    },
    [loadArtifacts, projectId],
  );

  const refreshArtifacts = useCallback(async () => {
    const runId =
      kernelRunId ||
      getProject(projectId)?.kernelRunId ||
      getWorkflow(projectId)?.kernelRunId ||
      null;
    if (!runId) {
      toast.error('没有可刷新的 Run，请先完成一次全流程');
      return;
    }
    try {
      await loadArtifacts(runId);
      setExecutionTab('results');
      toast.success('已从 WorkWings 读取持久化产物');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '刷新产物失败');
    }
  }, [kernelRunId, loadArtifacts, projectId]);

  const overallProgress = useMemo(() => {
    if (nodes.length === 0) return 0;
    const completed = nodes.filter((n) => n.status === 'completed').length;
    const running = nodes.filter((n) => n.status === 'running').length;
    return Math.round(((completed + running * 0.5) / nodes.length) * 100);
  }, [nodes]);

  const openKernelRun = useCallback(() => {
    if (!kernelRunId) {
      navigate('/runs');
      return;
    }
    navigate(`/runs?run=${encodeURIComponent(kernelRunId)}`);
  }, [kernelRunId, navigate]);

  const handleSave = useCallback(() => {
    saveWorkflow({
      projectId,
      nodes,
      edges,
      zoom,
      pan,
      results: generatedResults,
      kernelRunId,
      logs: logs.slice(-200),
    });
    updateProject(projectId, {
      goal: requirementDraft,
      progress: overallProgress,
      status: projectStatus,
      kernelRunId,
    });
    setIsSaved(true);
    toast.success('工作流已保存到本机');
  }, [
    projectId,
    nodes,
    edges,
    zoom,
    pan,
    generatedResults,
    requirementDraft,
    overallProgress,
    projectStatus,
    kernelRunId,
    logs,
  ]);

  const markUnsaved = useCallback(() => setIsSaved(false), []);

  const handleNodesChange = useCallback(
    (next: IWorkflowNode[]) => {
      setNodes(next);
      markUnsaved();
    },
    [markUnsaved],
  );

  const handleEdgesChange = useCallback(
    (next: IWorkflowEdge[]) => {
      setEdges(next);
      markUnsaved();
    },
    [markUnsaved],
  );

  const handleAddNode = useCallback(
    (_type: NodeType, _position?: { x: number; y: number }) => {
      toast.info('画布为 WorkWings 工作流只读视图，不能增删节点');
    },
    [],
  );

  const handleDeleteNode = useCallback((_id: string) => {
    toast.info('画布为 WorkWings 工作流只读视图，不能删除节点');
  }, []);

  const handleGenerateFromRequirement = useCallback(() => {
    if (!requirementDraft.trim()) {
      toast.error('请先描述你的产品需求');
      return;
    }
    updateProject(projectId, { goal: requirementDraft.trim() });
    const wf = buildWorkWingsWorkflow();
    setNodes(wf.nodes.map((n) => ({ ...n, status: 'waiting' })));
    setEdges(wf.edges);
    setGeneratedResults([]);
    setLogs([]);
    setAiOpen(false);
    markUnsaved();
    toast.success('已写入目标。点「运行全流程」将交给 WorkWings 执行');
    setExecutionTab('logs');
  }, [requirementDraft, markUnsaved, projectId]);

  const handleValidate = useCallback(async () => {
    setValidating(true);
    try {
      const health = await probeWorkWings();
      setKernelOnline(Boolean(health));
      if (!health) {
        toast.error('WorkWings 后端离线，无法校验');
        return;
      }
      toast.success('WorkWings 后端在线，工作流状态机可用');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '校验失败');
    } finally {
      setValidating(false);
    }
  }, []);

  const ensureWorkWingsProject = useCallback(async (): Promise<string> => {
    if (workwingsProjectIdRef.current) return workwingsProjectIdRef.current
    if (!project) throw new Error('项目尚未加载')
    if (project.workwingsProjectId) {
      workwingsProjectIdRef.current = project.workwingsProjectId
      return project.workwingsProjectId
    }
    try {
      const existing = await getWorkWingsProject(project.id)
      workwingsProjectIdRef.current = existing.project_id
      updateProject(project.id, { workwingsProjectId: existing.project_id })
      return existing.project_id
    } catch {
      const created = await createWorkWingsProject({
        name: project.name,
        description: project.description || project.goal,
      })
      workwingsProjectIdRef.current = created.project_id
      updateProject(project.id, { workwingsProjectId: created.project_id })
      return created.project_id
    }
  }, [project])

  const consumeWorkflowEvent = useCallback((event: WorkWingsStreamEvent) => {
    lastStreamSequenceRef.current = Math.max(
      lastStreamSequenceRef.current,
      event.sequence_no,
    )
    setLogs((prev) => {
      if (prev.some((item) => item.id === event.stream_event_id)) return prev
      return [...prev, eventToLog(event)].slice(-300)
    })
    setChatMessages((prev) => {
      if (prev.some((item) => item.id === event.stream_event_id)) return prev
      return [...prev, eventToChatMessage(event)].slice(-300)
    })
    if (event.node_id) {
      setSelectedNodeId(workWingsAgentTypeForNode(event.node_id) ?? event.node_id)
    }
    const eventStatus = event.status as WorkWingsRun['status']
    if (isRunWaitingApproval(eventStatus)) {
      setWaitingUser(true)
      void listApprovals(event.workflow_run_id)
        .then((approvals) => {
          setPendingApproval(
            approvals.requests.find((request) => request.status === 'pending') || null,
          )
        })
        .catch(() => {
          /* hydrateFromRun 会在下一次同步时补齐审批对象 */
        })
    }
  }, [])

  const watchWorkWingsRun = useCallback(
    async (runId: string, after = 0) => {
      const ac = abortRef.current
      await streamWorkflowRun(runId, {
        after,
        signal: ac?.signal,
        onEvent: consumeWorkflowEvent,
        onError: (error) => {
          if (!ac?.signal.aborted) setKernelError(error.message)
        },
      })
      if (ac?.signal.aborted) return
      await hydrateFromRun(runId)
    },
    [consumeWorkflowEvent, hydrateFromRun],
  )

  const handleRun = useCallback(() => {
    const goal =
      requirementDraft.trim() ||
      project?.description?.trim() ||
      projectName ||
      '未命名交付目标'
    void (async () => {
      abortRef.current?.abort()
      const ac = new AbortController()
      abortRef.current = ac
      try {
        const online = Boolean(await probeWorkWings())
        setKernelOnline(online)
        if (!online) throw new Error('WorkWings 后端离线')
        const backendProjectId = await ensureWorkWingsProject()
        const run = await startWorkflowRun(backendProjectId, {
          input_payload: {
            user_text: goal,
            goal,
            source_folders: [],
            working_directory: null,
            permission_mode: 'workspace-write',
            execution_mode: 'standard',
          },
        })
        runMetaRef.current = { id: `workwings:${run.workflow_run_id}`, startedAt: Date.now() }
        setKernelRunId(run.workflow_run_id)
        setIsRunning(isRunActive(run.status))
        setWaitingUser(isRunWaitingApproval(run.status))
        setPendingApproval(null)
        setLogs([])
        setChatMessages([])
        setGeneratedResults([])
        setKernelError(null)
        setProjectStatus(mapRunStatusToProjectStatus(run.status))
        setProjectProgress(workflowProgress(run))
        setNodes((prev) => mapRunToNodes(run, prev))
        updateProject(projectId, {
          status: mapRunStatusToProjectStatus(run.status),
          progress: workflowProgress(run),
          kernelRunId: run.workflow_run_id,
          workwingsProjectId: backendProjectId,
        })
        toast.info('WorkWings 已接收任务，正在流式执行')
        await watchWorkWingsRun(run.workflow_run_id)
        runMetaRef.current = null
      } catch (error) {
        if (ac.signal.aborted) return
        setIsRunning(false)
        setKernelError(error instanceof Error ? error.message : 'WorkWings 执行失败')
        setProjectStatus('failed')
        updateProject(projectId, { status: 'failed' })
        toast.error(error instanceof Error ? error.message : 'WorkWings 执行失败')
      }
    })()
  }, [
    ensureWorkWingsProject,
    project,
    projectId,
    projectName,
    requirementDraft,
    watchWorkWingsRun,
  ])

  const handleStop = useCallback(() => {
    const runId = kernelRunId
    abortRef.current?.abort()
    abortRef.current = null
    if (!runId) {
      setIsRunning(false)
      return
    }
    void cancelWorkflowRun(runId, '用户在工作台停止运行')
      .then((run) => {
        setIsRunning(false)
        setWaitingUser(false)
        setPendingApproval(null)
        setProjectStatus(mapRunStatusToProjectStatus(run.status))
        setProjectProgress(workflowProgress(run))
        setNodes((prev) => mapRunToNodes(run, prev))
        updateProject(projectId, {
          status: mapRunStatusToProjectStatus(run.status),
          progress: workflowProgress(run),
        })
        toast.warning('WorkWings 运行已取消')
      })
      .catch((error) => {
        setKernelError(error instanceof Error ? error.message : '取消运行失败')
        toast.error(error instanceof Error ? error.message : '取消运行失败')
      })
  }, [kernelRunId, projectId])

  const attachAndWatch = useCallback(
    async (runId: string, selectHint?: string | null) => {
      if (!projectId || !runId) return
      abortRef.current?.abort()
      const ac = new AbortController()
      abortRef.current = ac
      watchingRunRef.current = runId
      try {
        await hydrateFromRun(runId, selectHint)
        const run = await getWorkflowRun(runId)
        if (isRunActive(run.status)) {
          setIsRunning(true)
          await streamWorkflowRun(runId, {
            after: lastStreamSequenceRef.current,
            signal: ac.signal,
            onEvent: consumeWorkflowEvent,
          })
        }
        if (!ac.signal.aborted) await hydrateFromRun(runId, selectHint)
      } catch (error) {
        if (!ac.signal.aborted) {
          setKernelError(error instanceof Error ? error.message : '连接 WorkWings 失败')
        }
      }
    },
    [consumeWorkflowEvent, hydrateFromRun, projectId],
  )
  attachAndWatchRef.current = attachAndWatch;

  useEffect(() => {
    if (!projectId) return;
    const runId =
      pendingRunIdRef.current ||
      getProject(projectId)?.kernelRunId ||
      getWorkflow(projectId)?.kernelRunId ||
      null;
    if (!runId) return;
    void attachAndWatch(runId, pendingSelectRef.current);
    // 只在进入该项目时接一次，避免草稿变更导致重连
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const handleApprove = useCallback(async () => {
    if (!kernelRunId || !pendingApproval) return
    try {
      setWaitingUser(false)
      setPendingApproval(null)
      await approveRequest(kernelRunId, pendingApproval.approval_request_id)
      toast.info('审批已记录，WorkWings 正在继续')
      await attachAndWatch(kernelRunId)
    } catch (error) {
      setWaitingUser(true)
      setPendingApproval(pendingApproval)
      toast.error(error instanceof Error ? error.message : '审批失败')
    }
  }, [attachAndWatch, kernelRunId, pendingApproval])

  const handleReject = useCallback(async () => {
    if (!kernelRunId || !pendingApproval) return
    try {
      await rejectRequest(kernelRunId, pendingApproval.approval_request_id)
      setWaitingUser(false)
      setPendingApproval(null)
      setIsRunning(false)
      setProjectStatus('failed')
      updateProject(projectId, { status: 'failed' })
      toast.warning('审批已驳回，运行结束')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '驳回失败')
    }
  }, [kernelRunId, pendingApproval, projectId])

  const handleSendChat = useCallback(
    (msg: string) => {
      if (!kernelRunId) {
        toast.info('请先启动一个 WorkWings 运行')
        return
      }
      void import('@/integrations/workwings/client')
        .then(({ createWorkflowFeedback }) => createWorkflowFeedback(kernelRunId, msg))
        .then((event) => consumeWorkflowEvent(event))
        .catch((error: unknown) => {
          toast.error(error instanceof Error ? error.message : '发送消息失败')
        })
    },
    [consumeWorkflowEvent, kernelRunId],
  );

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  if (!project) {
    return (
      <div className="flex h-[50vh] items-center justify-center text-sm text-muted-foreground">
        正在加载项目…
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-0px)] flex flex-col">
      <div className="pixel-workflow-header flex items-center justify-between px-4 h-14 border-b border-border/60 bg-card/40 backdrop-blur-md shrink-0">
        <div className="flex items-center gap-3 min-w-0">
          <Button
            size="icon"
            variant="ghost"
            onClick={() => navigate('/chat')}
            className="size-8 shrink-0"
            title="返回智能对话"
          >
            <ChevronLeft className="size-4" />
          </Button>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Sparkles className="size-4 text-primary shrink-0" />
              <span className="text-sm font-display font-semibold truncate">
                {project.name}
              </span>
              <Badge
                variant="outline"
                className={`text-xs ${
                  projectStatus === 'running'
                    ? 'border-sky-500/30 text-sky-300 bg-sky-500/10'
                    : projectStatus === 'completed'
                      ? 'border-emerald-500/30 text-emerald-300 bg-emerald-500/10'
                      : projectStatus === 'failed'
                        ? 'border-red-500/30 text-red-300 bg-red-500/10'
                        : ''
                }`}
              >
                {projectStatus === 'running' && '进行中'}
                {projectStatus === 'completed' && '已完成'}
                {projectStatus === 'draft' && '草稿'}
                {projectStatus === 'failed' && '失败'}
                {` · ${projectProgress}%`}
              </Badge>
            </div>
            <div className="text-[11px] text-muted-foreground truncate mt-0.5">
              WorkWings：9 Agent 编排 · 19 个真实执行节点 · 审批与产物按后端状态同步
              {isRunning || waitingUser
                ? ' · 切走其它模块后点「工作流编排」会自动接上'
                : ''}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Button size="sm" variant="secondary" onClick={() => setAiOpen(true)}>
            <Wand2 className="size-3.5 mr-1.5" />
            填写目标
          </Button>
          <div className="hidden md:flex items-center gap-1.5 text-xs text-muted-foreground mr-1">
            {isSaved ? (
              <>
                <Cloud className="size-3.5" />
                已保存
              </>
            ) : (
              <>
                <Save className="size-3.5" />
                未保存
              </>
            )}
          </div>
          <Button size="sm" variant="secondary" onClick={handleSave} disabled={isSaved}>
            <Save className="size-3.5 mr-1.5" />
            保存
          </Button>
        </div>
      </div>

      <div className="pixel-workflow-layout flex-1 flex overflow-hidden">
        <div className="pixel-agent-column w-52 shrink-0 border-r border-border/50 bg-card/20">
          <NodePalette
            models={agentModels}
            nodes={agentNodes}
            selectedNodeId={selectedNodeId}
            onSelectAgent={setSelectedNodeId}
          />
        </div>

        <div className="pixel-canvas-column flex-1 flex flex-col min-w-0">
          <div
            className={`relative flex-1 min-h-0 transition-all duration-300 ${
              bottomPanelOpen ? 'min-h-[58%]' : 'h-full'
            }`}
          >
            <WorkflowCanvas
              nodes={agentNodes}
              edges={agentEdges}
              zoom={zoom}
              pan={pan}
              selectedNodeId={selectedNodeId}
              onNodesChange={handleNodesChange}
              onEdgesChange={handleEdgesChange}
              onPanChange={setPan}
              onZoomChange={setZoom}
              onSelectNode={setSelectedNodeId}
              onDeleteNode={handleDeleteNode}
              onAddNode={handleAddNode}
              readOnly
              agentGroups={agentGroups}
              errorCategory={kernelObserve?.error_category}
              focusNonce={focusNonce}
            />
            <button
              onClick={() => setBottomPanelOpen((v) => !v)}
              className="absolute bottom-0 left-1/2 -translate-x-1/2 px-4 py-1 text-xs text-muted-foreground bg-card border border-t-0 border-border rounded-b-md hover:bg-accent transition-colors z-10"
            >
              {bottomPanelOpen ? '收起面板 ▼' : '展开面板 ▲'}
            </button>
          </div>

          {bottomPanelOpen && (
            <div className="h-[38%] shrink-0 min-h-[200px] max-h-[420px]">
              <ExecutionPanel
                nodes={nodes}
                isRunning={isRunning}
                overallProgress={overallProgress}
                logs={logs}
                onRun={handleRun}
                onStop={handleStop}
                activeTab={executionTab}
                onTabChange={setExecutionTab}
                chatMessages={chatMessages}
                onSendChat={handleSendChat}
                projectId={projectId}
                results={generatedResults}
                kernelOnline={kernelOnline}
                validating={validating}
                kernelRunId={kernelRunId}
                waitingUser={waitingUser}
                pendingApproval={pendingApproval}
                onValidate={() => void handleValidate()}
                onApprove={() => void handleApprove()}
                onReject={() => void handleReject()}
                errorCategory={kernelObserve?.error_category}
                runError={kernelError}
                onOpenRuns={openKernelRun}
                onRefreshArtifacts={() => void refreshArtifacts()}
              />
            </div>
          )}
        </div>

        <div className="pixel-property-column w-72 shrink-0 border-l border-border/50 bg-card/20">
          <PropertyPanel
            node={agentNodes.find((n) => n.id === selectedNodeId) ?? null}
            containedNodes={selectedAgentGroup?.nodes ?? []}
            observe={kernelObserve}
            runError={kernelError}
            onOpenRuns={kernelRunId ? openKernelRun : undefined}
          />
        </div>
      </div>

      <Dialog open={aiOpen} onOpenChange={setAiOpen}>
        <DialogContent className="sm:max-w-lg surface-panel">
          <DialogHeader>
            <DialogTitle className="font-display flex items-center gap-2">
              <Wand2 className="size-4 text-primary" />
              交付目标
            </DialogTitle>
            <DialogDescription>
              写入本次运行的 goal。点「运行全流程」会执行 WorkWings
              后端确定性工作流，画布仅展示真实状态与产物。
            </DialogDescription>
          </DialogHeader>
          <Textarea
            value={requirementDraft}
            onChange={(e) => setRequirementDraft(e.target.value)}
            rows={7}
            className="text-sm"
            placeholder="例如：做一个面向中小商家的电商后台，需要商品/订单/库存管理，支持权限与数据看板，两周内可上线演示环境..."
          />
          <DialogFooter>
            <Button variant="secondary" onClick={() => setAiOpen(false)}>
              取消
            </Button>
            <Button onClick={handleGenerateFromRequirement}>
              <Sparkles className="size-3.5 mr-1.5" />
              写入目标并载入 WorkWings
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
