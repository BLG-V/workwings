import { STUDIO_ORDER, type StudioPageKind } from '@/lib/chat-intent'
import type { IResult } from '@/data/results'
import {
  fetchStudioStages,
  probeMawp,
  resumeRun,
  startStudioDeliver,
  streamRunEvents,
  type MawpRun,
  type SSEEvent,
} from '@/lib/mawp-api'
import {
  getScopedPlatformRunId,
  isPipelineActive,
  setScopedPlatformRunId,
  startPipelineFlow,
  writeStudioDraft,
} from '@/lib/studio-session'
import { formatDuration, replaceRunningRunForProject, upsertRun } from '@/lib/runs-store'
import { deliverProgress } from '@/lib/pipeline'
import { listProjects, updateProject } from '@/lib/projects-store'

export function getActivePlatformRunId(): string | null {
  return getScopedPlatformRunId()
}

export function setActivePlatformRunId(id: string | null) {
  setScopedPlatformRunId(id)
}

function asRecord(v: unknown): Record<string, unknown> {
  return v && typeof v === 'object' && !Array.isArray(v)
    ? (v as Record<string, unknown>)
    : {}
}

function yamlish(value: unknown, indent = 0): string {
  const pad = '  '.repeat(indent)
  if (value == null) return `${pad}null`
  if (typeof value === 'string') return `${pad}${value}`
  if (typeof value === 'number' || typeof value === 'boolean') return `${pad}${value}`
  if (Array.isArray(value)) {
    if (value.length === 0) return `${pad}(空)`
    return value
      .map((item) => {
        if (item && typeof item === 'object') {
          return `${pad}- ${yamlish(item, indent + 1).trimStart()}`
        }
        return `${pad}- ${String(item)}`
      })
      .join('\n')
  }
  const obj = asRecord(value)
  return Object.entries(obj)
    .map(([k, v]) => {
      if (v && typeof v === 'object') {
        return `${pad}- **${k}**\n${yamlish(v, indent + 1)}`
      }
      return `${pad}- **${k}**：${String(v)}`
    })
    .join('\n')
}

function formatTaskPlanMarkdown(
  stage: Record<string, unknown>,
  goal: string,
): string {
  const rawTasks = Array.isArray(stage.tasks) ? stage.tasks : []
  const tasks = rawTasks
    .map((item, index) => {
      const row = asRecord(item)
      const id = String(row.id || `T${index + 1}`)
      const title = String(row.title || row.name || '未命名任务')
      const deps = Array.isArray(row.depends_on)
        ? row.depends_on.map((d) => String(d))
        : []
      const desc = String(row.description || row.note || '').trim()
      return { id, title, deps, desc }
    })
    .filter((t) => t.title)

  const lines = [
    `# 任务规划 · ${goal.slice(0, 48) || 'Deliver'}`,
    '',
    `共 **${Number(stage.count) || tasks.length}** 项 · 来源 Planner（无独立架构 Agent）`,
    '',
  ]

  if (tasks.length === 0) {
    lines.push(
      '> 暂无任务拆解。重新运行全流程后，Planner 会输出带 depends_on 的任务列表。',
      '',
    )
    return lines.join('\n')
  }

  lines.push('## 执行顺序')
  lines.push('')
  lines.push('| 序号 | ID | 任务 | 依赖 |')
  lines.push('| --- | --- | --- | --- |')
  tasks.forEach((t, i) => {
    const dep = t.deps.length ? t.deps.join(', ') : '—'
    lines.push(`| ${i + 1} | \`${t.id}\` | ${t.title} | ${dep} |`)
  })
  lines.push('')

  const edged = tasks.filter((t) => t.deps.length > 0)
  if (edged.length > 0) {
    lines.push('## 依赖关系')
    lines.push('')
    for (const t of edged) {
      lines.push(`- ${t.deps.map((d) => `\`${d}\``).join(' + ')} → \`${t.id}\` ${t.title}`)
    }
    lines.push('')
  } else {
    lines.push('## 依赖关系')
    lines.push('')
    lines.push('各任务无前置依赖，可按表内顺序串行交付。')
    lines.push('')
  }

  const withDesc = tasks.filter((t) => t.desc)
  if (withDesc.length > 0) {
    lines.push('## 任务说明')
    lines.push('')
    for (const t of withDesc) {
      lines.push(`- **${t.id}** ${t.title}：${t.desc}`)
    }
    lines.push('')
  }

  const hint = String(stage.goal_hint || '').trim()
  if (hint) {
    lines.push('## 需求摘要（参考）')
    lines.push('')
    lines.push(hint.length > 160 ? `${hint.slice(0, 160)}…` : hint)
    lines.push('')
  }

  lines.push('> 详细需求见「需求文档」Tab；这里只看任务拆解与依赖。')
  return lines.join('\n')
}

