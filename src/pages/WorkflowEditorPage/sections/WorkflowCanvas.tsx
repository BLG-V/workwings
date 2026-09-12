import { useState, useCallback, useRef, useEffect, memo } from 'react';
import { motion } from 'framer-motion';
import {
  ZoomIn,
  ZoomOut,
  Maximize2,
  Grid3X3,
  X,
} from 'lucide-react';
import {
  NODE_META,
  type IWorkflowNode,
  type IWorkflowEdge,
  type NodeType,
  type NodeStatus,
} from '@/lib/workflow-types';
import { labelErrorCategory } from '@/lib/run-labels';
import type { WorkWingsAgentGroup } from '@/integrations/workwings/mappers';

interface WorkflowCanvasProps {
  nodes: IWorkflowNode[];
  edges: IWorkflowEdge[];
  zoom: number;
  pan: { x: number; y: number };
  selectedNodeId: string | null;
  onNodesChange: (nodes: IWorkflowNode[]) => void;
  onEdgesChange: (edges: IWorkflowEdge[]) => void;
  onPanChange: (pan: { x: number; y: number }) => void;
  onZoomChange: (zoom: number) => void;
  onSelectNode: (id: string | null) => void;
  onDeleteNode: (id: string) => void;
  onAddNode: (type: NodeType, position: { x: number; y: number }) => void;
  /** WorkWings 真实工作流只读：禁止拖节点、连线、删除 */
  readOnly?: boolean;
  errorCategory?: string | null;
  /** 从 Runs 跳入时，把目标节点移到视口中心 */
  focusNonce?: number;
  /** WorkWings Agent 聚合视图：选中 Agent 后展示其包含的真实节点 */
  agentGroups?: WorkWingsAgentGroup[];
}

const NODE_WIDTH = 250;
const NODE_HEADER_Y = 36;

const statusDotClass: Record<NodeStatus, string> = {
  waiting: 'bg-muted-foreground/40',
  running: 'bg-blue-400 animate-pulse shadow-[0_0_8px_rgba(59_130_246_0.8)]',
  completed: 'bg-emerald-400 shadow-[0_0_6px_rgba(52_211_153_0.6)]',
  failed: 'bg-red-400 shadow-[0_0_6px_rgba(248_113_113_0.6)]',
};

