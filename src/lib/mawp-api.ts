/** 智流 MAWP Platform API 客户端（对接 backend FastAPI） */

/** 经 Vite 代理 /api/mawp → 后端 /api */
const BASE = '/api/mawp'

export interface MawpHealth {
  status: string
  service?: string
  workspace?: string
  llm?: {
    provider: string
    model: string
    has_api_key: boolean
  }
  agent_models?: Record<string, string>
}

export interface MawpRun {
  run_id: string
  workflow_id: string
  status: string
  current_node_id?: string | null
  params?: Record<string, unknown>
  node_outputs?: Record<string, Record<string, unknown>>
  failed_node_id?: string | null
  error?: string | null
  created_at?: string
  updated_at?: string
  checkpoint?: Record<string, unknown> | null
  heal?: {
    enabled?: boolean
    round?: number
    max_rounds?: number
    last_reason?: string | null
    last_from?: string | null
    last_to?: string | null
    selected_model?: string | null
    model_strategy?: string | null
    error_category?: string | null
  } | null
  observe?: RunObserve
}

export interface RunObserveNode {
  node_id: string
  status?: string
  duration_ms?: number | null
  retries?: number
  total_tokens?: number
  cost_cny?: number | null
  model?: string
}

export interface RunObserveUsageAgent {
  agent: string
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  cost_cny: number
  calls: number
  models?: string[]
}

export interface RunObserveUsage {
  prompt_tokens?: number
  completion_tokens?: number
  total_tokens?: number
  cost_cny?: number
  by_agent?: RunObserveUsageAgent[]
}

export interface RunObserve {
  duration_ms?: number | null
  nodes?: RunObserveNode[]
  heal_attempts?: number
  heal_handoffs?: number
  node_retries?: number
  error_category?: string | null
  heal_reason?: string | null
  waiting_user?: boolean
  failed?: boolean
  event_count?: number
  usage?: RunObserveUsage
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail =
      typeof data?.detail === 'string'
        ? data.detail
        : data?.detail
          ? JSON.stringify(data.detail)
          : res.statusText
    throw new Error(detail || `请求失败 ${res.status}`)
  }
  return data as T
}

export async function fetchMawpHealth(): Promise<MawpHealth> {
  return request<MawpHealth>('/health')
}

export async function fetchPlatformInfo() {
  return request<{
    workspace: string
    example_workflows: Array<{ id: string; path: string }>
    agent_models: Record<string, string>
    default_llm_model: string
  }>('/platform/info')
}

export async function listPlatformRuns(limit = 40) {
  return request<{ runs: MawpRun[] }>(`/platform/runs?limit=${limit}`)
}

export async function getPlatformRun(runId: string) {
  return request<{ run: MawpRun; events: unknown[]; observe?: RunObserve }>(
    `/platform/runs/${encodeURIComponent(runId)}`,
  )
}

