import { memo } from 'react';
import {
  Settings,
  Cpu,
  FileInput,
  FileOutput,
  Eye,
  AlertCircle,
  ExternalLink,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import type { IWorkflowNode } from '@/lib/workflow-types';
import { NODE_META } from '@/lib/workflow-types';
import type { RunObserve } from '@/lib/mawp-api';
import { formatCnyLite, formatTok, labelErrorCategory } from '@/lib/run-labels';
import { canvasNodeKey } from '@/lib/pipeline';

interface PropertyPanelProps {
  node: IWorkflowNode | null;
  containedNodes?: IWorkflowNode[];
  observe?: RunObserve | null;
  runError?: string | null;
  onOpenRuns?: () => void;
}

const PropertyPanel = memo(function PropertyPanel({
  node,
  containedNodes = [],
  observe,
  runError,
  onOpenRuns,
}: PropertyPanelProps) {
  if (!node) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-4 text-center">
        <div className="size-12 rounded-full bg-accent/50 flex items-center justify-center mb-3">
          <Settings className="size-6 text-muted-foreground" />
        </div>
        <h3 className="text-sm font-medium mb-1">未选中 Agent</h3>
        <p className="text-xs text-muted-foreground leading-relaxed">
          点击 WorkWings Agent，查看模型、包含节点与执行原因
        </p>
      </div>
    );
  }

  const meta = NODE_META[node.type];
  const nodeDescription = node.config.prompt || meta.description;
  const statusLabel = {
    waiting: '等待中',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
  }[node.status];

  const statusColor = {
    waiting: 'bg-muted text-muted-foreground',
    running: 'bg-sky-500/20 text-sky-300',
    completed: 'bg-emerald-500/20 text-emerald-300',
    failed: 'bg-red-500/20 text-red-300',
  }[node.status];

  const agentUsage = observe?.usage?.by_agent?.find(
    (a) => canvasNodeKey(a.agent) === node.type || a.agent === node.id,
  );
  const nodeObs = observe?.nodes?.find(
    (n) => canvasNodeKey(n.node_id) === node.type || n.node_id === node.id,
  );
  const cat = observe?.error_category;
  const showFail = node.status === 'failed';

  return (
    <div className="pixel-property-panel h-full flex flex-col">
      <div className="px-4 py-3 border-b border-border/50">
        <div className="flex items-center gap-2.5 mb-2">
          <div
            className={`size-9 shrink-0 rounded-lg bg-gradient-to-br ${meta.color} flex items-center justify-center text-lg`}
          >
            {meta.icon}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium truncate">{node.label}</div>
            <div className="text-[11px] font-mono text-muted-foreground">{node.type}</div>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className={statusColor}>
            {statusLabel}
          </Badge>
          <Badge variant="outline" className="text-xs">
            {meta.stage} · {meta.label}
          </Badge>
          {node.status === 'failed' && cat ? (
            <Badge variant="outline" className="text-[10px] border-red-500/40 text-red-400">
              {labelErrorCategory(cat)}
            </Badge>
          ) : null}
          <Badge
            variant="outline"
            className="text-[10px] border-primary/30 text-primary"
          >
            <Eye className="size-3 mr-1" />
            只读
          </Badge>
        </div>
        <p className="text-[11px] text-muted-foreground mt-2">{nodeDescription}</p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {showFail ? (
          <div className="rounded-lg border border-red-500/30 bg-red-500/5 px-3 py-2.5 space-y-1.5">
            <div className="flex items-center gap-1.5 text-xs text-red-400">
              <AlertCircle className="size-3.5" />
              {cat ? labelErrorCategory(cat) : '失败'}
            </div>
            {runError ? (
              <p className="text-[11px] text-muted-foreground break-all leading-relaxed">
                {runError.slice(0, 280)}
              </p>
            ) : null}
          </div>
        ) : null}

        <div className="space-y-2">
          <Label className="text-xs flex items-center gap-1.5">
            <Cpu className="size-3.5" />
            WorkWings 模型（实时配置）
          </Label>
          <div className="rounded-lg border border-border/70 bg-background/50 px-3 py-2 text-sm font-mono">
            {nodeObs?.model || node.config.model || '—'}
          </div>
        </div>

        {containedNodes.length > 0 ? (
          <div className="space-y-2">
            <Label className="text-xs flex items-center gap-1.5">
              <Settings className="size-3.5" />
              包含节点
            </Label>
            <div className="rounded-lg border border-border/70 bg-background/50 p-2 space-y-1">
              {containedNodes.map((item) => (
                <div
                  key={item.id}
                  className="flex items-center justify-between gap-2 rounded-md px-2 py-1 text-[11px]"
                >
                  <span className="min-w-0 truncate">{item.label}</span>
                  <Badge variant="outline" className="shrink-0 text-[10px]">
                    {item.status === 'completed' && '已完成'}
                    {item.status === 'running' && '运行中'}
                    {item.status === 'failed' && '失败'}
                    {item.status === 'waiting' && '等待中'}
                  </Badge>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        <div className="grid grid-cols-2 gap-2 text-[11px]">
          <div className="rounded-lg border border-border/70 px-2.5 py-2">
            <div className="text-muted-foreground">本节点 Token</div>
            <div className="font-mono mt-0.5">
              {formatTok(agentUsage?.total_tokens ?? nodeObs?.total_tokens)}
            </div>
          </div>
          <div className="rounded-lg border border-border/70 px-2.5 py-2">
            <div className="text-muted-foreground">粗估成本</div>
            <div className="font-mono mt-0.5">
              {formatCnyLite(agentUsage?.cost_cny ?? nodeObs?.cost_cny)}
            </div>
          </div>
        </div>
        {observe?.usage?.total_tokens ? (
          <p className="text-[10px] text-muted-foreground">
            整次 Run {formatTok(observe.usage.total_tokens)} tok ·{' '}
            {formatCnyLite(observe.usage.cost_cny)}
          </p>
        ) : null}

        <div className="space-y-2">
          <Label className="text-xs flex items-center gap-1.5">
            <FileInput className="size-3.5" />
            上游
          </Label>
          <div className="rounded-lg border border-border/70 bg-background/50 px-3 py-2 text-xs font-mono text-muted-foreground">
            {node.config.inputSource}
          </div>
        </div>

        <div className="space-y-2">
          <Label className="text-xs flex items-center gap-1.5">
            <FileOutput className="size-3.5" />
            下游
          </Label>
          <div className="rounded-lg border border-border/70 bg-background/50 px-3 py-2 text-xs font-mono text-muted-foreground">
            {node.config.outputTarget}
          </div>
        </div>

        {onOpenRuns ? (
          <Button
            size="sm"
            variant="secondary"
            className="w-full h-8"
            onClick={onOpenRuns}
          >
            <ExternalLink className="size-3.5 mr-1.5" />
            去运行记录
          </Button>
        ) : null}
      </div>
    </div>
  );
});

export default PropertyPanel;
