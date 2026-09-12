import type { IProject } from '@/data/projects'
import type { IResult } from '@/data/results'
import {
  NODE_META,
  DEFAULT_KERNEL_MODELS,
  type IWorkflowNode,
  type NodeStatus,
  type NodeType,
} from '@/lib/workflow-types'
import type {
  JsonValue,
  WorkWingsArtifact,
  WorkWingsArtifactContent,
  WorkWingsNodeExecution,
  WorkWingsProject,
  WorkWingsProjectListItem,
  WorkWingsRun,
  WorkWingsRunStatus,
  WorkWingsStreamEvent,
} from './types'

type TimelineRole = 'user' | 'agent' | 'tool' | 'approval' | 'artifact' | 'system' | 'error'

export const WORKWINGS_NODE_ORDER = [
  'start',
  'multimodal_analysis',
  'project_analysis',
  'human_confirmation',
  'requirement_baseline',
  'requirement_approval',
  'prototype_generation',
  'prototype_approval',
  'architecture',
  'architecture_approval',
  'development',
  'implementation_apply',
  'test',
  'security',
  'security_exception_approval',
  'delivery',
  'deployment_approval',
  'deployment_verification',
  'end',
] as const

export const WORKWINGS_AGENT_ORDER = [
  'multimodal_analysis',
  'project_analysis',
  'requirement_baseline',
  'prototype_generation',
  'architecture',
  'development',
  'testing',
  'security',
  'delivery',
] as const

export type WorkWingsAgentType = (typeof WORKWINGS_AGENT_ORDER)[number]

export const WORKWINGS_AGENT_IDS: Record<WorkWingsAgentType, string> = {
  multimodal_analysis: 'multimodal_analysis_agent',
  project_analysis: 'project_analysis_agent',
  requirement_baseline: 'requirement_baseline_agent',
  prototype_generation: 'prototype_generation_agent',
  architecture: 'architecture_agent',
  development: 'development_agent',
  testing: 'testing_agent',
  security: 'security_agent',
  delivery: 'project_delivery_agent',
}

const WORKWINGS_NODE_AGENT: Record<string, WorkWingsAgentType> = {
  start: 'multimodal_analysis',
  multimodal_analysis: 'multimodal_analysis',
  project_analysis: 'project_analysis',
  human_confirmation: 'project_analysis',
  requirement_baseline: 'requirement_baseline',
  requirement_approval: 'requirement_baseline',
  prototype_generation: 'prototype_generation',
  prototype_approval: 'prototype_generation',
  architecture: 'architecture',
  architecture_approval: 'architecture',
  development: 'development',
  implementation_apply: 'development',
  test: 'testing',
  security: 'security',
  security_exception_approval: 'security',
  delivery: 'delivery',
  deployment_approval: 'delivery',
  deployment_verification: 'delivery',
  end: 'delivery',
}

export interface WorkWingsAgentGroup {
  type: WorkWingsAgentType
  agentId: string
  label: string
  stage: string
  description: string
  icon: string
  color: string
  nodes: IWorkflowNode[]
  primaryNodeId: string
}

export function workWingsAgentTypeForNode(
  nodeId?: string | null,
): WorkWingsAgentType | null {
  if (!nodeId) return null
  if (nodeId in WORKWINGS_NODE_AGENT) return WORKWINGS_NODE_AGENT[nodeId]
  return WORKWINGS_AGENT_ORDER.includes(nodeId as WorkWingsAgentType)
    ? (nodeId as WorkWingsAgentType)
    : null
}

export function workWingsAgentModel(
  type: WorkWingsAgentType,
  models?: Record<string, string> | null,
): string {
  return (
    models?.[WORKWINGS_AGENT_IDS[type]] ||
    models?.[type] ||
    DEFAULT_KERNEL_MODELS[type] ||
    '—'
  )
}

export function mapRunStatusToProjectStatus(
  status: WorkWingsRunStatus | string | null | undefined,
): IProject['status'] {
  if (status === 'succeeded' || status === 'archived') return 'completed'
  if (status === 'failed' || status === 'canceled') return 'failed'
  if (
    status === 'running' ||
    status === 'queued' ||
    status === 'ready' ||
    status === 'waiting_input' ||
    status === 'waiting_approval' ||
    status === 'waiting_tool' ||
    status === 'paused' ||
    status === 'retrying'
  ) {
    return 'running'
  }
  return 'draft'
}

export function isRunActive(status: WorkWingsRunStatus | string | null | undefined): boolean {
  return (
    status === 'running' ||
    status === 'queued' ||
    status === 'ready' ||
    status === 'waiting_input' ||
    status === 'waiting_tool' ||
    status === 'retrying'
  )
}

