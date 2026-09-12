import { useState, useMemo, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Plus,
  Search,
  Play,
  CheckCircle,
  Clock,
  AlertCircle,
  Trash2,
  FolderKanban,
  Calendar,
  Sparkles,
  Wand2,
  ArrowRight,
  History,
  Gauge,
  Workflow,
} from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
  CardDescription,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
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
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import type { IProject } from '@/data/projects';
import {
  createProject,
  deleteProject as removeStoredProject,
  listProjects,
  replaceProjects,
  resolveWorkflowPath,
  setLastProjectId,
  upsertProject,
} from '@/lib/projects-store';
import { deleteRunsForProject } from '@/lib/runs-store';
import { deleteWorkflow } from '@/lib/workflows-store';
import { format, formatDistanceToNow } from 'date-fns';
import { zhCN } from 'date-fns/locale';
import {
  createProject as createWorkWingsProject,
  deleteProject as deleteWorkWingsProject,
  listProjects as listWorkWingsProjects,
} from '@/integrations/workwings/client';
import { mapProject } from '@/integrations/workwings/mappers';

const statusConfig = {
  running: {
    label: '进行中',
    icon: Play,
    color: 'text-sky-300',
    bg: 'bg-sky-500/10 border-sky-500/30',
  },
  completed: {
    label: '已完成',
    icon: CheckCircle,
    color: 'text-emerald-300',
    bg: 'bg-emerald-500/10 border-emerald-500/30',
  },
  draft: {
    label: '草稿',
    icon: Clock,
    color: 'text-muted-foreground',
    bg: 'bg-muted/50 border-border',
  },
  failed: {
    label: '失败',
    icon: AlertCircle,
    color: 'text-red-300',
    bg: 'bg-red-500/10 border-red-500/30',
  },
};

const workwingsStages = [
  { key: 'input', stage: '01', icon: '◐', label: '输入分析' },
  { key: 'project', stage: '02', icon: '◇', label: '项目解析' },
  { key: 'approval', stage: '03', icon: '✓', label: '人工确认' },
  { key: 'baseline', stage: '04', icon: '▤', label: '需求基线' },
  { key: 'prototype', stage: '05', icon: '▧', label: '原型生成' },
  { key: 'build', stage: '06', icon: '⌘', label: '开发落地' },
  { key: 'verify', stage: '07', icon: '◎', label: '测试审查' },
  { key: 'delivery', stage: '08', icon: '↗', label: '交付验收' },
];

