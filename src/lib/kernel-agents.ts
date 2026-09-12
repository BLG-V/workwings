import {
  DEFAULT_KERNEL_MODELS,
  KERNEL_PIPELINE_ORDER,
  NODE_META,
} from '@/lib/workflow-types'

export type KernelAgentId = (typeof KERNEL_PIPELINE_ORDER)[number]

export interface KernelAgentGuide {
  type: KernelAgentId
  label: string
  icon: string
  stage: string
  description: string
  role: string
  capabilities: string[]
  color: string
  inputSource: string
  outputTarget: string
}

const GUIDES: Record<
  KernelAgentId,
  Pick<KernelAgentGuide, 'role' | 'capabilities' | 'inputSource' | 'outputTarget'>
> = {
  multimodal_analysis: {
    role: '解析用户上传的文本、图片和材料，沉淀结构化事实与约束',
    capabilities: ['多模态解析', '材料摘要', '约束提取'],
    inputSource: '用户输入 / 上传材料',
    outputTarget: 'project_analysis',
  },
  project_analysis: {
    role: '识别项目类型、目标范围、风险和初始需求草稿',
    capabilities: ['项目解析', '范围识别', '风险归纳'],
    inputSource: 'multimodal_analysis.artifact',
    outputTarget: 'requirement_baseline',
  },
  requirement_baseline: {
    role: '生成需求基线、验收标准和可审批需求文档',
    capabilities: ['需求基线', '验收标准', '文档产物'],
    inputSource: 'project_analysis.artifact',
    outputTarget: 'prototype_generation',
  },
  prototype_generation: {
    role: '基于需求基线生成原型图、页面流和交互说明',
    capabilities: ['原型生成', '页面流', '交互说明'],
    inputSource: 'requirement_baseline.artifact',
    outputTarget: 'architecture',
  },
  architecture: {
    role: '生成系统架构、接口契约、部署拓扑和工程边界',
    capabilities: ['架构设计', '接口契约', '技术边界'],
    inputSource: 'prototype_generation.artifact',
    outputTarget: 'development',
  },
  development: {
    role: '生成前后端变更、迁移脚本和工程实现产物',
    capabilities: ['代码实现', '迁移脚本', '工程产物'],
    inputSource: 'architecture.artifact',
    outputTarget: 'testing',
  },
  testing: {
    role: '运行真实测试与冒烟检查，记录通过和失败证据',
    capabilities: ['真实测试', '冒烟检查', '测试报告'],
    inputSource: 'development.artifact',
    outputTarget: 'security',
  },
  security: {
    role: '审查密钥泄露、权限边界、越权写入和上线阻断项',
    capabilities: ['安全审查', '越权检查', '阻断项识别'],
    inputSource: 'testing.artifact',
    outputTarget: 'delivery',
  },
  delivery: {
    role: '归档交付包、测试报告、变更摘要和验收说明',
    capabilities: ['交付归档', '验收说明', '产物收口'],
    inputSource: 'security.artifact',
    outputTarget: 'end',
  },
}

export const KERNEL_AGENT_GROUPS: { value: string; label: string; types: KernelAgentId[] }[] =
  [
    { value: 'all', label: '全部', types: [...KERNEL_PIPELINE_ORDER] },
    { value: 'analysis', label: '输入与分析', types: ['multimodal_analysis', 'project_analysis'] },
    {
      value: 'design',
      label: '需求与设计',
      types: ['requirement_baseline', 'prototype_generation', 'architecture'],
    },
    { value: 'build', label: '工程实现', types: ['development'] },
    { value: 'qa', label: '质量安全', types: ['testing', 'security'] },
    { value: 'release', label: '交付归档', types: ['delivery'] },
  ]

export function listKernelAgentGuides(): KernelAgentGuide[] {
  return KERNEL_PIPELINE_ORDER.map((type) => {
    const meta = NODE_META[type]
    const extra = GUIDES[type]
    return {
      type,
      label: `${meta.label} Agent`,
      icon: meta.icon,
      stage: meta.stage,
      description: meta.description,
      color: meta.color,
      ...extra,
    }
  })
}

export function fallbackKernelModels(): Record<string, string> {
  return { ...DEFAULT_KERNEL_MODELS }
}
