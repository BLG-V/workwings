import { useEffect, useState } from 'react'
import { Brain, ChevronDown, Check, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { toast } from 'sonner'
import { listModels, updateModels } from '@/lib/mawp-api'

interface ModelOption {
  id: string
  label: string
  tier: string
}

const AGENT_LABELS: Record<string, string> = {
  planner: '规划器 (Planner)',
  requirement: '需求分析 (Requirement)',
  coding: '代码生成 (Coding)',
  frontend: '前端生成 (Frontend)',
  testing: '测试验证 (Testing)',
  debug: '调试修复 (Debug)',
  review: '代码审查 (Review)',
  ship: '交付部署 (Ship)',
}

const AGENT_ORDER = ['planner', 'requirement', 'coding', 'frontend', 'testing', 'debug', 'review', 'ship']

export default function ModelSwitcher() {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [models, setModels] = useState<ModelOption[]>([])
  const [current, setCurrent] = useState<Record<string, string>>({})
  const [draft, setDraft] = useState<Record<string, string>>({})
  const [defaultModel, setDefaultModel] = useState('')

  const fetchModels = async () => {
    setLoading(true)
    try {
      const data = await listModels()
      setModels(data.available_models)
      setCurrent(data.current)
      setDraft(data.current)
      setDefaultModel(data.default_llm_model)
    } catch {
      // 离线时忽略
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (open) void fetchModels()
  }, [open])

  const handleSave = async () => {
    setSaving(true)
    try {
      const result = await updateModels(draft)
      setCurrent(result.current)
      toast.success('模型配置已更新')
      setOpen(false)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleReset = () => {
    setDraft(current)
    toast.info('已恢复当前配置')
  }

  const handleSetAll = (modelId: string) => {
    const next: Record<string, string> = {}
    for (const agent of AGENT_ORDER) {
      next[agent] = modelId
    }
    setDraft(next)
  }

  const hasChanges = JSON.stringify(draft) !== JSON.stringify(current)

  return (
    <>
      <Button
        variant="ghost"
        size="sm"
        className="h-8 gap-1.5 text-xs text-muted-foreground"
        onClick={() => setOpen(true)}
      >
        <Brain className="size-3.5" />
        <span className="hidden sm:inline">模型</span>
        <ChevronDown className="size-3" />
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="font-display flex items-center gap-2">
              <Brain className="size-4 text-primary" />
              多模型切换
            </DialogTitle>
            <DialogDescription>
              按阶段选择不同模型，平衡速度与质量。配置在运行时生效。
            </DialogDescription>
          </DialogHeader>

          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="size-6 animate-spin text-primary" />
            </div>
          ) : (
            <div className="flex-1 overflow-y-auto space-y-4 px-1">
              {/* 快捷操作 */}
              <div className="flex items-center gap-2 rounded-xl border border-border/80 bg-muted/30 px-3 py-2">
                <span className="text-[11px] text-muted-foreground shrink-0">快捷全设：</span>
                {models
                  .filter((m) => m.tier === 'fast')
                  .slice(0, 2)
                  .map((m) => (
                    <Button
                      key={m.id}
                      size="sm"
                      variant="secondary"
                      className="h-6 px-2 text-[10px]"
                      onClick={() => handleSetAll(m.id)}
                    >
                      {m.label.split('（')[0]}
                    </Button>
                  ))}
                {models
                  .filter((m) => m.tier === 'strong')
                  .slice(0, 2)
                  .map((m) => (
                    <Button
                      key={m.id}
                      size="sm"
                      variant="secondary"
                      className="h-6 px-2 text-[10px]"
                      onClick={() => handleSetAll(m.id)}
                    >
                      {m.label.split('（')[0]}
                    </Button>
                  ))}
                <div className="ml-auto text-[10px] text-muted-foreground">
                  默认：{defaultModel || '—'}
                </div>
              </div>

              {/* 各 Agent 模型选择 */}
              <div className="space-y-2">
                {AGENT_ORDER.map((agent) => (
                  <div
                    key={agent}
                    className="flex items-center gap-3 rounded-lg border border-border/60 px-3 py-2"
                  >
                    <div className="w-32 shrink-0">
                      <div className="text-xs font-medium">{AGENT_LABELS[agent] || agent}</div>
                      <div className="text-[10px] text-muted-foreground font-mono">{agent}</div>
                    </div>
                    <select
                      value={draft[agent] || ''}
                      onChange={(e) => setDraft({ ...draft, [agent]: e.target.value })}
                      className="flex-1 rounded-lg border border-border bg-background px-3 py-1.5 text-xs"
                    >
                      {models.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.label}
                        </option>
                      ))}
                    </select>
                    {draft[agent] !== current[agent] ? (
                      <span className="size-2 rounded-full bg-amber-400 shrink-0" title="已修改" />
                    ) : (
                      <span className="size-2 rounded-full bg-emerald-400 shrink-0" title="未修改" />
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 底部操作 */}
          <div className="flex items-center justify-between gap-2 border-t border-border/60 pt-3">
            <Button
              variant="ghost"
              size="sm"
              className="text-xs text-muted-foreground"
              onClick={handleReset}
              disabled={!hasChanges || saving}
            >
              恢复
            </Button>
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" onClick={() => setOpen(false)}>
                取消
              </Button>
              <Button
                size="sm"
                className="pressable"
                disabled={!hasChanges || saving}
                onClick={() => void handleSave()}
              >
                {saving ? (
                  <Loader2 className="size-3.5 mr-1.5 animate-spin" />
                ) : (
                  <Check className="size-3.5 mr-1.5" />
                )}
                保存配置
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