export function isRunWaitingApproval(
  status: WorkWingsRunStatus | string | null | undefined,
): boolean {
  return status === 'waiting_approval'
}

export function isRunTerminal(status: WorkWingsRunStatus | string | null | undefined): boolean {
  return (
    status === 'succeeded' ||
    status === 'failed' ||
    status === 'canceled' ||
    status === 'archived'
  )
}

export function workflowProgress(run: WorkWingsRun | null | undefined): number {
  if (!run) return 0
  if (run.status === 'succeeded' || run.status === 'archived') return 100
  if (run.status === 'failed' || run.status === 'canceled') return 100
  const index = run.current_node_id
    ? WORKWINGS_NODE_ORDER.indexOf(run.current_node_id as never)
    : -1
  if (index < 0) return run.status === 'created' ? 0 : 5
  return Math.round(
    ((index + (run.status === 'running' ? 0.5 : 0)) /
      (WORKWINGS_NODE_ORDER.length - 1)) *
      100,
  )
}

export function mapProject(
  item: WorkWingsProject | WorkWingsProjectListItem,
): IProject {
  const runs = 'workflow_runs' in item ? item.workflow_runs : []
  const latest = runs[0]
  const status = latest
    ? mapRunStatusToProjectStatus(latest.status)
    : item.status === 'archived'
      ? 'completed'
      : 'draft'
  const progress = latest
    ? workflowProgress({
        workflow_run_id: latest.workflow_run_id,
        project_id: item.project_id,
        template_id: latest.template_id,
        status: latest.status,
        current_node_id: latest.current_node_id,
        checkpoint_ref: latest.checkpoint_ref,
      })
    : 0
  return {
    id: item.project_id,
    name: item.name,
    description: item.description || '',
    goal: item.description || '',
    status,
    progress,
    createdAt:
      'created_at' in item
        ? item.created_at
        : item.latest_activity_at || new Date().toISOString(),
    kernelRunId: latest?.workflow_run_id || null,
    workwingsProjectId: item.project_id,
  }
}

const NODE_TYPE_BY_WORKWINGS: Record<string, NodeType> = {
  start: 'multimodal_analysis',
  multimodal_analysis: 'multimodal_analysis',
  project_analysis: 'project_analysis',
  human_confirmation: 'project_analysis',
  requirement_baseline: 'requirement_baseline',
  requirement_approval: 'requirement_baseline',
  prototype_generation: 'prototype_generation',
  prototype_approval: 'prototype_generation',
  architecture: 'architecture',
  architecture_approval: 'architecture',
  development: 'development',
  implementation_apply: 'development',
  test: 'testing',
  security: 'security',
  security_exception_approval: 'security',
  delivery: 'delivery',
  deployment_approval: 'delivery',
  deployment_verification: 'delivery',
  end: 'delivery',
}

const NODE_LABEL_BY_WORKWINGS: Record<string, string> = {
  start: '开始',
  multimodal_analysis: '多模态分析',
  project_analysis: '项目分析',
  human_confirmation: '人工确认',
  requirement_baseline: '需求基线',
  requirement_approval: '需求审批',
  prototype_generation: '原型生成',
  prototype_approval: '原型审批',
  architecture: '架构设计',
  architecture_approval: '架构审批',
  development: '开发变更',
  implementation_apply: '变更应用',
  test: '测试验证',
  security: '安全审查',
  security_exception_approval: '安全例外审批',
  delivery: '交付打包',
  deployment_approval: '部署审批',
  deployment_verification: '部署校验',
  end: '结束',
}

const NODE_DESCRIPTION_BY_WORKWINGS: Record<string, string> = {
  start: '创建运行上下文，锁定输入、权限和工作目录边界。',
  multimodal_analysis: '解析文字、图片与上传材料，生成结构化事实和约束。',
  project_analysis: '识别项目类型、目标范围、风险和后续需求草稿。',
  human_confirmation: '暂停等待人工确认项目解析结果，确认后继续。',
  requirement_baseline: '生成需求基线、验收标准和原型规格。',
  requirement_approval: '暂停等待需求基线审批，防止未确认需求进入开发。',
  prototype_generation: '基于需求生成可审查的页面原型与交互说明。',
  prototype_approval: '暂停等待原型审批，确认界面方向后继续。',
  architecture: '生成架构、接口、部署拓扑和工程实现边界。',
  architecture_approval: '暂停等待架构审批，确认技术方案和依赖。',
  development: '生成前后端变更、迁移和工程实现产物。',
  implementation_apply: '在审批后将受控变更应用到项目工作目录。',
  test: '运行真实测试与冒烟检查，记录通过和失败证据。',
  security: '审查安全风险、密钥泄露、越权写入和上线阻断项。',
  security_exception_approval: '高风险例外需要人工审批，不自动放行。',
  delivery: '归档交付包、测试报告、变更摘要和验收说明。',
  deployment_approval: '上线前人工审批，默认不执行生产部署。',
  deployment_verification: '验证部署结果、健康检查和回滚可用性。',
  end: '结束运行，持久化事件、产物、审计和检查点。',
}

