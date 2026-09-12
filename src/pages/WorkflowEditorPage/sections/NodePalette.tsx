import { memo } from 'react';
import { motion } from 'framer-motion';
import { CheckCircle2, Circle, Eye, Loader2, ShieldCheck, XCircle } from 'lucide-react';
import {
  NODE_META,
  type IWorkflowNode,
  type NodeStatus,
} from '@/lib/workflow-types';
import { Badge } from '@/components/ui/badge';

interface NodePaletteProps {
  models?: Record<string, string>;
  nodes?: IWorkflowNode[];
  selectedNodeId?: string | null;
  onSelectAgent?: (type: string) => void;
}

const statusIcon = (status: NodeStatus) => {
  switch (status) {
    case 'running':
      return <Loader2 className="size-3 animate-spin text-sky-400" />;
    case 'completed':
      return <CheckCircle2 className="size-3 text-emerald-400" />;
    case 'failed':
      return <XCircle className="size-3 text-red-400" />;
    default:
      return <Circle className="size-3 text-muted-foreground/45" />;
  }
};

const NodePalette = memo(function NodePalette({
  models = {},
  nodes = [],
  selectedNodeId = null,
  onSelectAgent,
}: NodePaletteProps) {
  return (
    <div className="pixel-agent-palette h-full flex flex-col">
      <div className="px-3 py-2.5 border-b border-border/50">
        <h3 className="text-sm font-display font-semibold flex items-center gap-2">
          <ShieldCheck className="size-3.5 text-primary" />
          WorkWings Agent
        </h3>
        <p className="text-[11px] text-muted-foreground mt-1 leading-snug">
          按 Agent 顺序编排，点击查看包含节点
        </p>
        <Badge
          variant="outline"
          className="mt-2 text-[10px] border-primary/30 text-primary"
        >
          <Eye className="size-3 mr-1" />
          只读
        </Badge>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {nodes.map((node, i) => {
          const meta = NODE_META[node.type];
          const model = node.config.model || models[node.id] || models[node.type] || 'Auto';
          const selected = node.id === selectedNodeId;
          return (
            <motion.button
              type="button"
              key={node.id}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: Math.min(i, 12) * 0.015, duration: 0.18 }}
              onClick={() => onSelectAgent?.(node.id)}
              className={`pixel-agent-row w-full text-left px-2 py-2 rounded-lg border transition-all ${
                selected
                  ? 'border-primary/55 bg-primary/10'
                  : 'border-transparent hover:border-border/80 hover:bg-accent/30'
              }`}
            >
              <div className="flex items-center gap-2">
                <div
                  className={`size-7 shrink-0 rounded-md bg-gradient-to-br ${meta.color} flex items-center justify-center text-sm`}
                >
                  {meta.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-1">
                    <span className="text-xs font-medium truncate">{node.label}</span>
                    {statusIcon(node.status)}
                  </div>
                  <div className="text-[10px] text-muted-foreground truncate font-mono">
                    {String(i + 1).padStart(2, '0')} · {model}
                  </div>
                </div>
              </div>
            </motion.button>
          );
        })}
      </div>
    </div>
  );
});

export default NodePalette;