function asPathList(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  const out: string[] = []
  for (const item of value) {
    if (typeof item === 'string') {
      const p = item.replace(/\\/g, '/').trim()
      if (p) out.push(p)
      continue
    }
    const row = asRecord(item)
    const p = String(row.path || row.file || row.name || '')
      .replace(/\\/g, '/')
      .trim()
    if (p) out.push(p)
  }
  return [...new Set(out)]
}

function groupPathsByDir(paths: string[]): Map<string, string[]> {
  const groups = new Map<string, string[]>()
  for (const path of paths) {
    const i = path.lastIndexOf('/')
    const dir = i >= 0 ? path.slice(0, i) : '.'
    const name = i >= 0 ? path.slice(i + 1) : path
    const list = groups.get(dir) || []
    list.push(name)
    groups.set(dir, list)
  }
  for (const list of groups.values()) list.sort()
  return groups
}

/** 侧栏文件树：按目录分组 */
export function buildCodeFileTree(
  paths: string[],
): NonNullable<IResult['fileTree']> {
  return [...groupPathsByDir(paths).entries()].map(([name, children]) => ({
    name,
    children: children.map((n) => ({ name: n })),
  }))
}

function formatCodeMarkdown(
  stage: Record<string, unknown>,
  _goal: string,
): string {
  const frontend = asRecord(stage.frontend)
  const files = asPathList(stage.changed_files)
  const tasksDone = asPathList(stage.tasks_done)
  const pages = Array.isArray(frontend.pages) ? frontend.pages : []
  const artifacts = asPathList(frontend.artifacts)
  const taskRuns = Array.isArray(stage.task_runs) ? stage.task_runs : []
  const status = String(stage.status ?? 'ok')
  const mode = String(stage.mode ?? 'default')
  const frontendDir = String(frontend.frontend_dir || '')
    .replace(/\\/g, '/')
    .trim()

  const lines = [
    '# 代码实现',
    '',
    `共 **${files.length}** 个变更文件 · 状态 \`${status}\` · 模式 \`${mode}\` · Coding + Frontend`,
    '',
  ]

  if (tasksDone.length > 0) {
    lines.push('## 完成任务')
    lines.push('')
    lines.push(tasksDone.map((t) => `- \`${t}\``).join('\n'))
    lines.push('')
  }

  lines.push('## 变更文件')
  lines.push('')
  if (files.length === 0) {
    lines.push('> 暂无变更文件。重新跑 Coding/Frontend 或点「刷新产物」拉取已有 Run。')
    lines.push('')
  } else {
    for (const [dir, names] of groupPathsByDir(files)) {
      lines.push(`### \`${dir}\``)
      lines.push('')
      for (const name of names) {
        lines.push(`- \`${name}\``)
      }
      lines.push('')
    }
  }

  if (frontendDir || pages.length > 0 || artifacts.length > 0) {
    lines.push('## Frontend')
    lines.push('')
    if (frontendDir) {
      lines.push(`- 目录：\`${frontendDir}\``)
      lines.push('')
    }
    if (pages.length > 0) {
      lines.push('| 页面 | 标题 |')
      lines.push('| --- | --- |')
      for (const item of pages) {
        const row = asRecord(item)
        const path = escapeMdCell(row.path || row.file || '—')
        const title = escapeMdCell(row.title || row.name || '—')
        lines.push(`| \`${path}\` | ${title} |`)
      }
      lines.push('')
    }
    if (artifacts.length > 0) {
      lines.push('### 产物')
      lines.push('')
      for (const a of artifacts) {
        lines.push(`- \`${a}\``)
      }
      lines.push('')
    }
  }

  if (taskRuns.length > 0) {
    lines.push('## 任务循环')
    lines.push('')
    lines.push('| 任务 | 标题 | 结果 | 尝试 | 文件数 |')
    lines.push('| --- | --- | --- | --- | --- |')
    for (const item of taskRuns) {
      const row = asRecord(item)
      const tid = escapeMdCell(row.task_id || '—')
      const title = escapeMdCell(row.title || '—')
      const ok = row.success === true ? '✓' : row.success === false ? '✗' : '—'
      const attempts = escapeMdCell(row.attempts ?? 1)
      const n = asPathList(row.changed_files).length
      lines.push(`| \`${tid}\` | ${title} | ${ok} | ${attempts} | ${n} |`)
    }
    lines.push('')
  }

  lines.push('> 详细需求见「需求文档」；此处只列 Coding / Frontend 变更与页面。')
  return lines.join('\n')
}

