/** 高级项目 API（分期交付） */

/** 经 Vite 代理 /api/mawp → 后端 /api */
const BASE = '/api/mawp'

export interface GapNextTask {
  capability_id?: string
  title: string
  reason?: string
  status?: string
  priority?: string
  suggested_phase?: string
}

export interface GapSummary {
  completed?: string[]
  partial?: string[]
  missing?: string[]
  next_tasks?: GapNextTask[]
  files?: string[]
}

export interface AdvancedPhase {
  id: string
  title: string
  goal: string
  deliverables?: string[]
  depends_on?: string[]
  status: string
  generated_files?: string[]
  generated_at?: string
  via?: string
  run_id?: string
  degraded?: boolean
  attempts?: number
  validation?: {
    placeholder?: boolean
    spec_gaps?: string[]
    gap?: GapSummary | null
  }
  testing?: {
    passed?: boolean
    log_summary?: string
    metric_command?: string
    failures?: string[]
  }
  task_runs?: Array<{
    task_id?: string
    title?: string
    success?: boolean
    changed_files?: string[]
    status?: string
  }>
}

export interface AdvancedProject {
  id: string
  title: string
  source_filename: string
  created_at: string
  updated_at: string
  workspace: string
  phases: AdvancedPhase[]
  srs_chars: number
  current_phase_id?: string | null
  status: string
  gap_summary?: GapSummary | null
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { ...init })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail =
      typeof data?.detail === 'string' ? data.detail : res.statusText
    throw new Error(detail || `请求失败 ${res.status}`)
  }
  return data as T
}

export async function listAdvancedProjects() {
  return request<{ projects: AdvancedProject[] }>('/platform/advanced/projects')
}

export async function getAdvancedProject(id: string) {
  return request<{ project: AdvancedProject }>(
    `/platform/advanced/projects/${encodeURIComponent(id)}`,
  )
}

export async function createAdvancedProject(input: {
  title?: string
  file?: File | null
  text?: string
}) {
  const form = new FormData()
  if (input.title) form.append('title', input.title)
  if (input.text) form.append('text', input.text)
  if (input.file) form.append('file', input.file)
  return request<{ project: AdvancedProject }>('/platform/advanced/projects', {
    method: 'POST',
    body: form,
  })
}

export async function generateAdvancedPhase(
  projectId: string,
  opts?: { verifyOnly?: boolean },
) {
  const q = new URLSearchParams({ use_agents: 'true' })
  if (opts?.verifyOnly) q.set('verify_only', 'true')
  return request<{
    project: AdvancedProject
    phase_id: string
    written: string[]
    via?: string
    run?: { run_id?: string; status?: string }
    changed_files?: string[]
    task_runs?: AdvancedPhase['task_runs']
    testing?: AdvancedPhase['testing']
  }>(
    `/platform/advanced/projects/${encodeURIComponent(projectId)}/generate?${q}`,
    { method: 'POST' },
  )
}

/** 按依赖波次生成剩余里程碑（默认可沙箱并行） */
export async function generateAdvancedRemaining(projectId: string) {
  return request<{
    project: AdvancedProject
    results: Array<{
      phase_id?: string
      via?: string
      written?: string[]
      changed_files?: string[]
      task_runs?: AdvancedPhase['task_runs']
      testing?: AdvancedPhase['testing']
    }>
    generated_count: number
    stopped_early?: boolean
    waves?: string[][]
    parallel_workers?: number
  }>(
    `/platform/advanced/projects/${encodeURIComponent(projectId)}/generate-remaining?use_agents=true&parallel_workers=2`,
    { method: 'POST' },
  )
}

/** 下载高级项目工作区 ZIP */
export function advancedProjectExportUrl(projectId: string) {
  return `${BASE}/platform/advanced/projects/${encodeURIComponent(projectId)}/export.zip`
}

export async function fetchAdvancedProjectTree(projectId: string) {
  return request<{
    project_id: string
    workspace: string
    paths: string[]
    truncated?: boolean
  }>(`/platform/advanced/projects/${encodeURIComponent(projectId)}/tree`)
}

export async function fetchAdvancedProjectFile(projectId: string, path: string) {
  const q = new URLSearchParams({ path })
  return request<{
    project_id: string
    path: string
    content: string
    truncated?: boolean
    size: number
  }>(
    `/platform/advanced/projects/${encodeURIComponent(projectId)}/file?${q.toString()}`,
  )
}

export async function copyAdvancedWorkspacePath(path: string) {
  await navigator.clipboard.writeText(path)
}
