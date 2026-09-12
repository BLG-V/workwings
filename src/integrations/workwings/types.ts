export type JsonValue = string | number | boolean | null | JsonObject | JsonValue[]
export type JsonObject = { [key: string]: JsonValue }

export type WorkWingsProjectStatus = 'created' | 'active' | 'paused' | 'archived'
export type WorkWingsRunStatus =
  | 'created'
  | 'queued'
  | 'ready'
  | 'running'
  | 'waiting_input'
  | 'waiting_approval'
  | 'waiting_tool'
  | 'paused'
  | 'retrying'
  | 'failed'
  | 'canceled'
  | 'succeeded'
  | 'archived'

export interface WorkWingsProjectRun {
  workflow_run_id: string
  template_id: string
  status: WorkWingsRunStatus
  current_node_id: string | null
  checkpoint_ref: string | null
  created_by: string
  updated_at: string
  title: string | null
  is_pinned: boolean
  is_unread: boolean
  archived_at: string | null
}

export interface WorkWingsProjectListItem {
  project_id: string
  name: string
  description: string | null
  owner_id: string
  status: WorkWingsProjectStatus
  asset_count: number
  workflow_run_count: number
  agent_execution_count: number
  latest_activity_at: string | null
  source_folders: string[]
  workflow_runs: WorkWingsProjectRun[]
}

export interface WorkWingsProject {
  project_id: string
  name: string
  description: string | null
  owner_id: string
  status: WorkWingsProjectStatus
  created_at: string
  updated_at: string
  source_folders: string[]
}

export interface WorkWingsHealthDependency {
  name: string
  status: string
  details: Record<string, JsonValue>
}

export interface WorkWingsHealth {
  status: string
  service: string
  environment: string
  dependencies: WorkWingsHealthDependency[]
}

export interface WorkWingsRuntimeConfig {
  app_env: string
  deployment_defaults: {
    frontend_domain: string | null
    api_domain: string | null
    project_root: string | null
  }
  model_route_defaults: Array<{
    agent_name: string
    model_name: string
    provider: string | null
  }>
}

export interface WorkWingsRun {
  workflow_run_id: string
  project_id: string
  template_id: string
  status: WorkWingsRunStatus
  current_node_id: string | null
  checkpoint_ref: string | null
}

export interface WorkWingsStartRunRequest {
  created_by?: string
  input_payload?: Record<string, JsonValue>
  model_name?: string | null
}

export interface WorkWingsStreamEvent {
  stream_event_id: string
  workflow_run_id: string
  project_id: string | null
  sequence_no: number
  event_type: string
  role: string
  title: string
  content: string
  status: string
  payload: Record<string, JsonValue>
  node_id: string | null
  agent_execution_id: string | null
  tool_execution_id: string | null
  occurred_at: string
}

export interface WorkWingsNodeExecution {
  execution_id: string
  workflow_run_id: string
  node_id: string
  node_type: string
  status: string
  input_payload: Record<string, JsonValue>
  output_payload: Record<string, JsonValue>
  error_message: string | null
  retry_count: number
  started_at: string | null
  finished_at: string | null
  updated_at: string
}

export interface WorkWingsArtifact {
  artifact_id: string
  workflow_run_id: string
  node_id: string
  artifact_type: string
  schema_version: string
  source_artifact_ids: string[]
  storage_uri: string
  content_hash: string
  validation_status: string
  version: number
  created_by: string
  created_at: string
  updated_at: string
}

export interface WorkWingsArtifactContent {
  artifact_id: string
  artifact_type: string
  content: Record<string, JsonValue>
}

export interface WorkWingsArtifactDownload {
  artifact_id: string
  download_url: string
  expires_at: string | null
}

export interface WorkWingsApprovalRequest {
  approval_request_id: string
  workflow_run_id: string
  node_id: string
  requester_id: string
  approver_id: string | null
  status: 'pending' | 'approved' | 'rejected' | 'transferred' | 'canceled'
  reason: string | null
  context: Record<string, JsonValue>
  approval_type: string
  created_at: string
  updated_at: string
}

export interface WorkWingsApprovalRecord {
  approval_record_id: string
  approval_request_id: string
  workflow_run_id: string
  node_id: string
  approver_id: string
  action: string
  comment: string | null
  decided_at: string | null
  created_at: string
  updated_at: string
}

export interface WorkWingsApprovals {
  requests: WorkWingsApprovalRequest[]
  records: WorkWingsApprovalRecord[]
}

export interface WorkWingsWorkspaceFileChange {
  change_id: string
  relative_path: string
  operation: string
  rename_from: string | null
  base_sha256: string | null
  before_sha256: string | null
  after_sha256: string | null
  before_size: number | null
  after_size: number | null
  status: string
  failure_reason: string | null
}

export interface WorkWingsWorkspaceChangeSet {
  change_set_id: string
  workflow_run_id: string
  project_id: string
  approval_request_id: string | null
  root_path: string
  status: string
  manifest_path: string | null
  error_message: string | null
  files: WorkWingsWorkspaceFileChange[]
}

export interface WorkWingsApiError extends Error {
  status: number
  detail: string
}

export interface WorkWingsStreamHandlers {
  onEvent?: (event: WorkWingsStreamEvent) => void
  onError?: (error: Error) => void
  onClose?: () => void
}