function formatTestMarkdown(
  stage: Record<string, unknown>,
  stages: Record<string, unknown>,
): string {
  const passed = stage.passed === true
  const status = String(stage.status || (passed ? 'pass' : 'fail')).toLowerCase()
  const attempt = Number(stage.attempt ?? 1) || 1
  const metric = String(
    stage.metric_command || stage.verify_command || '',
  ).trim()
  const exitCode = stage.exit_code
  const failures = Array.isArray(stage.failures) ? stage.failures : []
  const log = String(stage.log_summary || '').trim()
  const raw = asRecord(stages.raw)
  const debug = asRecord(raw.debug)

  const verdict = passed ? '通过' : '未通过'
  const lines = [
    '# 测试报告',
    '',
    `结果 **${verdict}** · 状态 \`${status}\` · 第 **${attempt}** 轮 · Testing Agent`,
    '',
    '## 验收摘要',
    '',
    '| 项 | 值 |',
    '| --- | --- |',
    `| 通过 | ${passed ? '✓ true' : '✗ false'} |`,
    `| 状态 | \`${status}\` |`,
    `| 轮次 | ${attempt} |`,
    `| metric | ${metric ? `\`${escapeMdCell(metric)}\`` : '演示 / 未配置真实命令'} |`,
    `| exit | ${exitCode == null || exitCode === '' ? '—' : `\`${escapeMdCell(exitCode)}\``} |`,
    '',
  ]

  lines.push('## 失败项')
  lines.push('')
  if (failures.length === 0) {
    lines.push(passed ? '> 无失败项。' : '> 未列出具体失败项，请看下方日志摘要。')
    lines.push('')
  } else {
    lines.push('| # | 说明 |')
    lines.push('| --- | --- |')
    failures.forEach((item, i) => {
      let text: string
      if (item && typeof item === 'object') {
        const row = asRecord(item)
        text = String(
          row.message || row.error || row.title || row.name || JSON.stringify(item),
        )
      } else {
        text = String(item ?? '')
      }
      lines.push(`| ${i + 1} | ${escapeMdCell(text)} |`)
    })
    lines.push('')
  }

  lines.push('## 日志摘要')
  lines.push('')
  if (log) {
    lines.push('```')
    lines.push(log.length > 4000 ? `${log.slice(0, 4000)}\n…（已截断）` : log)
    lines.push('```')
  } else {
    lines.push('> （无日志）')
  }
  lines.push('')

  if (Object.keys(debug).length > 0) {
    const fixed = debug.fixed === true
    const note = String(debug.note || '').trim()
    const based = Array.isArray(debug.based_on_failures)
      ? debug.based_on_failures
      : []
    const changed = asPathList(debug.changed_files)
    lines.push('## 调试跟进')
    lines.push('')
    lines.push(
      `- 修复：${fixed ? '✓ 已尝试修复' : String(debug.status || '—')}`,
    )
    if (note) lines.push(`- 说明：${note}`)
    if (based.length > 0) {
      lines.push(`- 依据失败：${based.map((b) => `\`${escapeMdCell(b)}\``).join(', ')}`)
    }
    if (changed.length > 0) {
      lines.push(`- 变更文件：${changed.map((p) => `\`${p}\``).join(', ')}`)
    }
    lines.push('')
  }

  lines.push(
    '> project_mode 时 metric 为真实冒烟命令；演示模式可能为 pass_on_attempt。',
  )
  return lines.join('\n')
}

/** 把平台 node_outputs 格式化成 Studio Markdown */

function escapeMdCell(raw: unknown): string {
  return String(raw ?? '')
    .replace(/\|/g, '\\|')
    .replace(/\r?\n/g, ' ')
    .trim()
}

function bulletList(items: unknown[], empty = '（暂无）'): string {
  const rows = (Array.isArray(items) ? items : items == null ? [] : [items])
    .map((item) => {
      if (item && typeof item === 'object') {
        const rec = asRecord(item)
        const title = rec.title || rec.name || rec.id
        if (title) return `- ${escapeMdCell(title)}`
        return `- ${escapeMdCell(JSON.stringify(item))}`
      }
      const text = String(item ?? '').trim()
      return text ? `- ${text}` : ''
    })
    .filter(Boolean)
  return rows.length ? rows.join('\n') : empty
}

function checklist(items: unknown[], empty = '（暂无）'): string {
  const rows = (Array.isArray(items) ? items : items == null ? [] : [items])
    .map((item) => {
      const text =
        item && typeof item === 'object'
          ? escapeMdCell(
              asRecord(item).title ||
                asRecord(item).name ||
                asRecord(item).text ||
                JSON.stringify(item),
            )
          : String(item ?? '').trim()
      return text ? `- [ ] ${text}` : ''
    })
    .filter(Boolean)
  return rows.length ? rows.join('\n') : empty
}

function tasksTable(tasks: unknown): string {
  const rows = (Array.isArray(tasks) ? tasks : [])
    .map((item) => asRecord(item))
    .filter((row) => Object.keys(row).length > 0)
  if (!rows.length) return '（暂无任务）'
  return [
    '| ID | 任务 | 依赖 |',
    '|----|------|------|',
    ...rows.map((row) => {
      const id = escapeMdCell(row.id || '—')
      const title = escapeMdCell(row.title || row.name || '—')
      const deps = Array.isArray(row.depends_on)
        ? row.depends_on.map((d) => escapeMdCell(d)).filter(Boolean).join(', ')
        : escapeMdCell(row.depends_on || '无')
      return `| ${id} | ${title} | ${deps || '无'} |`
    }),
  ].join('\n')
}

function firstSentence(text: string, max = 120): string {
  const t = text.replace(/\s+/g, ' ').trim()
  if (!t) return ''
  const m = t.match(/^(.{1,120}?[。.!？?；;])/)
  const cut = (m?.[1] || t).trim()
  return cut.length > max ? `${cut.slice(0, max)}…` : cut
}

function formatRequirementMarkdown(
  stage: Record<string, unknown>,
  goal: string,
): string {
  const summary = String(stage.summary || goal).trim() || goal
  const overview = firstSentence(summary, 160) || firstSentence(goal, 160) || '（无概述）'
  const specRef = stage.spec_ref ? String(stage.spec_ref) : ''
  const tasks = Array.isArray(stage.tasks) ? stage.tasks : []
  const ui = Array.isArray(stage.ui_key_points) ? stage.ui_key_points : []
  const ac = Array.isArray(stage.acceptance_criteria)
    ? stage.acceptance_criteria
    : []

  const lines = [
    '# 需求规格说明（PRD）',
    '',
    `共 **${tasks.length}** 项功能任务 · **${ui.length}** 条界面要点 · **${ac.length}** 条验收 · Requirement Agent`,
    '',
    '## 产品概述',
    '',
    overview,
    '',
  ]

  if (specRef) {
    lines.push(`- 规格参考：\`${specRef}\``)
    lines.push('')
  }

  lines.push('## 功能与任务')
  lines.push('')
  lines.push(tasksTable(stage.tasks))
  lines.push('')

  lines.push('## 界面要点')
  lines.push('')
  lines.push(bulletList(stage.ui_key_points))
  lines.push('')

  lines.push('## 验收标准')
  lines.push('')
  lines.push(checklist(stage.acceptance_criteria))
  lines.push('')

  // 仅当原始目标与概述明显不同时再附摘录，避免整段重复
  const goalTrim = goal.trim()
  const sameAsSummary =
    !goalTrim ||
    goalTrim === summary ||
    summary.startsWith(goalTrim.slice(0, 40)) ||
    goalTrim.startsWith(summary.slice(0, 40))
  if (goalTrim && !sameAsSummary) {
    lines.push('## 原始目标（摘录）')
    lines.push('')
    lines.push(firstSentence(goalTrim, 200) || goalTrim.slice(0, 200))
    lines.push('')
  }

  lines.push('> 任务依赖细节见「任务规划」Tab；此处看需求与验收。')
  return lines.join('\n')
}