export async function validateWorkflow(input: {
  path?: string
  yaml_text?: string
}) {
  return request<{
    ok: boolean
    workflow_id?: string
    errors: string[]
  }>('/platform/workflows/validate', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export async function runWorkflow(
  path: string,
  params: Record<string, unknown> = {},
  asyncMode = false,
) {
  return request<{ run: MawpRun }>('/platform/workflows/run', {
    method: 'POST',
    body: JSON.stringify({ path, params, async_mode: asyncMode }),
  })
}

export async function startStudioDeliver(
  goal: string,
  options?: {
    pass_on_attempt?: number
    review_status?: string
    async_mode?: boolean
    project_mode?: boolean
    project_root?: string
    project_title?: string
    frontend_dir?: string
    srs_excerpt?: string
    phase_id?: string
    create_workspace?: boolean
  },
) {
  return request<{
    run: MawpRun
    stages: Record<string, unknown>
    workflow: string
    project_mode?: boolean
    project_root?: string | null
    frontend_dir?: string
  }>('/platform/studio/deliver', {
    method: 'POST',
    body: JSON.stringify({
      goal,
      pass_on_attempt: options?.pass_on_attempt ?? 1,
      review_status: options?.review_status ?? 'pass',
      async_mode: options?.async_mode ?? true,
      project_mode: options?.project_mode ?? false,
      project_root: options?.project_root,
      project_title: options?.project_title,
      frontend_dir: options?.frontend_dir,
      srs_excerpt: options?.srs_excerpt,
      phase_id: options?.phase_id,
      create_workspace: options?.create_workspace ?? true,
    }),
  })
}

export async function fetchStudioStages(runId: string) {
  return request<{
    run: MawpRun
    stages: Record<string, unknown>
    stage_node_map: Record<string, string>
  }>(`/platform/studio/runs/${encodeURIComponent(runId)}/stages`)
}

export async function resumeRun(
  runId: string,
  action: 'approve' | 'reject' | 'input' = 'approve',
  data?: Record<string, unknown>,
) {
  return request<{ run: MawpRun; stages?: Record<string, unknown> }>(
    `/platform/runs/${encodeURIComponent(runId)}/resume`,
    {
      method: 'POST',
      body: JSON.stringify({ action, data }),
    },
  )
}

/** 探测后端是否在线（失败返回 null，不抛错） */
export async function probeMawp(): Promise<MawpHealth | null> {
  try {
    const health = await fetchMawpHealth()
    return health?.status === 'ok' ? health : null
  } catch {
    return null
  }
}

/** 重试失败的工作流运行 */
export async function retryRun(runId: string) {
  return request<{ run: MawpRun; stages?: Record<string, unknown> }>(
    `/platform/runs/${encodeURIComponent(runId)}/retry`,
    { method: 'POST', body: JSON.stringify({}) },
  )
}

/** 获取可用模型和当前配置 */
export async function listModels() {
  return request<{
    available_models: { id: string; label: string; tier: string }[]
    current: Record<string, string>
    default_llm_model: string
  }>(`/platform/models`)
}

// —— 版本管理 ——

export interface VersionSnapshot {
  snapshot_id: string
  path: string
  label: string
  created_at: string | null
  file_count: number
  run_id: string | null
}

export async function listVersionSnapshots(projectRoot: string) {
  return request<{ ok: boolean; snapshots: VersionSnapshot[] }>(
    `/platform/studio/project/versions?project_root=${encodeURIComponent(projectRoot)}`,
  )
}

export async function createVersionSnapshot(
  projectRoot: string,
  label?: string,
  note?: string,
  runId?: string,
) {
  const params = new URLSearchParams({ project_root: projectRoot })
  if (label) params.set('label', label)
  if (note) params.set('note', note)
  if (runId) params.set('run_id', runId)
  return request<{ ok: boolean; snapshot_id: string; copied_count: number }>(
    `/platform/studio/project/versions/create?${params.toString()}`,
    { method: 'POST' },
  )
}

export async function diffVersionSnapshot(
  projectRoot: string,
  snapshotId: string,
  path?: string,
) {
  const params = new URLSearchParams({ project_root: projectRoot })
  if (path) params.set('path', path)
  return request<{
    ok: boolean
    snapshot_id: string
    added: string[]
    removed: string[]
    changed: string[]
    diff?: string
    has_diff?: boolean
    summary: { added: number; removed: number; changed: number }
  }>(`/platform/studio/project/versions/${encodeURIComponent(snapshotId)}/diff?${params.toString()}`)
}

export async function restoreVersionSnapshot(
  projectRoot: string,
  snapshotId: string,
) {
  return request<{ ok: boolean; snapshot_id: string; restored_files: string[]; restored_count: number }>(
    `/platform/studio/project/versions/${encodeURIComponent(snapshotId)}/restore?project_root=${encodeURIComponent(projectRoot)}`,
    { method: 'POST' },
  )
}

/** 更新各 Agent 的模型配置 */
export async function updateModels(models: Record<string, string>) {
  return request<{
    ok: boolean
    current: Record<string, string>
  }>(`/platform/models`, {
    method: 'POST',
    body: JSON.stringify({ models }),
  })
}

/** 列出项目版本快照 */
export async function listProjectVersions(projectRoot: string) {
  return request<{
    project_root: string
    versions: Array<{
      snapshot_id: string
      label?: string
      created_at?: string
      file_count?: number
      run_id?: string
      status?: string
      note?: string
    }>
    count: number
  }>(`/platform/studio/project/versions?project_root=${encodeURIComponent(projectRoot)}`)
}

/** 获取版本详情 */
export async function getProjectVersionDetail(projectRoot: string, version: string) {
  return request<{
    project_root: string
    version: string
    manifest: Record<string, unknown>
    files: string[]
  }>(`/platform/studio/project/versions/${encodeURIComponent(version)}?project_root=${encodeURIComponent(projectRoot)}`)
}

/** 回滚到指定版本 */
export async function rollbackProjectVersion(projectRoot: string, version: string) {
  return request<{
    project_root: string
    ok: boolean
    restored_count: number
    rolled_back?: boolean
  }>(`/platform/studio/project/versions/${encodeURIComponent(version)}/rollback?project_root=${encodeURIComponent(projectRoot)}`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

/** 对比两个版本 */
export async function diffProjectVersions(projectRoot: string, versionA: string, versionB: string) {
  return request<{
    project_root: string
    version_a: string
    version_b: string
    added: string[]
    removed: string[]
    changed: string[]
    summary: { added: number; removed: number; changed: number }
  }>(`/platform/studio/project/versions/diff?project_root=${encodeURIComponent(projectRoot)}&version_a=${encodeURIComponent(versionA)}&version_b=${encodeURIComponent(versionB)}`)
}

/** SSE 实时事件流 */
export interface SSEEvent {
  type: string
  run_id?: string
  node_id?: string
  node_type?: string
  status?: string
  agent?: string
  error?: string
  attempt?: number
  max_retries?: number
  next?: string
  duration_ms?: number
  ts?: string
  current_node_id?: string | null
  completed_nodes?: number
  total_nodes?: number
  node_outputs_keys?: string[]
  failed_node_id?: string | null
  final?: boolean
  reason?: string
  from?: string
  to?: string
    selected_model?: string
    model_strategy?: string
    error_category?: string
}

export function streamRunEvents(
  runId: string,
  onEvent: (event: SSEEvent) => void,
  onStatus: (status: SSEEvent) => void,
  onDone: (finalStatus: string) => void,
  onError: (error: string) => void,
): () => void {
  const url = `${BASE}/platform/studio/runs/${encodeURIComponent(runId)}/stream`
  const es = new EventSource(url)

  es.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data) as SSEEvent
      onEvent(data)
    } catch {
      // ignore parse error
    }
  }

  es.addEventListener('status', (ev) => {
    try {
      const data = JSON.parse((ev as MessageEvent).data) as SSEEvent
      onStatus(data)
    } catch {
      // ignore
    }
  })

  es.addEventListener('done', (ev) => {
    try {
      const data = JSON.parse((ev as MessageEvent).data) as SSEEvent
      onDone(data.status || 'DONE')
    } catch {
      onDone('DONE')
    }
    es.close()
  })

  es.addEventListener('error', (ev) => {
    try {
      const data = JSON.parse((ev as MessageEvent).data) as SSEEvent
      onError(data.error || 'stream error')
    } catch {
      // EventSource 会自动重连，但如果已 done 则忽略
    }
  })

  es.onerror = () => {
    // 连接错误时关闭，不自动重连（避免无限重连）
    if (es.readyState === EventSource.CLOSED) {
      return
    }
    es.close()
  }

  return () => es.close()
}

// —— 版本管理 ——

/** 获取项目工作区文件树 */
export async function listProjectFiles(projectRoot: string, maxFiles = 500) {
  return request<{
    project_root: string
    workspace: string
    paths: string[]
    truncated: boolean
  }>(`/platform/studio/project/tree?project_root=${encodeURIComponent(projectRoot)}&max_files=${maxFiles}`)
}

/** 读取项目工作区内的文件 */
export async function readProjectFile(projectRoot: string, path: string, maxChars = 120000) {
  return request<{
    project_root: string
    path: string
    content: string
    truncated: boolean
    size: number
  }>(`/platform/studio/project/file?project_root=${encodeURIComponent(projectRoot)}&path=${encodeURIComponent(path)}&max_chars=${maxChars}`)
}

/** 下载项目工作区为 ZIP */
export async function downloadProjectZip(projectRoot: string): Promise<Blob> {
  const res = await fetch(`${BASE}/platform/studio/project/zip?project_root=${encodeURIComponent(projectRoot)}`)
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    const detail = typeof data?.detail === 'string' ? data.detail : res.statusText
    throw new Error(detail || `下载失败 ${res.status}`)
  }
  return res.blob()
}

/** 保存文件到项目工作区（在线编辑回写） */
export async function saveProjectFile(
  projectRoot: string,
  path: string,
  content: string,
) {
  return request<{
    project_root: string
    path: string
    saved: boolean
    created: boolean
    old_size: number
    new_size: number
  }>('/platform/studio/project/save', {
    method: 'POST',
    body: JSON.stringify({ project_root: projectRoot, path, content }),
  })
}

/** 获取文件内容（用于 diff 比较） */
export async function getProjectFileForDiff(projectRoot: string, path: string) {
  return request<{
    project_root: string
    path: string
    exists: boolean
    content: string
    size: number
  }>(`/platform/studio/project/diff?project_root=${encodeURIComponent(projectRoot)}&path=${encodeURIComponent(path)}`)
}

/** 比较文件 diff */
export async function compareProjectFileDiff(
  projectRoot: string,
  path: string,
  oldContent: string,
) {
  return request<{
    project_root: string
    path: string
    has_diff: boolean
    diff: string
    old_size: number
    new_size: number
  }>(
    `/platform/studio/project/diff-compare?project_root=${encodeURIComponent(projectRoot)}&path=${encodeURIComponent(path)}&old_content=${encodeURIComponent(oldContent)}`,
  )
}