export function groupWorkWingsNodes(nodes: IWorkflowNode[]): WorkWingsAgentGroup[] {
  return WORKWINGS_AGENT_ORDER.map((type) => {
    const meta = NODE_META[type]
    const groupNodes = WORKWINGS_NODE_ORDER
      .filter((nodeId) => WORKWINGS_NODE_AGENT[nodeId] === type)
      .map((nodeId) => nodes.find((node) => node.id === nodeId))
      .filter((node): node is IWorkflowNode => Boolean(node))
    return {
      type,
      agentId: WORKWINGS_AGENT_IDS[type],
      label: meta.label,
      stage: meta.stage,
      description: meta.description,
      icon: meta.icon,
      color: meta.color,
      nodes: groupNodes,
      primaryNodeId: groupNodes[0]?.id || type,
    }
  })
}

function mapNodeStatus(status: string): NodeStatus {
  const value = status.toLowerCase()
  if (
    value === 'succeeded' ||
    value === 'completed' ||
    value === 'success'
  ) {
    return 'completed'
  }
  if (
    value === 'failed' ||
    value === 'canceled' ||
    value === 'cancelled'
  ) {
    return 'failed'
  }
  if (
    value === 'running' ||
    value.startsWith('waiting') ||
    value === 'retrying'
  ) {
    return 'running'
  }
  return 'waiting'
}

export function mapNodeExecutions(
  nodes: WorkWingsNodeExecution[],
  existing: IWorkflowNode[],
): IWorkflowNode[] {
  if (nodes.length === 0) return existing
  const byId = new Map(nodes.map((node) => [node.node_id, node]))
  return existing.map((node) => {
    const execution = byId.get(node.id) || byId.get(node.agentId)
    if (!execution) return node
    return {
      ...node,
      label: NODE_LABEL_BY_WORKWINGS[execution.node_id] || node.label,
      status: mapNodeStatus(execution.status),
    }
  })
}

export function mapRunToNodes(
  run: WorkWingsRun,
  existing: IWorkflowNode[],
): IWorkflowNode[] {
  const currentOrder = run.current_node_id
    ? WORKWINGS_NODE_ORDER.indexOf(run.current_node_id as never)
    : -1
  return existing.map((node) => {
    const order = WORKWINGS_NODE_ORDER.indexOf(node.id as never)
    let status: NodeStatus = 'waiting'
    if (run.status === 'succeeded' || run.status === 'archived') {
      status = 'completed'
    } else if (run.status === 'failed' || run.status === 'canceled') {
      status =
        order >= 0 && order < currentOrder
          ? 'completed'
          : node.id === run.current_node_id
            ? 'failed'
            : 'waiting'
    } else if (order >= 0 && currentOrder >= 0) {
      status =
        order < currentOrder
          ? 'completed'
          : order === currentOrder
            ? 'running'
            : 'waiting'
    }
    return { ...node, status }
  })
}

export function buildWorkWingsWorkflow(): {
  nodes: IWorkflowNode[]
  edges: { id: string; source: string; target: string }[]
} {
  const nodes = WORKWINGS_NODE_ORDER.map((nodeId, index): IWorkflowNode => {
    const type = NODE_TYPE_BY_WORKWINGS[nodeId] || 'planner'
    const meta = NODE_META[type]
    return {
      id: nodeId,
      agentId: nodeId,
      type,
      label: NODE_LABEL_BY_WORKWINGS[nodeId] || meta.label,
      icon: meta.icon,
      position: {
        x: 56 + (index % 5) * 210,
        y: 72 + Math.floor(index / 5) * 150,
      },
      config: {
        model: 'Auto',
        prompt: NODE_DESCRIPTION_BY_WORKWINGS[nodeId] || `WorkWings node: ${nodeId}`,
        inputSource: 'WorkWings 持久化产物',
        outputTarget: 'WorkWings 平台存储',
      },
      status: 'waiting',
    }
  })
  const edges = WORKWINGS_NODE_ORDER.slice(1).map((target, index) => ({
    id: `edge-${WORKWINGS_NODE_ORDER[index]}-${target}`,
    source: WORKWINGS_NODE_ORDER[index],
    target,
  }))
  return { nodes, edges }
}