function reviewStatusLabel(status: string): string {
  const s = status.toLowerCase()
  if (s === 'pass' || s === 'ok' || s === 'passed') return '通过'
  if (s === 'blocking' || s === 'blocked' || s === 'fail' || s === 'failed')
    return '拦截'
  return status || '未知'
}

function formatFindingsTable(findings: unknown): string[] {
  const items = Array.isArray(findings) ? findings : []
  if (!items.length) return ['> 无审查发现项。', '']
  const lines = [
    '| # | 级别 | 位置 | 说明 |',
    '| --- | --- | --- | --- |',
  ]
  items.forEach((item, i) => {
    if (item && typeof item === 'object') {
      const row = asRecord(item)
      const level = escapeMdCell(row.level || row.severity || row.status || '—')
      const loc = escapeMdCell(row.file || row.path || row.location || '—')
      const msg = escapeMdCell(
        row.message || row.title || row.reason || JSON.stringify(item),
      )
      lines.push(`| ${i + 1} | ${level} | \`${loc}\` | ${msg} |`)
    } else {
      lines.push(`| ${i + 1} | — | — | ${escapeMdCell(item)} |`)
    }
  })
  lines.push('')
  return lines
}

function cleanDeliveryNotes(raw: string): string {
  const text = raw.trim()
  if (!text) return ''
  return text
    .replace(/^#\s*Delivery Notes[^\n]*\n+/i, '')
    .replace(/\nauto_push:\s*false\b/gi, '')
    .replace(/\nauto_merge:\s*false\b/gi, '')
    .trim()
}

function formatDeployMarkdown(
  stage: Record<string, unknown>,
  stages: Record<string, unknown>,
  goal: string,
): string {
  const review = asRecord(stage.review)
  const raw = asRecord(stages.raw)
  const human = asRecord(raw.human_review)
  const code = asRecord(stages.code)
  const frontend = asRecord(code.frontend)
  const files = asPathList(stage.changed_files).length
    ? asPathList(stage.changed_files)
    : asPathList(code.changed_files)
  const artifacts = asPathList(stage.artifacts).length
    ? asPathList(stage.artifacts)
    : asPathList(frontend.artifacts)
  const reviewStatus = String(review.status || '').toLowerCase()
  const blocking = Number(review.blocking_count ?? 0) || 0
  const shipStatus = String(stage.status || 'ok')
  const notes = cleanDeliveryNotes(String(stage.delivery_notes || ''))
  const commit = String(stage.commit_message || '').trim()
  const artifact = String(stage.artifact || '').trim()
  const testingPassed = stage.testing_passed
  const autoPush = stage.auto_push === true
  const autoMerge = stage.auto_merge === true

  const lines = [
    '# 审查与交付',
    '',
    `审查 **${reviewStatusLabel(reviewStatus)}** · 阻塞 **${blocking}** · 交付 \`${shipStatus}\` · Review + Ship`,
    '',
    '## 审查结论',
    '',
    '| 项 | 值 |',
    '| --- | --- |',
    `| 结论 | ${reviewStatusLabel(reviewStatus)}${reviewStatus ? ` (\`${reviewStatus}\`)` : ''} |`,
    `| 阻塞项 | ${blocking} |`,
    `| 交付状态 | \`${shipStatus}\` |`,
    `| 测试通过 | ${testingPassed === true ? '✓' : testingPassed === false ? '✗' : '—'} |`,
  ]
  if (human.decision) {
    lines.push(`| 人工审批 | \`${escapeMdCell(human.decision)}\` |`)
  }
  lines.push('')

  lines.push('## 发现项')
  lines.push('')
  lines.push(...formatFindingsTable(review.findings))

  lines.push('## 交付产物')
  lines.push('')
  const listed = [...files, ...artifacts, ...(artifact ? [artifact] : [])]
  const uniq = [...new Set(listed.map((p) => p.replace(/\\/g, '/')))]
  if (!uniq.length) {
    lines.push('> 未列出独立产物文件；说明正文里可能仍有路径。')
    lines.push('')
  } else {
    for (const [dir, names] of groupPathsByDir(uniq)) {
      lines.push(`### \`${dir}\``)
      lines.push('')
      for (const name of names) lines.push(`- \`${name}\``)
      lines.push('')
    }
  }

  lines.push('## 人工发布（平台不会代劳）')
  lines.push('')
  lines.push('| 开关 | 值 | 说明 |')
  lines.push('| --- | --- | --- |')
  lines.push(
    `| auto_push | ${autoPush ? '✗ true（异常）' : '关闭 false'} | 必须为 false，禁止自动推送 |`,
  )
  lines.push(
    `| auto_merge | ${autoMerge ? '✗ true（异常）' : '关闭 false'} | 必须为 false，禁止自动合并 |`,
  )
  lines.push('')
  if (commit) {
    lines.push('建议提交说明：')
    lines.push('')
    lines.push('```')
    lines.push(commit)
    lines.push('```')
    lines.push('')
  }
  const shipList = Array.isArray(stage.checklist) ? stage.checklist : []
  lines.push('发布清单：')
  lines.push('')
  lines.push(
    shipList.length
      ? checklist(shipList)
      : [
          '- [ ] 阅读交付说明与产物',
          '- [ ] 人工 git commit',
          '- [ ] 人工 git push / 开 PR（如需要）',
          '- [ ] 人工合并（平台不会 merge）',
        ].join('\n'),
  )
  lines.push('')

  lines.push('## 交付说明')
  lines.push('')
  if (notes) {
    lines.push(notes)
  } else {
    lines.push(goal.trim() ? `> 目标：${goal.trim().slice(0, 400)}` : '> 暂无交付说明。')
  }
  lines.push('')
  lines.push('> 来源：MAWP Review + Ship（禁止自动 push/merge）')
  return lines.join('\n')
}

export function formatStageMarkdown(
  kind: StudioPageKind,
  stages: Record<string, unknown>,
  goal: string,
): string {
  const stage = asRecord(stages[kind])
  if (kind === 'requirement') {
    return formatRequirementMarkdown(stage, goal)
  }
  if (kind === 'architecture') {
    return formatTaskPlanMarkdown(stage, goal)
  }
  if (kind === 'code') {
    return formatCodeMarkdown(stage, goal)
  }
  if (kind === 'test') {
    return formatTestMarkdown(stage, stages)
  }
  return formatDeployMarkdown(stage, stages, goal)
}

function mapPlatformStatus(status: string): 'running' | 'completed' | 'failed' {
  const s = status.toUpperCase()
  if (s === 'DONE') return 'completed'
  if (s === 'FAILED' || s === 'CANCELLED') return 'failed'
  return 'running'
}

function mergeOutputKeys(run: MawpRun, keys?: string[] | null): MawpRun {
  if (!keys?.length) return run
  const outputs = { ...(run.node_outputs || {}) }
  let changed = false
  for (const key of keys) {
    if (key && !outputs[key]) {
      outputs[key] = { _stream: true }
      changed = true
    }
  }
  return changed ? { ...run, node_outputs: outputs } : run
}

function applyStreamSnapshot(run: MawpRun, snap: SSEEvent): MawpRun {
  const next: MawpRun = {
    ...run,
    status: snap.status || run.status,
    current_node_id: snap.current_node_id ?? snap.node_id ?? run.current_node_id,
    failed_node_id: snap.failed_node_id ?? run.failed_node_id,
    error: snap.error || run.error,
  }
  const keys = [...(snap.node_outputs_keys || [])]
  const kind = String(snap.type || '').toLowerCase()
  if (snap.node_id && (kind.includes('end') || kind.includes('done') || snap.status === 'DONE')) {
    keys.push(snap.node_id)
  }
  return mergeOutputKeys(next, keys)
}

function syncLocalRun(
  run: MawpRun,
  projectName: string,
  startedAt: number,
  projectId = 'platform-deliver',
) {
  mirrorPlatformRunToLocal(run, { projectName, projectId, startedAt })
}

export function mirrorPlatformRunToLocal(
  run: MawpRun,
  options?: {
    projectName?: string
    projectId?: string
    startedAt?: number
  },
) {
  if (!run.run_id) return
  const progress = deliverProgress(run)
  const projects = listProjects()
  const matched =
    projects.find((p) => p.kernelRunId === run.run_id) ||
    (options?.projectId
      ? projects.find((p) => p.id === options.projectId)
      : undefined)
  const projectId = options?.projectId || matched?.id || 'platform-deliver'
  const projectName =
    options?.projectName || matched?.name || run.workflow_id || 'Deliver'
  const startedAt = options?.startedAt || Date.parse(run.created_at || '') || Date.now()
  const mapped = mapPlatformStatus(run.status)
  const row = {
    id: `platform:${run.run_id}`,
    projectId,
    projectName,
    status: mapped,
    startTime: run.created_at || new Date(startedAt).toISOString(),
    endTime:
      mapped !== 'running'
        ? run.updated_at || new Date().toISOString()
        : undefined,
    duration:
      mapped === 'running'
        ? '运行中...'
        : formatDuration(Date.now() - startedAt),
    nodesTotal: progress.total,
    nodesCompleted: progress.completed,
    logsCount: Math.max(
      progress.completed,
      Object.keys(run.node_outputs || {}).length,
    ),
  }
  if (mapped === 'running') {
    replaceRunningRunForProject(projectId, row)
  } else {
    upsertRun(row)
  }
  if (matched) {
    const nextStatus =
      mapped === 'completed'
        ? 'completed'
        : mapped === 'failed'
          ? 'failed'
          : 'running'
    updateProject(matched.id, {
      kernelRunId: run.run_id,
      status: nextStatus,
      progress: progress.percent,
    })
  }
}

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms))
}

