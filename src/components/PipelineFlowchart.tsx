import { memo } from 'react';
import { motion } from 'framer-motion';
import { CheckCircle2, Circle, Loader2, XCircle } from 'lucide-react';
import {
  NODE_META,
  PIPELINE_ORDER,
  STUDIO_PIPELINE_ORDER,
  type IWorkflowNode,
  type NodeStatus,
  type NodeType,
} from '@/lib/workflow-types';

interface PipelineFlowchartProps {
  nodes?: IWorkflowNode[];
  activeType?: NodeType | null;
  compact?: boolean;
  onStageClick?: (type: NodeType) => void;
  /** studio = 工作台五阶段；kernel = WorkWings 9 Agent */
  variant?: 'kernel' | 'studio';
}

const statusIcon = (status: NodeStatus) => {
  switch (status) {
    case 'running':
      return <Loader2 className="size-3.5 animate-spin text-sky-300" />;
    case 'completed':
      return <CheckCircle2 className="size-3.5 text-emerald-400" />;
    case 'failed':
      return <XCircle className="size-3.5 text-red-400" />;
    default:
      return <Circle className="size-3.5 text-muted-foreground/50" />;
  }
};

const PipelineFlowchart = memo(function PipelineFlowchart({
  nodes = [],
  activeType,
  compact = false,
  onStageClick,
  variant = 'kernel',
}: PipelineFlowchartProps) {
  const statusMap = new Map(nodes.map((n) => [n.type, n.status]));
  const order = variant === 'studio' ? STUDIO_PIPELINE_ORDER : PIPELINE_ORDER;

  return (
    <div className={`pixel-pipeline w-full ${compact ? 'py-2' : 'py-4'}`}>
      <div className="relative flex items-stretch gap-0 overflow-x-auto pb-2">
        {order.map((type, index) => {
          const meta = NODE_META[type];
          const status = statusMap.get(type) ?? 'waiting';
          const isActive = activeType === type || status === 'running';
          const isDone = status === 'completed';
          const isFailed = status === 'failed';

          return (
            <div key={type} className="flex items-center min-w-0">
              <motion.button
                type="button"
                whileHover={{ y: -2 }}
                onClick={() => onStageClick?.(type)}
                className={`pixel-pipeline__step relative flex flex-col items-start gap-1.5 rounded-xl border px-3 py-2.5 text-left transition-all min-w-[128px] ${
                  isFailed
                    ? 'border-red-500/50 bg-red-500/5'
                    : isActive
                      ? 'border-primary/60 bg-primary/10 glow-ring'
                      : isDone
                        ? 'border-emerald-500/35 bg-emerald-500/5'
                        : 'border-border/70 bg-card/40 hover:border-primary/35'
                }`}
              >
                <div className="flex w-full items-center justify-between gap-2">
                  <span className="text-[10px] font-mono text-muted-foreground">
                    {meta.stage}
                  </span>
                  {statusIcon(status)}
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-base leading-none">{meta.icon}</span>
                  <span className="text-xs font-semibold">{meta.label}</span>
                </div>
                {!compact && (
                  <p className="text-[10px] text-muted-foreground leading-snug line-clamp-2">
                    {meta.description}
                  </p>
                )}
                {status === 'running' && (
                  <div className="absolute inset-x-2 bottom-1 h-0.5 overflow-hidden rounded-full bg-primary/20">
                    <div className="h-full w-1/2 animate-shimmer rounded-full bg-gradient-to-r from-transparent via-primary to-transparent bg-[length:200%_100%]" />
                  </div>
                )}
              </motion.button>

              {index < order.length - 1 && (
                <div className="pixel-pipeline__connector mx-1 flex w-8 shrink-0 items-center">
                  <svg width="32" height="12" className="overflow-visible">
                    <defs>
                      <linearGradient id={`flow-${type}`} x1="0" y1="0" x2="1" y2="0">
                        <stop offset="0%" stopColor="hsl(211 90% 48%)" stopOpacity="0.25" />
                        <stop offset="100%" stopColor="hsl(199 85% 45%)" stopOpacity="0.95" />
                      </linearGradient>
                    </defs>
                    <path
                      d="M0 6 H28"
                      stroke={`url(#flow-${type})`}
                      strokeWidth="2"
                      strokeDasharray={isDone || isActive ? '5 3' : '2 4'}
                      className={isActive ? 'animate-[dashflow_1s_linear_infinite]' : ''}
                      fill="none"
                    />
                    <polygon
                      points="28,3 32,6 28,9"
                      fill={isDone || isActive ? 'hsl(199 85% 45%)' : 'hsl(214 18% 75%)'}
                    />
                  </svg>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
});

export default PipelineFlowchart;
