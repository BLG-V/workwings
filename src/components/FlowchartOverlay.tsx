import { useCallback, useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  addEdge,
  Background,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Connection,
  type Edge,
  type Node,
  type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Plus, Trash2, X } from 'lucide-react'
import type { FlowchartPayload, FlowNodeType } from '@/lib/flowchart'
import { layoutFlowchart } from '@/lib/flowchart'
import FlowchartExportMenu from '@/components/FlowchartExportMenu'
import { cn } from '@/lib/utils'

function FlowNodeView({ data, selected }: NodeProps) {
  const kind = (data.kind as FlowNodeType) || 'process'
  const label = String(data.label || '')
  return (
    <div
      className={cn(
        'min-w-[120px] max-w-[200px] rounded-xl border px-3 py-2 text-center text-[13px] shadow-sm',
        selected ? 'border-primary ring-2 ring-primary/20' : 'border-border',
        kind === 'start' || kind === 'end'
          ? 'rounded-full bg-emerald-50'
          : kind === 'decision'
            ? 'rounded-lg bg-amber-50'
            : kind === 'io'
              ? 'bg-sky-50'
              : 'bg-white',
      )}
    >
      <Handle type="target" position={Position.Top} className="!bg-primary" />
      <div className="font-medium leading-snug">{label}</div>
      <div className="mt-0.5 text-[10px] text-muted-foreground">{kind}</div>
      <Handle type="source" position={Position.Bottom} className="!bg-primary" />
    </div>
  )
}

const nodeTypes = { flow: FlowNodeView }

function toRf(doc: FlowchartPayload): { nodes: Node[]; edges: Edge[] } {
  const laid = layoutFlowchart({ nodes: doc.nodes, edges: doc.edges })
  return {
    nodes: laid.nodes.map((n) => ({
      id: n.id,
      type: 'flow',
      position: { x: n.x ?? 0, y: n.y ?? 0 },
      data: { label: n.label, kind: n.type },
    })),
    edges: laid.edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      label: e.label,
      animated: false,
    })),
  }
}

function fromRf(
  title: string,
  createdAt: string,
  nodes: Node[],
  edges: Edge[],
  sourceHint?: string,
): FlowchartPayload {
  return {
    title,
    createdAt,
    sourceHint,
    nodes: nodes.map((n) => ({
      id: n.id,
      label: String(n.data?.label || n.id),
      type: (n.data?.kind as FlowNodeType) || 'process',
      x: n.position.x,
      y: n.position.y,
    })),
    edges: edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      label: e.label ? String(e.label) : undefined,
    })),
  }
}

type FlowchartOverlayProps = {
  open: boolean
  initial: FlowchartPayload | null
  onClose: (doc: FlowchartPayload | null) => void
  onChange?: (doc: FlowchartPayload) => void
}

