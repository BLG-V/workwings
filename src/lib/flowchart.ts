/** 流程图统一数据模型（预览 / 编辑 / 导出共用） */

export type FlowNodeType = 'start' | 'end' | 'process' | 'decision' | 'io'

export interface FlowchartNode {
  id: string
  label: string
  type: FlowNodeType
  x?: number
  y?: number
}

export interface FlowchartEdge {
  id: string
  source: string
  target: string
  label?: string
}

export interface FlowchartPayload {
  title: string
  nodes: FlowchartNode[]
  edges: FlowchartEdge[]
  createdAt: string
  sourceHint?: string
}

const NODE_TYPES: FlowNodeType[] = [
  'start',
  'end',
  'process',
  'decision',
  'io',
]

function asType(v: unknown): FlowNodeType {
  const s = String(v || 'process').toLowerCase()
  if (NODE_TYPES.includes(s as FlowNodeType)) return s as FlowNodeType
  if (/开始|start/.test(s)) return 'start'
  if (/结束|end/.test(s)) return 'end'
  if (/判断|决策|decision|菱形/.test(s)) return 'decision'
  if (/输入|输出|io|document/.test(s)) return 'io'
  return 'process'
}

/** 从模型回复中提取 JSON 流程图 */
export function parseFlowchartFromModel(
  raw: string,
  fallbackTitle = '流程图',
): Omit<FlowchartPayload, 'createdAt'> {
  const text = raw.trim()
  let jsonStr = text
  const fence = text.match(/```(?:json)?\s*([\s\S]*?)```/i)
  if (fence?.[1]) jsonStr = fence[1].trim()
  else {
    const start = text.indexOf('{')
    const end = text.lastIndexOf('}')
    if (start >= 0 && end > start) jsonStr = text.slice(start, end + 1)
  }

  let data: unknown
  try {
    data = JSON.parse(jsonStr)
  } catch {
    throw new Error('模型未返回可解析的流程图 JSON，请重试或换种描述')
  }

  const obj = data as Record<string, unknown>
  const rawNodes = Array.isArray(obj.nodes) ? obj.nodes : []
  const rawEdges = Array.isArray(obj.edges) ? obj.edges : []

  const nodes: FlowchartNode[] = rawNodes
    .map((n, i) => {
      const row = n as Record<string, unknown>
      const id = String(row.id || `n${i + 1}`).replace(/\s+/g, '_')
      const label = String(row.label || row.text || row.name || `节点${i + 1}`).trim()
      return {
        id,
        label: label.slice(0, 40),
        type: asType(row.type),
        x: typeof row.x === 'number' ? row.x : undefined,
        y: typeof row.y === 'number' ? row.y : undefined,
      }
    })
    .filter((n) => n.label)

  if (nodes.length < 2) {
    throw new Error('流程图节点过少，请补充更完整的流程描述或上传文档')
  }

  const idSet = new Set(nodes.map((n) => n.id))
  const edges: FlowchartEdge[] = rawEdges
    .map((e, i) => {
      const row = e as Record<string, unknown>
      const source = String(row.source || row.from || '')
      const target = String(row.target || row.to || '')
      if (!idSet.has(source) || !idSet.has(target)) return null
      return {
        id: String(row.id || `e${i + 1}`),
        source,
        target,
        label: row.label ? String(row.label).slice(0, 20) : undefined,
      }
    })
    .filter(Boolean) as FlowchartEdge[]

  // 若无边，按节点顺序串起来
  if (edges.length === 0 && nodes.length > 1) {
    for (let i = 0; i < nodes.length - 1; i++) {
      edges.push({
        id: `e${i + 1}`,
        source: nodes[i].id,
        target: nodes[i + 1].id,
      })
    }
  }

  const laid = layoutFlowchart({ nodes, edges })
  return {
    title: String(obj.title || fallbackTitle).slice(0, 40) || fallbackTitle,
    nodes: laid.nodes,
    edges: laid.edges,
  }
}