const WorkflowCanvas = memo(function WorkflowCanvas({
  nodes,
  edges,
  zoom,
  pan,
  selectedNodeId,
  onNodesChange,
  onEdgesChange,
  onPanChange,
  onZoomChange,
  onSelectNode,
  onDeleteNode,
  onAddNode,
  readOnly = false,
  errorCategory = null,
  focusNonce = 0,
  agentGroups = [],
}: WorkflowCanvasProps) {
  const canvasRef = useRef<HTMLDivElement>(null);
  const [isPanning, setIsPanning] = useState(false);
  const panStartRef = useRef({ x: 0, y: 0, panX: 0, panY: 0 });
  const [draggingNode, setDraggingNode] = useState<string | null>(null);
  const dragOffsetRef = useRef({ x: 0, y: 0 });
  const [connecting, setConnecting] = useState<{
    sourceId: string;
    startX: number;
    startY: number;
    endX: number;
    endY: number;
  } | null>(null);

  // 滚轮缩放
  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      e.preventDefault();
      const delta = e.deltaY > 0 ? -0.1 : 0.1;
      const newZoom = Math.min(Math.max(zoom + delta, 0.3), 2);
      onZoomChange(newZoom);
    },
    [zoom, onZoomChange],
  );

  // 画布平移（拖拽空白区）
  const handleCanvasMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (e.button !== 0) return;
      const target = e.target as HTMLElement;
      if (target.closest('[data-node]')) return;
      if (target.closest('[data-edge]')) return;
      setIsPanning(true);
      panStartRef.current = {
        x: e.clientX,
        y: e.clientY,
        panX: pan.x,
        panY: pan.y,
      };
      onSelectNode(null);
    },
    [pan, onSelectNode],
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (isPanning) {
        const dx = e.clientX - panStartRef.current.x;
        const dy = e.clientY - panStartRef.current.y;
        onPanChange({
          x: panStartRef.current.panX + dx,
          y: panStartRef.current.panY + dy,
        });
        return;
      }
      if (draggingNode) {
        const rect = canvasRef.current?.getBoundingClientRect();
        if (!rect) return;
        const x = (e.clientX - rect.left - pan.x) / zoom - dragOffsetRef.current.x;
        const y = (e.clientY - rect.top - pan.y) / zoom - dragOffsetRef.current.y;
        onNodesChange(
          nodes.map((n) =>
            n.id === draggingNode ? { ...n, position: { x, y } } : n,
          ),
        );
      }
      if (connecting) {
        const rect = canvasRef.current?.getBoundingClientRect();
        if (!rect) return;
        setConnecting({
          ...connecting,
          endX: (e.clientX - rect.left - pan.x) / zoom,
          endY: (e.clientY - rect.top - pan.y) / zoom,
        });
      }
    },
    [isPanning, draggingNode, connecting, pan, zoom, nodes, onPanChange, onNodesChange],
  );

  const handleMouseUp = useCallback(() => {
    setIsPanning(false);
    setDraggingNode(null);
    if (connecting) {
      setConnecting(null);
    }
  }, [connecting]);

  // 节点拖拽开始
  const handleNodeMouseDown = useCallback(
    (e: React.MouseEvent, nodeId: string) => {
      e.stopPropagation();
      const node = nodes.find((n) => n.id === nodeId);
      if (!node) return;
      onSelectNode(nodeId);
      if (readOnly) return;
      const rect = canvasRef.current?.getBoundingClientRect();
      if (!rect) return;
      const mouseX = (e.clientX - rect.left - pan.x) / zoom;
      const mouseY = (e.clientY - rect.top - pan.y) / zoom;
      dragOffsetRef.current = {
        x: mouseX - node.position.x,
        y: mouseY - node.position.y,
      };
      setDraggingNode(nodeId);
    },
    [nodes, pan, zoom, onSelectNode, readOnly],
  );

  // 开始连线
  const handleConnectStart = useCallback(
    (e: React.MouseEvent, nodeId: string) => {
      e.stopPropagation();
      if (readOnly) return;
      const node = nodes.find((n) => n.id === nodeId);
      if (!node) return;
      setConnecting({
        sourceId: nodeId,
        startX: node.position.x + NODE_WIDTH,
        startY: node.position.y + NODE_HEADER_Y,
        endX: node.position.x + NODE_WIDTH,
        endY: node.position.y + NODE_HEADER_Y,
      });
    },
    [nodes, readOnly],
  );

  // 结束连线（放到目标节点左侧）
  const handleConnectEnd = useCallback(
    (e: React.MouseEvent, targetId: string) => {
      e.stopPropagation();
      if (connecting && connecting.sourceId !== targetId) {
        const exists = edges.some(
          (edge) =>
            edge.source === connecting.sourceId && edge.target === targetId,
        );
        if (!exists) {
          onEdgesChange([
            ...edges,
            {
              id: `e-${connecting.sourceId}-${targetId}`,
              source: connecting.sourceId,
              target: targetId,
            },
          ]);
        }
      }
      setConnecting(null);
    },
    [connecting, edges, onEdgesChange],
  );

  // 删除键删除节点
  useEffect(() => {
    if (readOnly) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Delete' || e.key === 'Backspace') {
        if (selectedNodeId && document.activeElement?.tagName !== 'INPUT' && document.activeElement?.tagName !== 'TEXTAREA') {
          onDeleteNode(selectedNodeId);
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedNodeId, onDeleteNode, readOnly]);

  useEffect(() => {
    if (!focusNonce || !selectedNodeId) return;
    const node = nodes.find((n) => n.id === selectedNodeId);
    const el = canvasRef.current;
    if (!node || !el) return;
    const rect = el.getBoundingClientRect();
    onPanChange({
      x: Math.round(rect.width / 2 - (node.position.x + NODE_WIDTH / 2) * zoom),
      y: Math.round(rect.height / 2 - (node.position.y + 56) * zoom),
    });
  }, [focusNonce]);

  // 拖放节点到画布
  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      if (readOnly) return;
      const nodeType = e.dataTransfer.getData('nodeType') as NodeType;
      if (!nodeType) return;
      const rect = canvasRef.current?.getBoundingClientRect();
      if (!rect) return;
      const x = (e.clientX - rect.left - pan.x) / zoom - NODE_WIDTH / 2;
      const y = (e.clientY - rect.top - pan.y) / zoom - 32;
      onAddNode(nodeType, { x, y });
    },
    [pan, zoom, onAddNode, readOnly],
  );

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  // 计算贝塞尔曲线路径
  const getBezierPath = (
    sx: number,
    sy: number,
    tx: number,
    ty: number,
  ) => {
    const dx = Math.abs(tx - sx) * 0.5;
    return `M ${sx} ${sy} C ${sx + dx} ${sy}, ${tx - dx} ${ty}, ${tx} ${ty}`;
  };

  const handleZoomIn = () => onZoomChange(Math.min(zoom + 0.1, 2));
  const handleZoomOut = () => onZoomChange(Math.max(zoom - 0.1, 0.3));
  const handleFitView = () => {
    onZoomChange(1);
    onPanChange({ x: 0, y: 0 });
  };

  return (
    <div
      ref={canvasRef}
      className="pixel-workflow-canvas relative w-full h-full overflow-hidden cursor-grab active:cursor-grabbing select-none"
      onMouseDown={handleCanvasMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onWheel={handleWheel}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
    >
      {/* 网格背景 */}
      <div
        className="absolute inset-0 opacity-30"
        style={{
          backgroundImage:
            'radial-gradient(circle, hsl(214 24% 82%) 1px, transparent 1px)',
          backgroundSize: `${20 * zoom}px ${20 * zoom}px`,
          backgroundPosition: `${pan.x}px ${pan.y}px`,
        }}
      />

      {/* 画布内容层 */}
      <div
        className="absolute top-0 left-0 origin-top-left"
        style={{
          transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
        }}
      >
        {/* SVG 连线层 */}
        <svg
          className="absolute top-0 left-0 overflow-visible pointer-events-none"
          style={{ width: 5000, height: 4000 }}
        >
          <defs>
            <marker
              id="arrowhead"
              markerWidth="10"
              markerHeight="7"
              refX="9"
              refY="3.5"
              orient="auto"
            >
              <polygon points="0 0, 10 3.5, 0 7" fill="hsl(211 90% 48%)" />
            </marker>
            <marker
              id="arrowhead-active"
              markerWidth="10"
              markerHeight="7"
              refX="9"
              refY="3.5"
              orient="auto"
            >
              <polygon points="0 0, 10 3.5, 0 7" fill="hsl(199 85% 45%)" />
            </marker>
          </defs>
          {edges.map((edge) => {
            const source = nodes.find((n) => n.id === edge.source);
            const target = nodes.find((n) => n.id === edge.target);
            if (!source || !target) return null;
            const sx = source.position.x + NODE_WIDTH;
            const sy = source.position.y + NODE_HEADER_Y;
            const tx = target.position.x;
            const ty = target.position.y + NODE_HEADER_Y;
            const isActive =
              source.status === 'running' ||
              source.status === 'completed' ||
              target.status === 'running';
            return (
              <g key={edge.id} data-edge>
                <path
                  d={getBezierPath(sx, sy, tx, ty)}
                  fill="none"
                  stroke={isActive ? 'hsl(199 85% 45%)' : 'hsl(211 90% 48%)'}
                  strokeWidth="2"
                  strokeDasharray={
                    source.status === 'running' || target.status === 'running'
                      ? '8 4'
                      : 'none'
                  }
                  markerEnd={isActive ? 'url(#arrowhead-active)' : 'url(#arrowhead)'}
                  className={
                    source.status === 'running' || target.status === 'running'
                      ? 'animate-[dashflow_1s_linear_infinite]'
                      : ''
                  }
                  opacity={source.status === 'waiting' && target.status === 'waiting' ? 0.45 : 1}
                />
              </g>
            );
          })}
          {connecting && (
            <path
              d={getBezierPath(
                connecting.startX,
                connecting.startY,
                connecting.endX,
                connecting.endY,
              )}
              fill="none"
              stroke="hsl(211 90% 48%)"
              strokeWidth="2"
              strokeDasharray="6 4"
            />
          )}
        </svg>

        {/* 节点层 */}
        {nodes.map((node) => {
          const meta = NODE_META[node.type];
          const isSelected = selectedNodeId === node.id;
          const isRunning = node.status === 'running';
          const agentGroup = agentGroups.find(
            (group) => group.type === node.id || group.type === node.type,
          );
          return (
            <motion.div
              key={node.id}
              data-node
              layout
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              transition={{ duration: 0.15 }}
              className={`pixel-workflow-node absolute w-[250px] rounded-xl border-2 bg-card/95 backdrop-blur-sm transition-shadow ${
                readOnly ? 'cursor-pointer' : 'cursor-move'
              } ${
                isSelected && node.status === 'failed'
                  ? 'border-red-500 glow-ring shadow-[0_0_18px_hsl(0_84%_60%_/_0.4)]'
                  : isSelected
                    ? 'border-primary glow-ring'
                    : isRunning
                      ? 'border-sky-400/80 shadow-[0_0_18px_hsl(195_90%_55%_/_0.35)]'
                      : node.status === 'completed'
                        ? 'border-emerald-500/50'
                        : node.status === 'failed'
                          ? 'border-red-500/50'
                          : 'border-border hover:border-primary/50'
              }`}
              style={{
                left: node.position.x,
                top: node.position.y,
              }}
              onMouseDown={(e) => handleNodeMouseDown(e, node.id)}
              onMouseUp={(e) => handleConnectEnd(e, node.id)}
            >
              {/* 节点头部 */}
              <div
                className={`pixel-workflow-node__header flex items-center gap-2 px-3 py-2 rounded-t-md bg-gradient-to-r ${meta.color} text-white`}
              >
                <span className="text-base">{meta.icon}</span>
                <span className="flex-1 text-sm font-medium truncate">
                  {node.label}
                </span>
                <div className={`size-2.5 rounded-full ${statusDotClass[node.status]} shrink-0`} />
              </div>
              {/* 节点内容 */}
              <div className="px-3 py-2 space-y-1">
                <div className="text-[10px] text-muted-foreground">
                  {node.config.prompt || NODE_META[node.type].description}
                </div>
                <div className="text-xs font-mono text-foreground/80">
                  {node.config.model}
                </div>
                {isSelected && agentGroup ? (
                  <div className="mt-2 rounded-lg border border-border/70 bg-background/55 p-2">
                    <div className="mb-1.5 flex items-center justify-between text-[10px] text-muted-foreground">
                      <span>包含节点</span>
                      <span>{agentGroup.nodes.length}</span>
                    </div>
                    <div className="space-y-1">
                      {agentGroup.nodes.map((child) => (
                        <div
                          key={child.id}
                          className="flex items-center gap-1.5 rounded-md bg-card/60 px-2 py-1 text-[10px]"
                        >
                          <span className={`size-1.5 shrink-0 rounded-full ${statusDotClass[child.status]}`} />
                          <span className="min-w-0 flex-1 truncate">{child.label}</span>
                          <span className="shrink-0 font-mono text-muted-foreground">{child.id}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
                {node.status === 'failed' && errorCategory ? (
                  <span className="inline-flex max-w-full items-center rounded border border-red-500/40 bg-red-500/10 px-1.5 py-0.5 text-[10px] text-red-400 truncate">
                    {labelErrorCategory(errorCategory)}
                  </span>
                ) : null}
              </div>
              {/* 删除按钮 */}
              {isSelected && !readOnly && (
                <button
                  className="!absolute -top-2.5 -right-2.5 z-20 size-6 rounded-full bg-card border border-border flex items-center justify-center hover:bg-destructive hover:text-destructive-foreground transition-colors"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteNode(node.id);
                  }}
                >
                  <X className="size-3.5" />
                </button>
              )}
              {/* 左侧输入连接点 */}
              {!readOnly ? (
                <div
                  className="absolute -left-2 top-1/2 -translate-y-1/2 size-4 rounded-full bg-card border-2 border-primary cursor-crosshair hover:scale-125 transition-transform"
                  onMouseUp={(e) => handleConnectEnd(e, node.id)}
                />
              ) : null}
              {/* 右侧输出连接点 */}
              {!readOnly ? (
                <div
                  className="absolute -right-2 top-1/2 -translate-y-1/2 size-4 rounded-full bg-primary border-2 border-primary cursor-crosshair hover:scale-125 transition-transform"
                  onMouseDown={(e) => handleConnectStart(e, node.id)}
                />
              ) : null}
            </motion.div>
          );
        })}
      </div>

      {/* 缩放控件 */}
      <div className="absolute bottom-4 right-4 flex items-center gap-1 p-1.5 rounded-md bg-card/90 backdrop-blur-sm border border-border">
        <button
          onClick={handleZoomOut}
          className="p-1.5 rounded hover:bg-accent transition-colors"
          title="缩小"
        >
          <ZoomOut className="size-4" />
        </button>
        <span className="text-xs tabular-nums w-12 text-center text-muted-foreground">
          {Math.round(zoom * 100)}%
        </span>
        <button
          onClick={handleZoomIn}
          className="p-1.5 rounded hover:bg-accent transition-colors"
          title="放大"
        >
          <ZoomIn className="size-4" />
        </button>
        <button
          onClick={handleFitView}
          className="p-1.5 rounded hover:bg-accent transition-colors"
          title="适应视图"
        >
          <Maximize2 className="size-4" />
        </button>
      </div>

      {/* 空状态提示 */}
      {nodes.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="text-center">
            <Grid3X3 className="size-12 mx-auto text-muted-foreground/30 mb-3" />
            <p className="text-sm text-muted-foreground">
              {readOnly
                ? '正在载入 WorkWings 工作流节点…'
                : '从左侧面板拖拽 Agent 节点到此处'}
            </p>
            {!readOnly ? (
              <p className="text-xs text-muted-foreground/70 mt-1">
                或点击左侧节点快速添加
              </p>
            ) : null}
          </div>
        </div>
      )}

      {/* dashflow animation */}
      <style>{`
        @keyframes dashflow {
          from { stroke-dashoffset: 12; }
          to { stroke-dashoffset: 0; }
        }
      `}</style>
    </div>
  );
});

export default WorkflowCanvas;