export async function runDeliverPipeline(options: {
  goal: string
  topic?: string
  projectId?: string
  projectName?: string
  projectMode?: boolean
  /** Studio 默认 true；编排页应 false，停在 WAITING_USER 等人审 */
  autoApprove?: boolean
  signal?: AbortSignal
  onProgress?: (info: {
    run: MawpRun
    stages: Record<string, unknown>
    currentNode?: string | null
    event?: SSEEvent
    statusEvent?: SSEEvent
  }) => void
}): Promise<{
  run: MawpRun
  stages: Record<string, unknown>
  usedPlatform: boolean
  projectRoot?: string | null
  waitingUser?: boolean
}> {
  const goal = options.goal.trim()
  const health = await probeMawp()
  if (!health) {
    throw new Error('MAWP_OFFLINE')
  }

  const startedAt = Date.now()
  const projectName = options.projectName || options.topic || goal.slice(0, 24) || 'Deliver'
  const started = await startStudioDeliver(goal, {
    async_mode: true,
    review_status: 'pass',
    pass_on_attempt: 1,
    project_mode: Boolean(options.projectMode),
    project_title: projectName,
    create_workspace: Boolean(options.projectMode),
  })

  let run = started.run
  let stages = (started.stages || {}) as Record<string, unknown>
  const projectRoot = started.project_root ?? null
  setActivePlatformRunId(run.run_id)
  syncLocalRun(run, projectName, startedAt, options.projectId)
  options.onProgress?.({ run, stages, currentNode: run.current_node_id })

  // 尝试 SSE 实时流，失败则降级为轮询
  let useSSE = true
  let sseClosed = false

  const terminal = new Set(['DONE', 'FAILED', 'CANCELLED', 'WAITING_USER'])

  if (useSSE) {
    try {
      await new Promise<void>((resolve, reject) => {
        let stopStream = () => {}
        const pullFull = () => {
          void fetchStudioStages(run.run_id)
            .then((latest) => {
              if (options.signal?.aborted) return
              run = {
                ...run,
                ...latest.run,
                node_outputs: {
                  ...(run.node_outputs || {}),
                  ...(latest.run.node_outputs || {}),
                },
              }
              stages = (latest.stages || stages) as Record<string, unknown>
              syncLocalRun(run, projectName, startedAt, options.projectId)
              options.onProgress?.({
                run,
                stages,
                currentNode: run.current_node_id,
              })
            })
            .catch(() => {
              /* 快照失败不影响 SSE */
            })
        }
        const fullTimer = setInterval(pullFull, 4000)
        const finish = () => {
          clearInterval(fullTimer)
          stopStream()
        }

        stopStream = streamRunEvents(
          run.run_id,
          // onEvent: 节点事件
          (evt) => {
            if (options.signal?.aborted) {
              finish()
              reject(new Error('ABORTED'))
              return
            }
            run = applyStreamSnapshot(run, evt)
            syncLocalRun(run, projectName, startedAt, options.projectId)
            options.onProgress?.({
              run,
              stages,
              currentNode: evt.node_id || run.current_node_id,
              event: evt,
            })
          },
          // onStatus: 状态快照
          (status) => {
            if (options.signal?.aborted) {
              finish()
              reject(new Error('ABORTED'))
              return
            }
            run = applyStreamSnapshot(run, status)
            syncLocalRun(run, projectName, startedAt, options.projectId)
            options.onProgress?.({
              run,
              stages,
              currentNode: status.current_node_id || run.current_node_id,
              statusEvent: status,
            })
          },
          // onDone: 终态
          () => {
            sseClosed = true
            finish()
            fetchStudioStages(run.run_id)
              .then((latest) => {
                run = latest.run
                stages = latest.stages as Record<string, unknown>
                syncLocalRun(run, projectName, startedAt, options.projectId)
                options.onProgress?.({ run, stages, currentNode: run.current_node_id })
                resolve()
              })
              .catch(() => resolve())
          },
          // onError
          (err) => {
            if (!sseClosed) {
              console.warn('[SSE] stream error, falling back to polling:', err)
              useSSE = false
              finish()
              resolve()
            }
          },
        )

        setTimeout(() => {
          if (!sseClosed) {
            finish()
            resolve()
          }
        }, 600000)
      })
    } catch {
      useSSE = false
    }
  }

  // 降级轮询
  if (!sseClosed && !terminal.has((run.status || '').toUpperCase())) {
    while (!terminal.has((run.status || '').toUpperCase())) {
      if (options.signal?.aborted) throw new Error('ABORTED')
      await sleep(800)
      const latest = await fetchStudioStages(run.run_id)
      run = latest.run
      stages = latest.stages as Record<string, unknown>
      syncLocalRun(run, projectName, startedAt, options.projectId)
      options.onProgress?.({ run, stages, currentNode: run.current_node_id })
    }
  }

  if ((run.status || '').toUpperCase() === 'WAITING_USER') {
    const autoApprove = options.autoApprove !== false
    if (!autoApprove) {
      syncLocalRun(run, projectName, startedAt, options.projectId)
      return {
        run,
        stages,
        usedPlatform: true,
        projectRoot,
        waitingUser: true,
      }
    }
    const resumed = await resumeRun(run.run_id, 'approve')
    run = resumed.run
    if (resumed.stages) stages = resumed.stages as Record<string, unknown>
    // continue polling if still running
    while (!['DONE', 'FAILED', 'CANCELLED'].includes((run.status || '').toUpperCase())) {
      if (options.signal?.aborted) throw new Error('ABORTED')
      await sleep(800)
      const latest = await fetchStudioStages(run.run_id)
      run = latest.run
      stages = latest.stages as Record<string, unknown>
      syncLocalRun(run, projectName, startedAt, options.projectId)
      options.onProgress?.({ run, stages, currentNode: run.current_node_id })
    }
  }

  syncLocalRun(run, projectName, startedAt, options.projectId)

  if ((run.status || '').toUpperCase() === 'FAILED') {
    throw new Error(run.error || '平台 Deliver 执行失败')
  }

  // 把五阶段草稿写入 session，供各 Studio 页直接用
  for (const kind of [
    'requirement',
    'architecture',
    'code',
    'test',
    'deploy',
  ] as StudioPageKind[]) {
    const content = formatStageMarkdown(kind, stages, goal)
    writeStudioDraft(kind, {
      prompt: goal,
      output: content,
      done: true,
      isDemo: false,
      thinkingSteps: [
        `平台 Run ${run.run_id}`,
        `节点 ${run.current_node_id || 'end'}`,
        `阶段 ${kind} 已从 node_outputs 映射`,
      ],
      thinkingDone: true,
    })
  }

  return { run, stages, usedPlatform: true, projectRoot, waitingUser: false }
}