/** 简单自上而下布局 */
export function layoutFlowchart(graph: {
  nodes: FlowchartNode[]
  edges: FlowchartEdge[]
}): { nodes: FlowchartNode[]; edges: FlowchartEdge[] } {
  const indeg = new Map<string, number>()
  graph.nodes.forEach((n) => indeg.set(n.id, 0))
  graph.edges.forEach((e) => {
    indeg.set(e.target, (indeg.get(e.target) || 0) + 1)
  })

  const levels = new Map<string, number>()
  const queue = graph.nodes
    .filter((n) => (indeg.get(n.id) || 0) === 0)
    .map((n) => n.id)
  queue.forEach((id) => levels.set(id, 0))

  const outs = new Map<string, string[]>()
  graph.edges.forEach((e) => {
    const list = outs.get(e.source) || []
    list.push(e.target)
    outs.set(e.source, list)
  })

  const seen = new Set<string>(queue)
  while (queue.length) {
    const id = queue.shift()!
    const lv = levels.get(id) || 0
    for (const t of outs.get(id) || []) {
      levels.set(t, Math.max(levels.get(t) || 0, lv + 1))
      if (!seen.has(t)) {
        seen.add(t)
        queue.push(t)
      }
    }
  }

  graph.nodes.forEach((n, i) => {
    if (!levels.has(n.id)) levels.set(n.id, i)
  })

  const byLevel = new Map<number, FlowchartNode[]>()
  graph.nodes.forEach((n) => {
    const lv = levels.get(n.id) || 0
    const list = byLevel.get(lv) || []
    list.push(n)
    byLevel.set(lv, list)
  })

  const nodes = graph.nodes.map((n) => {
    if (typeof n.x === 'number' && typeof n.y === 'number') return n
    const lv = levels.get(n.id) || 0
    const row = byLevel.get(lv) || [n]
    const idx = row.findIndex((x) => x.id === n.id)
    const count = row.length
    const x = 120 + idx * 220 - ((count - 1) * 220) / 2 + 280
    const y = 40 + lv * 120
    return { ...n, x, y }
  })

  return { nodes, edges: graph.edges }
}

export function flowchartToMermaid(doc: FlowchartPayload): string {
  const lines = ['flowchart TD']
  for (const n of doc.nodes) {
    const label = n.label.replace(/"/g, "'")
    if (n.type === 'start' || n.type === 'end') {
      lines.push(`  ${n.id}(["${label}"])`)
    } else if (n.type === 'decision') {
      lines.push(`  ${n.id}{"${label}"}`)
    } else if (n.type === 'io') {
      lines.push(`  ${n.id}[/"${label}"/]`)
    } else {
      lines.push(`  ${n.id}["${label}"]`)
    }
  }
  for (const e of doc.edges) {
    if (e.label) {
      lines.push(`  ${e.source} -->|"${e.label.replace(/"/g, "'")}"| ${e.target}`)
    } else {
      lines.push(`  ${e.source} --> ${e.target}`)
    }
  }
  return lines.join('\n')
}

export const FLOWCHART_SYSTEM_PROMPT = `你是「智流」流程图助手。根据用户描述和/或文档内容，输出可渲染的流程图数据结构。

硬性要求：
1. 只输出一个 JSON 对象，不要 Markdown 解释、不要代码围栏外的文字
2. JSON 字段：
{
  "title": "短标题",
  "nodes": [{ "id": "n1", "label": "节点文案", "type": "start|process|decision|io|end" }],
  "edges": [{ "id": "e1", "source": "n1", "target": "n2", "label": "可选" }]
}
3. nodes 至少 3 个；必须有合理的 start 与 end（或首尾节点）
4. id 用简短英文/拼音数字，edges 的 source/target 必须引用已有 id
5. label 简体中文，尽量短（≤16 字）
6. 决策节点 type=decision，分支边可带「是/否」等 label
7. 信息不足时仍给出合理主流程，不要空 nodes`

export function buildFlowchartUserPrompt(opts: {
  topic: string
  fileText?: string
}): string {
  const topic = opts.topic.trim() || '根据材料整理业务流程'
  const parts = [
    `请生成流程图 JSON。`,
    `用户要求：\n${topic}`,
  ]
  if (opts.fileText?.trim()) {
    parts.push(
      `附件/文档内容（请据此抽取真实步骤，勿编造无关业务）：\n${opts.fileText.trim().slice(0, 18000)}`,
    )
  }
  return parts.join('\n\n')
}