function jsonToMarkdown(value: JsonValue | Record<string, JsonValue>): string {
  if (typeof value === 'string') return value
  return `\`\`\`json\n${JSON.stringify(value, null, 2)}\n\`\`\``
}

function findPayloadText(
  value: JsonValue | Record<string, JsonValue> | undefined,
  keys: string[],
  depth = 0,
): string | undefined {
  if (!value || depth > 4) return undefined
  if (typeof value !== 'object' || Array.isArray(value)) return undefined
  for (const [rawKey, rawValue] of Object.entries(value)) {
    const key = rawKey.toLowerCase()
    if (keys.includes(key) && typeof rawValue === 'string' && rawValue.trim()) {
      return rawValue.trim()
    }
  }
  for (const rawValue of Object.values(value)) {
    const nested = findPayloadText(rawValue, keys, depth + 1)
    if (nested) return nested
  }
  return undefined
}

function previewPayload(payload: Record<string, JsonValue>): string | undefined {
  const entries = Object.entries(payload).filter(([, value]) => value != null)
  if (entries.length === 0) return undefined
  const safe = Object.fromEntries(entries.slice(0, 8))
  return JSON.stringify(safe, null, 2)
}

function artifactResultType(type: string): IResult['type'] {
  const normalized = type.toLowerCase()
  if (normalized.includes('requirement')) return 'requirement'
  if (normalized.includes('prototype') || normalized.includes('frontend')) {
    return 'architecture'
  }
  if (normalized.includes('architecture')) return 'architecture'
  if (
    normalized.includes('backend') ||
    normalized.includes('code') ||
    normalized.includes('migration') ||
    normalized.includes('pullrequest')
  ) {
    return 'code'
  }
  if (normalized.includes('test') || normalized.includes('security')) return 'test'
  if (
    normalized.includes('delivery') ||
    normalized.includes('deployment') ||
    normalized.includes('release')
  ) {
    return 'deployment'
  }
  return 'document'
}

export function artifactToResult(
  projectId: string,
  artifact: WorkWingsArtifact,
  content?: WorkWingsArtifactContent | null,
): IResult {
  const resultType = artifactResultType(artifact.artifact_type)
  return {
    id: artifact.artifact_id,
    projectId,
    type: resultType,
    title: artifact.artifact_type,
    summary: `${artifact.node_id} · v${artifact.version} · ${artifact.validation_status}`,
    content: content
      ? jsonToMarkdown(content.content)
      : `Artifact persisted at ${artifact.storage_uri}`,
  }
}

export function eventToLog(event: WorkWingsStreamEvent) {
  const nodeName = event.node_id || event.role || 'workwings'
  const level =
    event.status === 'failed'
      ? 'error'
      : event.status === 'succeeded'
        ? 'success'
        : event.status.includes('wait')
          ? 'warn'
          : 'info'
  return {
    id: event.stream_event_id,
    timestamp: new Date(event.occurred_at).toLocaleTimeString('zh-CN', {
      hour12: false,
    }),
    nodeId: event.node_id || 'workwings',
    nodeName,
    level: level as 'info' | 'success' | 'warn' | 'error',
    message: event.content || event.title || event.event_type,
  }
}

export function eventToChatMessage(event: WorkWingsStreamEvent) {
  const eventType = event.event_type.toLowerCase()
  const role: TimelineRole =
    event.status === 'failed'
      ? 'error'
      : event.role === 'user'
        ? 'user'
        : eventType.includes('approval')
          ? 'approval'
          : eventType.includes('artifact')
            ? 'artifact'
            : event.tool_execution_id || eventType.startsWith('tool.')
              ? 'tool'
              : eventType.startsWith('agent.') ||
                  eventType.startsWith('turn.') ||
                  eventType.startsWith('plan.')
                ? 'agent'
                : 'system'
  const command = findPayloadText(event.payload, ['command', 'cmd', 'shell'])
  const toolName = findPayloadText(event.payload, ['tool_name', 'tool', 'name'])
  return {
    id: event.stream_event_id,
    role,
    agentId: event.node_id || undefined,
    title: event.title || event.event_type,
    content: event.content || event.title || event.event_type,
    timestamp: event.occurred_at,
    eventType: event.event_type,
    status: event.status,
    sequenceNo: event.sequence_no,
    toolExecutionId: event.tool_execution_id || undefined,
    command,
    toolName,
    payloadPreview: previewPayload(event.payload),
  }
}
