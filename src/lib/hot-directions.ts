import type { LucideIcon } from 'lucide-react'
import {
  Boxes,
  Check,
  ChevronRight,
  FileText,
  Layers,
  LayoutGrid,
  PenLine,
  Search,
  Sparkles,
  Zap,
} from 'lucide-react'
import type { ChatSession } from '@/lib/chat-history'

export type HotDirection = {
  id: string
  /** 展示短标题（大方向） */
  label: string
  hint: string
  icon: LucideIcon
  /** 点下去实际发给对话的开放式提示 */
  prompt: string
}

/** 能力方向池（非业务写死样例）；每次按日种子抽样 */
export const HOT_DIRECTION_POOL: HotDirection[] = [
  {
    id: 'req',
    label: '梳理产品需求',
    hint: '需求',
    icon: FileText,
    prompt:
      '帮我把一个想法梳理成可落地的产品需求：目标用户、核心场景、验收标准，先问我缺什么信息。',
  },
  {
    id: 'arch',
    label: '设计系统架构',
    hint: '架构',
    icon: Boxes,
    prompt:
      '根据我描述的业务，给出系统架构与关键流程图：模块边界、数据流、技术选型建议。先确认范围再画。',
  },
  {
    id: 'code',
    label: '实现核心功能',
    hint: '编码',
    icon: PenLine,
    prompt:
      '按多 Agent 工程方式帮我实现一个核心功能模块（API + 前端入口），先对齐接口契约再写代码。',
  },
  {
    id: 'test',
    label: '补齐测试验收',
    hint: '测试',
    icon: Check,
    prompt:
      '为当前功能补测试与验收清单：单元/接口/冒烟各给可执行项，并说明怎么判定通过。',
  },
  {
    id: 'ship',
    label: '准备部署上线',
    hint: '部署',
    icon: ChevronRight,
    prompt:
      '整理部署与上线清单：环境变量、启动命令、回滚与观测要点，适合演示/测试环境。',
  },
  {
    id: 'orchestrate',
    label: '编排 Agent 流程',
    hint: '编排',
    icon: LayoutGrid,
    prompt:
      '帮我设计一条多 Agent 交付链路（规划→需求→编码→测试→评审→交付），说明每步输入输出。',
  },
  {
    id: 'module',
    label: '拆解业务模块',
    hint: '模块',
    icon: Layers,
    prompt:
      '把复杂业务拆成可迭代模块与里程碑，标出本期最小可交付范围，避免一次做整仓。',
  },
  {
    id: 'api',
    label: '约定接口契约',
    hint: '设计',
    icon: Zap,
    prompt:
      '先和我一起定接口契约（路径、字段、错误码），再据此指导前后端实现与联调。',
  },
  {
    id: 'research',
    label: '深入研究问题',
    hint: '研究',
    icon: Search,
    prompt:
      '针对我提出的技术/产品问题做深入研究：对比方案、风险与推荐路径，结论要可执行。',
  },
  {
    id: 'advanced',
    label: '启动高级项目',
    hint: '工程',
    icon: Sparkles,
    prompt:
      '我想做一个可分期交付的高级项目：请先问清目标与约束，再建议里程碑和第一期 MVP。',
  },
]

function daySeed(d = new Date()): number {
  return d.getFullYear() * 10000 + (d.getMonth() + 1) * 100 + d.getDate()
}

function seededShuffle<T>(list: T[], seed: number): T[] {
  const arr = [...list]
  let s = seed % 2147483647
  if (s <= 0) s += 2147483646
  for (let i = arr.length - 1; i > 0; i -= 1) {
    s = (s * 48271) % 2147483647
    const j = s % (i + 1)
    ;[arr[i], arr[j]] = [arr[j], arr[i]]
  }
  return arr
}

/** 从历史会话提炼开放方向（去重、截断） */
function directionsFromSessions(sessions: ChatSession[]): HotDirection[] {
  const out: HotDirection[] = []
  const seen = new Set<string>()
  for (const s of sessions.slice(0, 12)) {
    const title = (s.title || '').trim()
    if (title.length < 4 || title === '新对话' || title === '图片对话') continue
    const key = title.slice(0, 18)
    if (seen.has(key)) continue
    seen.add(key)
    out.push({
      id: `hist-${s.id}`,
      label: key.length >= 18 ? `${key}…` : key,
      hint: '续聊',
      icon: Search,
      prompt: `继续这个方向：${title}。先总结上次要点，再问我下一步想推进什么。`,
    })
    if (out.length >= 3) break
  }
  return out
}

/**
 * 组装首页热门方向：历史续聊（动态）+ 当日抽样的能力方向（非写死业务词）。
 */
export function resolveHotDirections(
  sessions: ChatSession[] = [],
  options?: { limit?: number; now?: Date },
): HotDirection[] {
  const limit = options?.limit ?? 8
  const now = options?.now ?? new Date()
  const fromHistory = directionsFromSessions(sessions)
  const pool = seededShuffle(HOT_DIRECTION_POOL, daySeed(now))
  const merged: HotDirection[] = []
  const used = new Set<string>()

  for (const item of [...fromHistory, ...pool]) {
    if (used.has(item.id) || used.has(item.label)) continue
    used.add(item.id)
    used.add(item.label)
    merged.push(item)
    if (merged.length >= limit) break
  }
  return merged
}