export default function ProjectsPage() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<IProject[]>(() => listProjects());
  const [keyword, setKeyword] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [createOpen, setCreateOpen] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [newProject, setNewProject] = useState({
    name: '',
    description: '',
    goal: '',
  });

  useEffect(() => {
    const refresh = () => setProjects(listProjects());
    refresh();
    window.addEventListener('mawp-projects-change', refresh);
    window.addEventListener('mawp-auth-change', refresh);
    return () => {
      window.removeEventListener('mawp-projects-change', refresh);
      window.removeEventListener('mawp-auth-change', refresh);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    void listWorkWingsProjects()
      .then((items) => {
        if (!cancelled) {
          const mapped = items.map(mapProject);
          replaceProjects(mapped);
          setProjects(mapped);
        }
      })
      .catch(() => {
        /* WorkWings 离线时只保留本机 UI 缓存，创建/运行仍会提示后端不可用 */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = useMemo(() => {
    return projects.filter((p) => {
      const matchKeyword =
        !keyword ||
        p.name.toLowerCase().includes(keyword.toLowerCase()) ||
        p.description.toLowerCase().includes(keyword.toLowerCase());
      const matchStatus = statusFilter === 'all' || p.status === statusFilter;
      return matchKeyword && matchStatus;
    });
  }, [projects, keyword, statusFilter]);

  const stats = useMemo(() => {
    const total = projects.length;
    const running = projects.filter((p) => p.status === 'running').length;
    const completed = projects.filter((p) => p.status === 'completed').length;
    const failed = projects.filter((p) => p.status === 'failed').length;
    const avgProgress = Math.round(
      projects.reduce((s, p) => s + p.progress, 0) / Math.max(total, 1),
    );
    const lastUpdated = projects[0]?.createdAt ?? null;
    return { total, running, completed, failed, avgProgress, lastUpdated };
  }, [projects]);

  const openProjectRuns = (projectId: string) => {
    setLastProjectId(projectId)
    navigate('/runs')
  }

  const handleCreate = () => {
    if (!newProject.name.trim()) {
      toast.error('请输入项目名称');
      return;
    }
    void (async () => {
      try {
        const remote = await createWorkWingsProject({
          name: newProject.name,
          description: [newProject.description, newProject.goal]
            .filter(Boolean)
            .join('\n\n'),
        });
        const project = {
          ...mapProject(remote),
          goal: newProject.goal.trim(),
        };
        upsertProject(project);
        const stored = project;
        setProjects((current) => [stored, ...current.filter((item) => item.id !== stored.id)]);
        setCreateOpen(false);
        setNewProject({ name: '', description: '', goal: '' });
        toast.success('项目创建成功，已进入 WorkWings 工作流');
        navigate(`/workflow/${stored.id}`);
      } catch (error) {
        toast.error(error instanceof Error ? error.message : 'WorkWings 项目创建失败');
      }
    })();
  };

  const handleDelete = (id: string) => {
    void (async () => {
      const removeLocalProject = () => {
        removeStoredProject(id);
        deleteWorkflow(id);
        deleteRunsForProject(id);
        setProjects((current) => current.filter((item) => item.id !== id));
        setDeleteId(null);
      };
      try {
        const target = projects.find((item) => item.id === id);
        await deleteWorkWingsProject(target?.workwingsProjectId || id);
        removeLocalProject();
        toast.success('项目及其后端数据已删除');
      } catch (error) {
        if (
          error &&
          typeof error === 'object' &&
          'status' in error &&
          (error as { status?: number }).status === 404
        ) {
          removeLocalProject();
          toast.success('后端项目不存在，已清理本地项目缓存');
          return;
        }
        toast.error(error instanceof Error ? error.message : '项目删除失败');
      }
    })();
  };

  const openDemoPipeline = () => {
    const path = resolveWorkflowPath();
    if (path) {
      navigate(path);
      return;
    }
    const project = createProject({
      name: '演示流水线项目',
      description: '一键体验需求 → 架构 → 代码 → 测试 → 部署',
      goal: '跑通智流完整多智能体流水线',
    });
    navigate(`/workflow/${project.id}`);
  };

  const createDialog = (
    <Dialog open={createOpen} onOpenChange={setCreateOpen}>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>创建新项目</DialogTitle>
          <DialogDescription>
            填写目标后进入工作流，可一键生成完整 Agent 流水线
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="name">项目名称 *</Label>
            <Input
              id="name"
              value={newProject.name}
              onChange={(e) =>
                setNewProject((p) => ({ ...p, name: e.target.value }))
              }
              placeholder="例如：电商后台管理系统"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="description">项目描述</Label>
            <Textarea
              id="description"
              value={newProject.description}
              onChange={(e) =>
                setNewProject((p) => ({
                  ...p,
                  description: e.target.value,
                }))
              }
              placeholder="简要描述项目背景与核心功能"
              rows={3}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="goal">项目目标 / 需求草稿</Label>
            <Textarea
              id="goal"
              value={newProject.goal}
              onChange={(e) =>
                setNewProject((p) => ({ ...p, goal: e.target.value }))
              }
              placeholder="用自然语言描述最终目标，后续可智能生成流水线"
              rows={3}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={() => setCreateOpen(false)}>
            取消
          </Button>
          <Button onClick={handleCreate}>创建并进入编辑器</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );

  return (
    <div className="flex flex-col gap-4 p-5 md:p-6">
      {createDialog}

      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-[11px] text-primary">
            <Sparkles className="size-3.5" />
            智流 AgentFlow · WorkWings 项目中枢
          </div>
          <h1 className="mt-1 font-display text-2xl font-semibold tracking-tight">
            项目管理
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            统一进入工作流、运行记录与交付。自然语言建项，卡片里继续跑。
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={() => setCreateOpen(true)}>
            <Wand2 className="size-4 mr-2" />
            新建项目
          </Button>
          <Button variant="secondary" onClick={openDemoPipeline}>
            体验流水线
            <ArrowRight className="size-4 ml-2" />
          </Button>
          <Button variant="outline" onClick={() => navigate('/runs')}>
            <History className="size-4 mr-2" />
            运行记录
          </Button>
        </div>
      </header>

      <div className="flex flex-wrap items-center gap-1.5">
        <span className="mr-1 text-[11px] text-muted-foreground shrink-0">
          标准流水线
        </span>
        {workwingsStages.map((stage, index) => {
          return (
            <span key={stage.key} className="inline-flex items-center gap-1.5">
              {index > 0 ? (
                <span className="text-muted-foreground/40 text-[10px]">→</span>
              ) : null}
              <span className="inline-flex items-center gap-1 rounded-full border border-border/70 bg-card/70 px-2 py-0.5 text-[11px]">
                <span className="font-mono text-[10px] text-muted-foreground">
                  {stage.stage}
                </span>
                <span>{stage.icon}</span>
                <span className="font-medium">{stage.label}</span>
              </span>
            </span>
          );
        })}
      </div>

      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border/60 bg-card/40 px-3 py-2">
        {[
          { label: '全部', value: stats.total },
          { label: '进行中', value: stats.running },
          { label: '完成', value: stats.completed },
          { label: '失败', value: stats.failed },
          { label: '均进度', value: `${stats.avgProgress}%` },
        ].map((item) => (
          <div
            key={item.label}
            className="flex items-baseline gap-1.5 rounded-lg px-2 py-1"
          >
            <span className="text-base font-display font-semibold tabular-nums leading-none">
              {item.value}
            </span>
            <span className="text-[11px] text-muted-foreground">{item.label}</span>
          </div>
        ))}
        <div className="hidden md:flex items-center gap-1.5 text-[11px] text-muted-foreground ml-1 pl-2 border-l border-border/60 min-w-0">
          <Gauge className="size-3.5 shrink-0" />
          <span className="truncate">
            最近 {projects[0]?.name ?? '暂无'}
            {stats.lastUpdated
              ? ` · ${formatDistanceToNow(new Date(stats.lastUpdated), { locale: zhCN, addSuffix: true })}`
              : ''}
          </span>
        </div>
        <div className="relative flex-1 min-w-[180px] max-w-sm ml-auto">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="搜索项目"
            className="h-8 pl-8 text-sm"
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="h-8 w-[128px]">
            <SelectValue placeholder="状态" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部状态</SelectItem>
            <SelectItem value="running">进行中</SelectItem>
            <SelectItem value="completed">已完成</SelectItem>
            <SelectItem value="draft">草稿</SelectItem>
            <SelectItem value="failed">失败</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center border border-dashed rounded-xl">
          <FolderKanban className="size-12 text-muted-foreground/50 mb-4" />
          <h3 className="text-lg font-medium mb-2">暂无项目</h3>
          <p className="text-sm text-muted-foreground mb-4">
            创建第一个项目，开启智能研发流水线
          </p>
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="size-4 mr-2" />
            新建项目
          </Button>
        </div>
      ) : (
        <motion.div
          layout
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
        >
          <AnimatePresence mode="popLayout">
            {filtered.map((project) => {
              const sc = statusConfig[project.status];
              const StatusIcon = sc.icon;
              return (
                <motion.div
                  key={project.id}
                  layout
                  initial={{ opacity: 0, scale: 0.96 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.96 }}
                  transition={{ duration: 0.2 }}
                  whileHover={{ y: -3 }}
                >
                  <Card
                    className="h-full cursor-pointer group hover:border-primary/45 transition-colors bg-card/70"
                    onClick={() => navigate(`/workflow/${project.id}`)}
                    role="link"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        navigate(`/workflow/${project.id}`)
                      }
                    }}
                  >
                    <CardHeader className="pb-2 pt-4 px-4" onClick={(e) => e.stopPropagation()}>
                      <div className="flex items-start justify-between gap-2">
                        <CardTitle className="text-sm font-semibold line-clamp-1">
                          {project.name}
                        </CardTitle>
                        <div className="flex items-center gap-1 shrink-0">
                          <Badge
                            variant="outline"
                            className={`${sc.bg} ${sc.color} border text-[10px]`}
                          >
                            <StatusIcon className="size-3 mr-1" />
                            {sc.label}
                          </Badge>
                          <Button
                            size="icon"
                            variant="ghost"
                            className="size-7 opacity-0 group-hover:opacity-100 transition-opacity"
                            onClick={(e) => {
                              e.stopPropagation();
                              setDeleteId(project.id);
                            }}
                          >
                            <Trash2 className="size-4 text-muted-foreground hover:text-destructive" />
                          </Button>
                        </div>
                      </div>
                      <CardDescription className="line-clamp-1 text-xs">
                        {project.description || '暂无描述'}
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-2.5 px-4 pb-3" onClick={(e) => e.stopPropagation()}>
                      <div className="space-y-1">
                        <div className="flex items-center justify-between text-[11px]">
                          <span className="text-muted-foreground">
                            WorkWings 进度
                          </span>
                          <span className="font-medium tabular-nums">
                            {project.progress}%
                          </span>
                        </div>
                        <Progress value={project.progress} className="h-1.5" />
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          size="sm"
                          className="h-7 flex-1"
                          onClick={(e) => {
                            e.stopPropagation()
                            navigate(`/workflow/${project.id}`)
                          }}
                        >
                          <Workflow className="size-3.5 mr-1.5" />
                          打开工作流
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-7"
                          onClick={(e) => {
                            e.stopPropagation()
                            openProjectRuns(project.id)
                          }}
                        >
                          运行记录
                        </Button>
                      </div>
                    </CardContent>
                    <CardFooter className="flex items-center justify-between border-t px-4 py-2.5" onClick={(e) => e.stopPropagation()}>
                      <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                        <Calendar className="size-3.5" />
                        {format(new Date(project.createdAt), 'yyyy年MM月dd日', {
                          locale: zhCN,
                        })}
                      </div>
                      <Link
                        to={`/workflow/${project.id}`}
                        className="text-[11px] text-primary hover:underline"
                        onClick={(e) => e.stopPropagation()}
                      >
                        进入编辑器 →
                      </Link>
                    </CardFooter>
                  </Card>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </motion.div>
      )}

      <AlertDialog open={!!deleteId} onOpenChange={(o) => !o && setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除项目？</AlertDialogTitle>
            <AlertDialogDescription>
              删除后项目数据将无法恢复，包括工作流配置和运行记录。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => deleteId && handleDelete(deleteId)}
            >
              确认删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
