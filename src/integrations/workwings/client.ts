import { getWorkWingsActorId, getWorkWingsHeaders, WORKWINGS_BASE } from './auth'
import type {
  JsonValue,
  WorkWingsApiError,
  WorkWingsApprovals,
  WorkWingsApprovalRecord,
  WorkWingsArtifact,
  WorkWingsArtifactContent,
  WorkWingsArtifactDownload,
  WorkWingsHealth,
  WorkWingsNodeExecution,
  WorkWingsProject,
  WorkWingsProjectListItem,
  WorkWingsRun,
  WorkWingsRuntimeConfig,
  WorkWingsStartRunRequest,
  WorkWingsStreamEvent,
  WorkWingsWorkspaceChangeSet,
} from './types'

export interface WorkWingsProjectCreateInput {
  name: string
  description?: string | null
  owner_id?: string
  status?: 'created' | 'active' | 'paused' | 'archived'
  source_folders?: string[]
}

export interface WorkWingsProjectUpdateInput {
  name?: string
  description?: string | null
  status?: 'created' | 'active' | 'paused' | 'archived'
  source_folders?: string[]
}

export interface WorkWingsDecisionInput {
  approver_id?: string
  comment?: string | null
  input_payload?: Record<string, JsonValue>
}

function apiError(status: number, detail: string): WorkWingsApiError {
  const error = new Error(detail || `WorkWings request failed: ${status}`) as WorkWingsApiError
  error.status = status
  error.detail = detail
  return error
}

function stringifyDetail(data: unknown, fallback: string): string {
  if (data && typeof data === 'object' && 'detail' in data) {
    const detail = (data as { detail?: unknown }).detail
    if (typeof detail === 'string') return detail
    if (detail != null) return JSON.stringify(detail)
  }
  return fallback
}

export async function workwingsRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = getWorkWingsHeaders(init.headers)
  if (init.body != null && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const res = await fetch(`${WORKWINGS_BASE}${path}`, { ...init, headers })
  if (res.status === 204) return undefined as T

  const text = await res.text()
  let data: unknown = null
  if (text) {
    try {
      data = JSON.parse(text) as unknown
    } catch {
      data = text
    }
  }
  if (!res.ok) {
    throw apiError(res.status, stringifyDetail(data, res.statusText))
  }
  return data as T
}

export async function getHealth(): Promise<WorkWingsHealth> {
  return workwingsRequest<WorkWingsHealth>('/health')
}

export async function probeWorkWings(): Promise<WorkWingsHealth | null> {
  try {
    const health = await getHealth()
    return health?.status ? health : null
  } catch {
    return null
  }
}

export async function getRuntimeConfig(): Promise<WorkWingsRuntimeConfig> {
  return workwingsRequest<WorkWingsRuntimeConfig>('/runtime-config')
}

export async function listProjects(): Promise<WorkWingsProjectListItem[]> {
  return workwingsRequest<WorkWingsProjectListItem[]>('/projects')
}

export async function createProject(
  input: WorkWingsProjectCreateInput,
): Promise<WorkWingsProject> {
  return workwingsRequest<WorkWingsProject>('/projects', {
    method: 'POST',
    body: JSON.stringify({
      name: input.name,
      description: input.description ?? null,
      owner_id: input.owner_id || getWorkWingsActorId(),
      status: input.status || 'created',
      source_folders: input.source_folders || [],
    }),
  })
}

export async function getProject(projectId: string): Promise<WorkWingsProject> {
  return workwingsRequest<WorkWingsProject>(`/projects/${encodeURIComponent(projectId)}`)
}

export async function updateProject(
  projectId: string,
  input: WorkWingsProjectUpdateInput,
): Promise<WorkWingsProject> {
  return workwingsRequest<WorkWingsProject>(`/projects/${encodeURIComponent(projectId)}`, {
    method: 'PATCH',
    body: JSON.stringify(input),
  })
}

export async function deleteProject(projectId: string): Promise<void> {
  return workwingsRequest<void>(`/projects/${encodeURIComponent(projectId)}`, {
    method: 'DELETE',
  })
}

export async function startWorkflowRun(
  projectId: string,
  input: WorkWingsStartRunRequest = {},
): Promise<WorkWingsRun> {
  return workwingsRequest<WorkWingsRun>(
    `/projects/${encodeURIComponent(projectId)}/workflow-runs`,
    {
      method: 'POST',
      body: JSON.stringify({
        created_by: input.created_by || getWorkWingsActorId(),
        input_payload: input.input_payload || {},
        model_name: input.model_name ?? null,
      }),
    },
  )
}

export async function getWorkflowRun(runId: string): Promise<WorkWingsRun> {
  return workwingsRequest<WorkWingsRun>(`/workflow-runs/${encodeURIComponent(runId)}`)
}