export function stageContentFromCache(
  kind: StudioPageKind,
  stages: Record<string, unknown>,
  goal: string,
): string {
  return formatStageMarkdown(kind, stages, goal)
}

/** 把 Deliver stages 映射成编排页「智能产物」列表 */
const STAGE_RESULT_META: {
  kind: StudioPageKind
  type: IResult['type']
  title: string
  summary: string
}[] = [
  {
    kind: 'requirement',
    type: 'requirement',
    title: '需求文档',
    summary: '来自 Requirement Agent',
  },
  {
    kind: 'architecture',
    type: 'architecture',
    title: '任务规划',
    summary: 'Planner 任务拆解与依赖（非系统架构图）',
  },
  {
    kind: 'code',
    type: 'code',
    title: '代码与前端',
    summary: '来自 Coding + Frontend Agent',
  },
  {
    kind: 'test',
    type: 'test',
    title: '测试报告',
    summary: '来自 Testing / Debug Agent',
  },
  {
    kind: 'deploy',
    type: 'deployment',
    title: '审查与交付',
    summary: '来自 Review + Ship Agent',
  },
]

export function resultsFromDeliverStages(
  projectId: string,
  goal: string,
  stages: Record<string, unknown> | null | undefined,
  runId?: string | null,
): IResult[] {
  const text = goal.trim() || 'Deliver'
  const bag = stages || {}
  const stamp = Date.now()
  const rid = runId ? runId.slice(0, 8) : ''
  return STAGE_RESULT_META.map((row) => {
    const content = formatStageMarkdown(row.kind, bag, text)
    const base: IResult = {
      id: `deliver-${row.type}-${runId || stamp}`,
      projectId,
      type: row.type,
      title: rid ? `${row.title} · ${rid}` : row.title,
      summary: row.summary,
      content,
    }
    if (row.type === 'code') {
      const codeStage = asRecord(bag.code)
      const files = asPathList(codeStage.changed_files)
      const frontend = asRecord(codeStage.frontend)
      const extra = asPathList(frontend.artifacts).filter((p) => p.includes('/'))
      const tree = buildCodeFileTree([...files, ...extra])
      if (tree.length > 0) base.fileTree = tree
    }
    return base
  })
}

