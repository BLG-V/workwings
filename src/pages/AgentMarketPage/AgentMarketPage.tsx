import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Search, ShieldCheck, Eye, Workflow } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/components/ui/select';
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerDescription,
} from '@/components/ui/drawer';
import { listModels, probeMawp } from '@/lib/mawp-api';
import {
  fallbackKernelModels,
  KERNEL_AGENT_GROUPS,
  listKernelAgentGuides,
  type KernelAgentGuide,
  type KernelAgentId,
} from '@/lib/kernel-agents';
import { createProject, resolveWorkflowPath } from '@/lib/projects-store';

function openWorkflowAtAgent(
  navigate: ReturnType<typeof useNavigate>,
  type: KernelAgentId,
) {
  const path = resolveWorkflowPath();
  if (path) {
    navigate(path, { state: { selectAgent: type } });
    return;
  }
  const project = createProject({
    name: '未命名项目',
    description: '查看 WorkWings Agent 编排',
    goal: '',
  });
  navigate(`/workflow/${project.id}`, { state: { selectAgent: type } });
}

export default function AgentMarketPage() {
  const navigate = useNavigate();
  const [keyword, setKeyword] = useState('');
  const [group, setGroup] = useState('all');
  const [selected, setSelected] = useState<KernelAgentGuide | null>(null);
  const [models, setModels] = useState<Record<string, string>>(fallbackKernelModels);
  const [kernelOnline, setKernelOnline] = useState<boolean | null>(null);

  useEffect(() => {
    void (async () => {
      const health = await probeMawp();
      setKernelOnline(Boolean(health));
      if (!health) return;
      try {
        const { current } = await listModels();
        setModels({ ...fallbackKernelModels(), ...(current || {}) });
      } catch {
        /* 离线用默认模型标签 */
      }
    })();
  }, []);

  const guides = useMemo(() => listKernelAgentGuides(), []);

  const filtered = useMemo(() => {
    const allowed = KERNEL_AGENT_GROUPS.find((g) => g.value === group)?.types ?? [];
    const q = keyword.trim().toLowerCase();
    return guides.filter((a) => {
      if (group !== 'all' && !allowed.includes(a.type)) return false;
      if (!q) return true;
      return (
        a.label.toLowerCase().includes(q) ||
        a.type.includes(q) ||
        a.description.toLowerCase().includes(q) ||
        a.capabilities.some((c) => c.toLowerCase().includes(q))
      );
    });
  }, [guides, keyword, group]);

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-display font-bold tracking-tight">WorkWings Agent 编排</h1>
          <p className="text-sm text-muted-foreground mt-1">
            WorkWings 9 Agent 链从多模态分析到交付归档，模型按 Agent 配置路由，不能随意增删
          </p>
        </div>
        <div className="flex items-center gap-2">
          {kernelOnline != null ? (
            <Badge
              variant="outline"
              className={
                kernelOnline
                  ? 'border-emerald-500/30 text-emerald-600'
                  : 'border-amber-500/30 text-amber-700'
              }
            >
              {kernelOnline ? 'WorkWings 在线' : 'WorkWings 离线'}
            </Badge>
          ) : null}
          <Badge variant="outline" className="border-primary/30 text-primary">
            <Eye className="size-3 mr-1" />
            只读说明
          </Badge>
        </div>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1 max-w-md">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="搜索 Agent 名称或能力"
            className="pl-9"
          />
        </div>
        <Select value={group} onValueChange={setGroup}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="阶段筛选" />
          </SelectTrigger>
          <SelectContent>
            {KERNEL_AGENT_GROUPS.map((c) => (
              <SelectItem key={c.value} value={c.value}>
                {c.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div>
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3 flex items-center gap-2">
          <ShieldCheck className="size-4 text-primary" />
          WorkWings 9 Agent
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {filtered.map((agent, i) => (
            <motion.div
              key={agent.type}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.04 }}
            >
              <Card
                className="cursor-pointer hover:border-primary/50 transition-colors h-full pressable"
                onClick={() => setSelected(agent)}
              >
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    <div
                      className={`size-12 rounded-xl bg-gradient-to-br ${agent.color} flex items-center justify-center text-2xl shrink-0`}
                    >
                      {agent.icon}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold text-sm truncate">{agent.label}</h3>
                        <Badge variant="outline" className="text-[10px] shrink-0 font-mono">
                          {agent.stage}
                        </Badge>
                      </div>
                      <p className="text-[11px] font-mono text-muted-foreground mt-0.5 truncate">
                        {models[agent.type] || '—'}
                      </p>
                      <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                        {agent.description}
                      </p>
                      <div className="flex flex-wrap gap-1 mt-2">
                        {agent.capabilities.slice(0, 3).map((cap) => (
                          <span
                            key={cap}
                            className="text-[10px] px-1.5 py-0.5 rounded bg-accent text-muted-foreground"
                          >
                            {cap}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
        {filtered.length === 0 ? (
          <div className="rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground">
            没有匹配的 WorkWings Agent
          </div>
        ) : null}
      </div>

      <Drawer open={!!selected} onOpenChange={(o) => !o && setSelected(null)}>
        <DrawerContent className="max-w-2xl mx-auto">
          {selected ? (
            <div className="p-6">
              <DrawerHeader className="p-0 mb-4">
                <div className="flex items-start gap-4">
                  <div
                    className={`size-16 rounded-xl bg-gradient-to-br ${selected.color} flex items-center justify-center text-3xl shrink-0`}
                  >
                    {selected.icon}
                  </div>
                  <div className="flex-1">
                    <DrawerTitle className="text-xl">{selected.label}</DrawerTitle>
                    <DrawerDescription className="mt-1">
                      {selected.description}
                    </DrawerDescription>
                  </div>
                </div>
              </DrawerHeader>

              <div className="space-y-4">
                <div>
                  <h4 className="text-sm font-semibold mb-2">在链上的职责</h4>
                  <p className="text-sm text-muted-foreground">{selected.role}</p>
                </div>

                <div>
                  <h4 className="text-sm font-semibold mb-2">能力</h4>
                  <div className="flex flex-wrap gap-2">
                    {selected.capabilities.map((cap) => (
                      <Badge key={cap} variant="outline">
                        {cap}
                      </Badge>
                    ))}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <h4 className="font-semibold mb-1">Agent 模型</h4>
                    <p className="font-mono text-muted-foreground text-xs">
                      {models[selected.type] || '—'}
                    </p>
                  </div>
                  <div>
                    <h4 className="font-semibold mb-1">节点 id</h4>
                    <p className="font-mono text-muted-foreground text-xs">{selected.type}</p>
                  </div>
                  <div>
                    <h4 className="font-semibold mb-1">上游</h4>
                    <p className="font-mono text-muted-foreground text-xs">
                      {selected.inputSource}
                    </p>
                  </div>
                  <div>
                    <h4 className="font-semibold mb-1">下游</h4>
                    <p className="font-mono text-muted-foreground text-xs">
                      {selected.outputTarget}
                    </p>
                  </div>
                </div>

                <div className="flex gap-2 pt-4">
                  <Button
                    className="flex-1 pressable"
                    onClick={() => {
                      const type = selected.type;
                      setSelected(null);
                      openWorkflowAtAgent(navigate, type);
                    }}
                  >
                    <Workflow className="size-4 mr-2" />
                    在编排中查看
                  </Button>
                  <Button variant="secondary" onClick={() => setSelected(null)}>
                    关闭
                  </Button>
                </div>
              </div>
            </div>
          ) : null}
        </DrawerContent>
      </Drawer>
    </div>
  );
}