export async function pauseWorkflowRun(
  runId: string,
  reason?: string,
): Promise<WorkWingsRun> {
  return workwingsRequest<WorkWingsRun>(`/workflow-runs/${encodeURIComponent(runId)}/pause`, {
    method: 'POST',
    body: JSON.stringify({ actor: getWorkWingsActorId(), reason: reason ?? null }),
  })
}

export async function resumeWorkflowRun(
  runId: string,
  inputPayload: Record<string, JsonValue> = {},
): Promise<WorkWingsRun> {
  return workwingsRequest<WorkWingsRun>(`/workflow-runs/${encodeURIComponent(runId)}/resume`, {
    method: 'POST',
    body: JSON.stringify({ actor: getWorkWingsActorId(), input_payload: inputPayload }),
  })
}

export async function cancelWorkflowRun(
  runId: string,
  reason?: string,
): Promise<WorkWingsRun> {
  return workwingsRequest<WorkWingsRun>(`/workflow-runs/${encodeURIComponent(runId)}/cancel`, {
    method: 'POST',
    body: JSON.stringify({ actor: getWorkWingsActorId(), reason: reason ?? null }),
  })
}

export async function listStreamEvents(
  runId: string,
  after = 0,
): Promise<WorkWingsStreamEvent[]> {
  const params = new URLSearchParams({ after: String(after) })
  return workwingsRequest<WorkWingsStreamEvent[]>(
    `/workflow-runs/${encodeURIComponent(runId)}/stream-events?${params.toString()}`,
  )
}

export async function createWorkflowFeedback(
  runId: string,
  message: string,
): Promise<WorkWingsStreamEvent> {
  return workwingsRequest<WorkWingsStreamEvent>(
    `/workflow-runs/${encodeURIComponent(runId)}/feedback`,
    {
      method: 'POST',
      body: JSON.stringify({ message }),
    },
  )
}

export async function listNodes(runId: string): Promise<WorkWingsNodeExecution[]> {
  return workwingsRequest<WorkWingsNodeExecution[]>(
    `/workflow-runs/${encodeURIComponent(runId)}/nodes`,
  )
}

export async function listArtifacts(runId: string): Promise<WorkWingsArtifact[]> {
  return workwingsRequest<WorkWingsArtifact[]>(
    `/workflow-runs/${encodeURIComponent(runId)}/artifacts`,
  )
}

export async function getArtifactContent(
  artifactId: string,
): Promise<WorkWingsArtifactContent> {
  return workwingsRequest<WorkWingsArtifactContent>(
    `/artifacts/${encodeURIComponent(artifactId)}/content`,
  )
}

export async function createArtifactDownload(
  artifactId: string,
): Promise<WorkWingsArtifactDownload> {
  return workwingsRequest<WorkWingsArtifactDownload>(
    `/artifacts/${encodeURIComponent(artifactId)}/download`,
    { method: 'POST' },
  )
}

export async function listApprovals(runId: string): Promise<WorkWingsApprovals> {
  return workwingsRequest<WorkWingsApprovals>(
    `/workflow-runs/${encodeURIComponent(runId)}/approvals`,
  )
}

function decisionBody(input: WorkWingsDecisionInput = {}) {
  return {
    approver_id: input.approver_id || getWorkWingsActorId(),
    comment: input.comment ?? null,
    input_payload: input.input_payload || {},
  }
}

export async function approveRequest(
  runId: string,
  approvalRequestId: string,
  input?: WorkWingsDecisionInput,
): Promise<WorkWingsApprovalRecord> {
  return workwingsRequest<WorkWingsApprovalRecord>(
    `/workflow-runs/${encodeURIComponent(runId)}/approvals/${encodeURIComponent(approvalRequestId)}/approve`,
    {
      method: 'POST',
      body: JSON.stringify(decisionBody(input)),
    },
  )
}

export async function rejectRequest(
  runId: string,
  approvalRequestId: string,
  input?: WorkWingsDecisionInput,
): Promise<WorkWingsApprovalRecord> {
  return workwingsRequest<WorkWingsApprovalRecord>(
    `/workflow-runs/${encodeURIComponent(runId)}/approvals/${encodeURIComponent(approvalRequestId)}/reject`,
    {
      method: 'POST',
      body: JSON.stringify(decisionBody(input)),
    },
  )
}

export async function listWorkspaceChanges(
  runId: string,
): Promise<WorkWingsWorkspaceChangeSet[]> {
  return workwingsRequest<WorkWingsWorkspaceChangeSet[]>(
    `/workflow-runs/${encodeURIComponent(runId)}/workspace-changes`,
  )
}