export default function FlowchartOverlay({
  open,
  initial,
  onClose,
  onChange,
}: FlowchartOverlayProps) {
  const seed = useMemo(
    () => (initial ? toRf(initial) : { nodes: [], edges: [] }),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 仅打开时灌入
    [open, initial?.createdAt, initial?.title],
  )
  const [title, setTitle] = useState(initial?.title || '流程图')
  const [nodes, setNodes, onNodesChange] = useNodesState(seed.nodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(seed.edges)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  useEffect(() => {
    if (!open || !initial) return
    const next = toRf(initial)
    setTitle(initial.title)
    setNodes(next.nodes)
    setEdges(next.edges)
    setSelectedId(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, initial?.createdAt, initial?.title])

  const snapshot = useCallback(() => {
    return fromRf(
      title,
      initial?.createdAt || new Date().toISOString(),
      nodes,
      edges,
      initial?.sourceHint,
    )
  }, [title, initial?.createdAt, initial?.sourceHint, nodes, edges])

  const onConnect = useCallback(
    (c: Connection) => setEdges((eds) => addEdge({ ...c, id: `e-${Date.now()}` }, eds)),
    [setEdges],
  )

  const addNode = (type: FlowNodeType) => {
    const id = `n${Date.now().toString(36)}`
    setNodes((prev) => [
      ...prev,
      {
        id,
        type: 'flow',
        position: { x: 180 + (prev.length % 3) * 40, y: 80 + prev.length * 24 },
        data: {
          label: type === 'decision' ? '是否通过？' : type === 'end' ? '结束' : '新步骤',
          kind: type,
        },
      },
    ])
  }

  const selected = nodes.find((n) => n.id === selectedId)

  const renameSelected = (label: string) => {
    if (!selectedId) return
    setNodes((prev) =>
      prev.map((n) =>
        n.id === selectedId ? { ...n, data: { ...n.data, label } } : n,
      ),
    )
  }

  const removeSelected = () => {
    if (!selectedId) return
    setNodes((prev) => prev.filter((n) => n.id !== selectedId))
    setEdges((prev) =>
      prev.filter((e) => e.source !== selectedId && e.target !== selectedId),
    )
    setSelectedId(null)
  }

  if (!open) return null

  const liveDoc = snapshot()

  return createPortal(
    <div className="fixed inset-0 z-[80] flex items-stretch justify-center bg-black/45 p-0 md:p-4">
      <div className="relative flex h-full w-full max-w-6xl flex-col overflow-hidden bg-[#f7f8fa] shadow-2xl md:rounded-2xl">
        <header className="flex items-center gap-2 border-b border-black/5 bg-white px-3 py-2.5">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="min-w-0 flex-1 bg-transparent text-[15px] font-medium outline-none"
          />
          <button
            type="button"
            className="inline-flex items-center gap-1 rounded-lg px-2 py-1.5 text-[12px] text-[#5c6370] hover:bg-black/5 pressable"
            onClick={() => addNode('process')}
          >
            <Plus className="size-3.5" />
            步骤
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-1 rounded-lg px-2 py-1.5 text-[12px] text-[#5c6370] hover:bg-black/5 pressable"
            onClick={() => addNode('decision')}
          >
            <Plus className="size-3.5" />
            判断
          </button>
          <FlowchartExportMenu doc={liveDoc} />
          <button
            type="button"
            title="关闭"
            onClick={() => onClose(snapshot())}
            className="inline-flex size-8 items-center justify-center rounded-lg text-[#5c6370] hover:bg-black/5 pressable"
          >
            <X className="size-4" />
          </button>
        </header>

        <div className="flex min-h-0 flex-1">
          <div className="min-w-0 flex-1">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              nodeTypes={nodeTypes}
              fitView
              onNodeClick={(_, n) => setSelectedId(n.id)}
              onPaneClick={() => setSelectedId(null)}
            >
              <Background gap={18} size={1} />
              <Controls />
              <MiniMap pannable zoomable />
            </ReactFlow>
          </div>
          <aside className="hidden w-56 shrink-0 border-l border-black/5 bg-white p-3 md:block">
            <div className="text-[12px] font-medium text-muted-foreground">节点属性</div>
            {selected ? (
              <div className="mt-3 space-y-3">
                <label className="block text-[12px]">
                  文案
                  <input
                    className="mt-1 w-full rounded-md border border-border px-2 py-1.5 text-[13px] outline-none focus:border-primary"
                    value={String(selected.data?.label || '')}
                    onChange={(e) => renameSelected(e.target.value)}
                  />
                </label>
                <button
                  type="button"
                  onClick={removeSelected}
                  className="inline-flex w-full items-center justify-center gap-1 rounded-md border border-destructive/30 px-2 py-1.5 text-[12px] text-destructive hover:bg-destructive/5 pressable"
                >
                  <Trash2 className="size-3.5" />
                  删除节点
                </button>
              </div>
            ) : (
              <p className="mt-3 text-[12px] leading-relaxed text-muted-foreground">
                点击节点可改文案；拖拽连线可加边。顶部「导出」支持 PNG / SVG / PDF / Draw.io / Mermaid / JSON。
              </p>
            )}
            <div className="mt-4">
              <FlowchartExportMenu doc={liveDoc} align="left" className="w-full [&_button]:w-full [&_button]:justify-between" />
            </div>
          </aside>
        </div>
      </div>
    </div>,
    document.body,
  )
}
