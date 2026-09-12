/** 编排页 ↔ MAWP 内核：校验 / 运行路径约定（不新增 Agent） */

import {
  fetchStudioStages,
  getPlatformRun,
  resumeRun,
  validateWorkflow,
  type MawpRun,
} from '@/lib/mawp-api'

/** 与 backend platform.DELIVER_WORKFLOW 对齐 */
export const DELIVER_WORKFLOW_PATH =
  'apps/demo-code-agent/workflows/deliver.yaml'

export type KernelValidateResult = {
  ok: boolean
  workflow_id?: string
  errors: string[]
  path: string
}

/** 校验编排页实际会跑的 Deliver YAML（内核真路径） */
export async function validateDeliverWorkflow(): Promise<KernelValidateResult> {
  const res = await validateWorkflow({ path: DELIVER_WORKFLOW_PATH })
  return {
    ok: Boolean(res.ok),
    workflow_id: res.workflow_id,
    errors: Array.isArray(res.errors) ? res.errors : [],
    path: DELIVER_WORKFLOW_PATH,
  }
}

export function isWaitingUser(run: MawpRun | null | undefined): boolean {
  return (run?.status || '').toUpperCase() === 'WAITING_USER'
}

export function isTerminalRun(run: MawpRun | null | undefined): boolean {
  const s = (run?.status || '').toUpperCase()
  return s === 'DONE' || s === 'FAILED' || s === 'CANCELLED'
}

export async function approvePlatformRun(runId: string) {
  return resumeRun(runId, 'approve')
}

export async function rejectPlatformRun(runId: string) {
  return resumeRun(runId, 'reject')
}

export async function refreshPlatformRun(runId: string) {
  return getPlatformRun(runId)
}

export function platformRunLocalId(runId: string) {
  return `platform:${runId}`
}

async function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms))
}

/** 审批后续跑：轮询到 DONE / FAILED / CANCELLED / 再次 WAITING_USER */
export async function pollRunUntilSettled(
  runId: string,
  options?: {
    signal?: AbortSignal
    onTick?: (run: MawpRun, stages: Record<string, unknown>) => void
  },
): Promise<{ run: MawpRun; stages: Record<string, unknown> }> {
  let latest = await fetchStudioStages(runId)
  options?.onTick?.(latest.run, latest.stages as Record<string, unknown>)
  while (!isTerminalRun(latest.run) && !isWaitingUser(latest.run)) {
    if (options?.signal?.aborted) throw new Error('ABORTED')
    await sleep(800)
    latest = await fetchStudioStages(runId)
    options?.onTick?.(latest.run, latest.stages as Record<string, unknown>)
  }
  return { run: latest.run, stages: latest.stages as Record<string, unknown> }
}
