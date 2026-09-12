# -*- coding: utf-8 -*-
from pathlib import Path

Path(r"c:\Users\wzt20\Desktop\agentflow\src\pages\AgentMarketPage\AgentMarketPage.tsx").write_text(r'''import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Search,
  Plus,
  Sparkles,
  Star,
} from 'lucide-react';
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerDescription,
} from '@/components/ui/drawer';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { MOCK_AGENTS, type IAgent } from '@/data/agents';
import { toast } from 'sonner';

const categories = [
  { value: 'all', label: '全部' },
  { value: 'analysis', label: '需求分析' },
  { value: 'architecture', label: '架构设计' },
  { value: 'development', label: '代码开发' },
  { value: 'testing', label: '测试验证' },
  { value: 'deployment', label: '部署运维' },
  { value: 'document', label: '文档生成' },
  { value: 'custom', label: '角色模板' },
];

export default function AgentMarketPage() {
  const navigate = useNavigate();
  const [keyword, setKeyword] = useState('');
  const [category, setCategory] = useState('all');
  const [selectedAgent, setSelectedAgent] = useState<IAgent | null>(null);
  const [agents, setAgents] = useState(MOCK_AGENTS);
  const [createOpen, setCreateOpen] = useState(false);
  const [draft, setDraft] = useState({
    name: '',
    description: '',
    role: '',
    model: 'GPT-4o',
  });

  const filtered = useMemo(() => {
    return agents.filter((a) => {
      const matchKeyword =
        !keyword ||
        a.name.toLowerCase().includes(keyword.toLowerCase()) ||
        a.description.toLowerCase().includes(keyword.toLowerCase());
      const matchCategory = category === 'all' || a.category === category;
      return matchKeyword && matchCategory;
    });
  }, [keyword, category, agents]);

  const officialAgents = filtered.filter((a) => !a.isTemplate);
  const templateAgents = filtered.filter((a) => a.isTemplate);

  const handleCreate = () => {
    if (!draft.name.trim()) {
      toast.error('请填写 Agent 名称');
      return;
    }
    const agent: IAgent = {
      id: `custom-${Date.now()}`,
      name: draft.name.trim(),
      icon: '✨',
      description: draft.description.trim() || '自定义 Agent',
      role: draft.role.trim() || '自定义角色',
      capabilities: ['自定义能力', '对话协作'],
      model: draft.model,
      category: 'custom',
      isTemplate: true,
      templateName: draft.name.trim(),
      imageUrl:
        'https://lf3-static.bytednsdoc.com/obj/eden-cn/ylcylz_fsph_ryhs/ljhwZthlaukjlkulzlp/feisuda/avatar/base/7.jpg',
    };
    setAgents((prev) => [agent, ...prev]);
    setCreateOpen(false);
    setDraft({ name: '', description: '', role: '', model: 'GPT-4o' });
    setSelectedAgent(agent);
    toast.success('自定义 Agent 已创建');
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-display font-bold tracking-tight">Agent 市场</h1>
          <p className="text-sm text-muted-foreground mt-1">
            覆盖需求分析、架构流程图、代码编写、测试与部署的官方 Agent
          </p>
        </div>
        <Button className="pressable" onClick={() => setCreateOpen(true)}>
          <Plus className="size-4 mr-2" />
          创建自定义Agent
        </Button>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1 max-w-md">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="搜索Agent名称或描述"
            className="pl-9"
          />
        </div>
        <Select value={category} onValueChange={setCategory}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="分类筛选" />
          </SelectTrigger>
          <SelectContent>
            {categories.map((c) => (
              <SelectItem key={c.value} value={c.value}>
                {c.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {officialAgents.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3 flex items-center gap-2">
            <Sparkles className="size-4 text-primary" />
            官方 Agent
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {officialAgents.map((agent, i) => (
              <motion.div
                key={agent.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
              >
                <Card
                  className="cursor-pointer hover:border-primary/50 transition-colors h-full pressable"
                  onClick={() => setSelectedAgent(agent)}
                >
                  <CardContent className="p-4">
                    <div className="flex items-start gap-3">
                      <div className="size-12 rounded-xl bg-gradient-to-br from-primary to-sky-400 flex items-center justify-center text-2xl shrink-0">
                        {agent.icon}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <h3 className="font-semibold text-sm truncate">
                            {agent.name}
                          </h3>
                          <Badge variant="outline" className="text-[10px] shrink-0">
                            {agent.model}
                          </Badge>
                        </div>
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
        </div>
      )}

      {templateAgents.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3 flex items-center gap-2">
            <Star className="size-4 text-amber-500" />
            角色模板
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {templateAgents.map((agent, i) => (
              <motion.div
                key={agent.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
              >
                <Card
                  className="cursor-pointer hover:border-primary/50 transition-colors h-full pressable"
                  onClick={() => setSelectedAgent(agent)}
                >
                  <CardContent className="p-4">
                    <div className="flex items-start gap-3">
                      <div className="size-12 rounded-xl bg-gradient-to-br from-amber-500 to-orange-500 flex items-center justify-center text-2xl shrink-0">
                        {agent.icon}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <h3 className="font-semibold text-sm truncate">
                            {agent.name}
                          </h3>
                          <Badge className="text-[10px] shrink-0 bg-amber-500/15 text-amber-700 border-amber-500/30">
                            模板
                          </Badge>
                        </div>
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
        </div>
      )}

      <Drawer open={!!selectedAgent} onOpenChange={(o) => !o && setSelectedAgent(null)}>
        <DrawerContent className="max-w-2xl mx-auto">
          {selectedAgent && (
            <div className="p-6">
              <DrawerHeader className="p-0 mb-4">
                <div className="flex items-start gap-4">
                  <div className="size-16 rounded-xl bg-gradient-to-br from-primary to-sky-400 flex items-center justify-center text-3xl shrink-0">
                    {selectedAgent.icon}
                  </div>
                  <div className="flex-1">
                    <DrawerTitle className="text-xl">{selectedAgent.name}</DrawerTitle>
                    <DrawerDescription className="mt-1">
                      {selectedAgent.description}
                    </DrawerDescription>
                  </div>
                </div>
              </DrawerHeader>

              <div className="space-y-4">
                <div>
                  <h4 className="text-sm font-semibold mb-2">角色设定</h4>
                  <p className="text-sm text-muted-foreground">{selectedAgent.role}</p>
                </div>

                <div>
                  <h4 className="text-sm font-semibold mb-2">能力标签</h4>
                  <div className="flex flex-wrap gap-2">
                    {selectedAgent.capabilities.map((cap) => (
                      <Badge key={cap} variant="outline">
                        {cap}
                      </Badge>
                    ))}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <h4 className="text-sm font-semibold mb-2">默认模型</h4>
                    <p className="text-sm text-muted-foreground">{selectedAgent.model}</p>
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold mb-2">分类</h4>
                    <p className="text-sm text-muted-foreground">
                      {categories.find((c) => c.value === selectedAgent.category)?.label}
                    </p>
                  </div>
                </div>

                <div className="flex gap-2 pt-4">
                  <Button
                    className="flex-1 pressable"
                    onClick={() => {
                      toast.success(`已添加 ${selectedAgent.name} 到工作流`);
                      setSelectedAgent(null);
                      navigate('/workflow/1', {
                        state: { addAgentId: selectedAgent.id },
                      });
                    }}
                  >
                    <Plus className="size-4 mr-2" />
                    添加到工作流
                  </Button>
                  <Button variant="secondary" onClick={() => setSelectedAgent(null)}>
                    关闭
                  </Button>
                </div>
              </div>
            </div>
          )}
        </DrawerContent>
      </Drawer>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>创建自定义 Agent</DialogTitle>
            <DialogDescription>
              配置名称、角色与默认模型，创建后可加入工作流
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="space-y-2">
              <Label>名称</Label>
              <Input
                value={draft.name}
                onChange={(e) => setDraft((d) => ({ ...d, name: e.target.value }))}
                placeholder="例如：合规审查 Agent"
              />
            </div>
            <div className="space-y-2">
              <Label>描述</Label>
              <Textarea
                rows={2}
                value={draft.description}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, description: e.target.value }))
                }
                placeholder="这个 Agent 擅长做什么"
              />
            </div>
            <div className="space-y-2">
              <Label>角色设定</Label>
              <Textarea
                rows={2}
                value={draft.role}
                onChange={(e) => setDraft((d) => ({ ...d, role: e.target.value }))}
                placeholder="例如：资深合规专家"
              />
            </div>
            <div className="space-y-2">
              <Label>默认模型</Label>
              <Select
                value={draft.model}
                onValueChange={(v) => setDraft((d) => ({ ...d, model: v }))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {['GPT-4o', 'Claude 3.5', '豆包4', 'DeepSeek', 'Gemini 1.5'].map(
                    (m) => (
                      <SelectItem key={m} value={m}>
                        {m}
                      </SelectItem>
                    ),
                  )}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>
              取消
            </Button>
            <Button onClick={handleCreate}>创建</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
''', encoding='utf-8')
print('AgentMarket written')