/** 用已有 Deliver Run 填满五阶段草稿，不新开一轮 */
export async function hydrateAllStudioDraftsFromRun(runId: string, goal: string) {
  const text = goal.trim()
  if (!isPipelineActive()) startPipelineFlow(text)
  const latest = await fetchStudioStages(runId)
  const stages = (latest.stages || {}) as Record<string, unknown>
  for (const kind of STUDIO_ORDER) {
    writeStudioDraft(kind, {
      prompt: text,
      output: formatStageMarkdown(kind, stages, text),
      done: true,
      isDemo: false,
      thinkingSteps: [
        `复用平台 Run ${runId}`,
        `阶段 ${kind} 已从 node_outputs 映射`,
      ],
      thinkingDone: true,
    })
  }
  return { run: latest.run, stages }
}

/** deliver 节点 → studio 阶段进度提示 */
export function studioKindFromNode(nodeId: string | null | undefined): StudioPageKind | null {
  if (!nodeId) return null
  const map: Record<string, StudioPageKind> = {
    planner: 'architecture',
    requirement: 'requirement',
    coding: 'code',
    frontend: 'code',
    testing: 'test',
    debug: 'test',
    review: 'deploy',
    ship: 'deploy',
    // 兼容旧画布类型
    analysis: 'requirement',
    architecture: 'architecture',
    development: 'code',
    deployment: 'deploy',
  }
  return map[nodeId] ?? null
}
