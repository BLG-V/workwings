// EXPORTS: IWorkflowNode, IWorkflowEdge, IWorkflow, NodeStatus, NodeType, NODE_META, PIPELINE_ORDER
export type NodeStatus = 'waiting' | 'running' | 'completed' | 'failed';

/** WorkWings 9 Agent 编排 + Studio 六阶段（后者仅工作台顶栏） */
export type NodeType =
  | 'multimodal_analysis'
  | 'project_analysis'
  | 'requirement_baseline'
  | 'prototype_generation'
  | 'security'
  | 'delivery'
  | 'planner'
  | 'requirement'
  | 'coding'
  | 'frontend'
  | 'testing'
  | 'debug'
  | 'review'
  | 'ship'
  | 'analysis'
  | 'architecture'
  | 'development'
  | 'deployment'
  | 'document';

export const KERNEL_PIPELINE_ORDER: NodeType[] = [
  'multimodal_analysis',
  'project_analysis',
  'requirement_baseline',
  'prototype_generation',
  'architecture',
  'development',
  'testing',
  'security',
  'delivery',
];

/** 编排页默认展示 WorkWings 9 Agent 编排 */
export const PIPELINE_ORDER = KERNEL_PIPELINE_ORDER;

/** Studio 工作台保留五阶段 + 文档占位，并映射到 WorkWings Agent 产物 */
export const STUDIO_PIPELINE_ORDER: NodeType[] = [
  'analysis',
  'architecture',
  'development',
  'testing',
  'deployment',
  'document',
];

export interface IWorkflowNode {
  id: string;
  agentId: string;
  type: NodeType;
  label: string;
  icon: string;
  position: { x: number; y: number };
  config: {
    model: string;
    prompt: string;
    inputSource: string;
    outputTarget: string;
  };
  status: NodeStatus;
}

export interface IWorkflowEdge {
  id: string;
  source: string;
  target: string;
}

export interface IWorkflow {
  nodes: IWorkflowNode[];
  edges: IWorkflowEdge[];
  zoom: number;
  pan: { x: number; y: number };
}

export const DEFAULT_KERNEL_MODELS: Record<string, string> = {
  multimodal_analysis: 'deepseek-v4-flash-vision-exp',
  project_analysis: 'qwen3.7-plus',
  requirement_baseline: 'qwen3.7-plus',
  prototype_generation: 'qwen3-coder-plus',
  architecture: 'qwen3.7-plus',
  development: 'qwen3-coder-plus',
  testing: 'qwen3-coder-plus',
  security: 'qwen3.7-plus',
  delivery: 'qwen3.7-plus',
  planner: 'deepseek-v4-flash',
  requirement: 'deepseek-v4-flash',
  coding: 'deepseek-v4-pro',
  frontend: 'deepseek-v4-pro',
  debug: 'deepseek-v4-pro',
  review: 'deepseek-v4-flash',
  ship: 'deepseek-v4-flash',
};

export const NODE_META: Record<
  NodeType,
  {
    label: string;
    icon: string;
    color: string;
    accent: string;
    stage: string;
    defaultPrompt: string;
    description: string;
  }
> = {
  multimodal_analysis: {
    label: '多模态分析',
    icon: '🧠',
    color: 'from-sky-500 to-cyan-400',
    accent: 'hsl(199 89% 48%)',
    stage: '01',
    description: 'WorkWings Multimodal 解析文本、图片与上传材料',
    defaultPrompt: 'WorkWings Agent：multimodal_analysis_agent',
  },
  project_analysis: {
    label: '项目分析',
    icon: '🧭',
    color: 'from-blue-500 to-sky-400',
    accent: 'hsl(211 90% 48%)',
    stage: '02',
    description: 'WorkWings Project Analysis 识别目标范围、风险与项目上下文',
    defaultPrompt: 'WorkWings Agent：project_analysis_agent',
  },
  requirement_baseline: {
    label: '需求基线',
    icon: '📋',
    color: 'from-cyan-500 to-teal-400',
    accent: 'hsl(187 80% 40%)',
    stage: '03',
    description: 'WorkWings Requirement Baseline 输出需求文档与验收标准',
    defaultPrompt: 'WorkWings Agent：requirement_baseline_agent',
  },
  prototype_generation: {
    label: '原型生成',
    icon: '🖼️',
    color: 'from-teal-500 to-emerald-400',
    accent: 'hsl(168 76% 42%)',
    stage: '04',
    description: 'WorkWings Prototype 生成原型图、页面流和交互说明',
    defaultPrompt: 'WorkWings Agent：prototype_generation_agent',
  },
  planner: {
    label: '规划',
    icon: '🧭',
    color: 'from-sky-500 to-cyan-400',
    accent: 'hsl(199 89% 48%)',
    stage: '01',
    description: 'WorkWings Planner 拆任务、定依赖，禁止合成一条大任务',
    defaultPrompt: 'WorkWings Agent：planner',
  },
  requirement: {
    label: '需求',
    icon: '📋',
    color: 'from-cyan-500 to-teal-400',
    accent: 'hsl(187 80% 40%)',
    stage: '02',
    description: 'WorkWings Requirement 输出结构化 PRD、验收标准与本期范围',
    defaultPrompt: 'WorkWings Agent：requirement',
  },
  coding: {
    label: '编码',
    icon: '💻',
    color: 'from-emerald-500 to-lime-400',
    accent: 'hsl(142 70% 45%)',
    stage: '03',
    description: 'WorkWings Coding 按子任务写代码，失败项可续跑',
    defaultPrompt: 'WorkWings Agent：coding',
  },
  frontend: {
    label: '前端',
    icon: '🖥️',
    color: 'from-lime-500 to-green-400',
    accent: 'hsl(122 60% 40%)',
    stage: '04',
    description: 'WorkWings Frontend 生成页面与入口，挂到 index.html',
    defaultPrompt: 'WorkWings Agent：frontend',
  },
  testing: {
    label: '测试',
    icon: '🧪',
    color: 'from-amber-500 to-yellow-400',
    accent: 'hsl(38 92% 50%)',
    stage: '05',
    description: 'WorkWings Testing 执行冒烟与 metric 真实验收',
    defaultPrompt: 'WorkWings Agent：testing',
  },
  debug: {
    label: '调试',
    icon: '🔧',
    color: 'from-orange-500 to-amber-400',
    accent: 'hsl(24 90% 50%)',
    stage: '06',
    description: 'WorkWings Debug 按失败分类修复代码',
    defaultPrompt: 'WorkWings Agent：debug',
  },
  review: {
    label: '审查',
    icon: '🔎',
    color: 'from-violet-500 to-indigo-400',
    accent: 'hsl(252 70% 55%)',
    stage: '07',
    description: 'WorkWings Review 遇到 blocking 时进入人工审批',
    defaultPrompt: 'WorkWings Agent：review',
  },
  ship: {
    label: '交付',
    icon: '🚀',
    color: 'from-rose-500 to-orange-400',
    accent: 'hsl(12 80% 55%)',
    stage: '08',
    description: 'WorkWings Ship 归档产物并生成交付说明',
    defaultPrompt: 'WorkWings Agent：ship',
  },
  analysis: {
    label: '需求分析',
    icon: '📋',
    color: 'from-sky-500 to-cyan-400',
    accent: 'hsl(199 89% 48%)',
    stage: '01',
    description: '对应 WorkWings Requirement：结构化 PRD 与验收标准',
    defaultPrompt: '请深度分析用户需求，输出结构化的需求文档。',
  },
  architecture: {
    label: '架构设计',
    icon: '🏗️',
    color: 'from-teal-500 to-emerald-400',
    accent: 'hsl(168 76% 42%)',
    stage: '05',
    description: 'WorkWings Architecture 生成架构、接口契约与技术边界',
    defaultPrompt: 'WorkWings Agent：architecture_agent',
  },
  development: {
    label: '开发实现',
    icon: '💻',
    color: 'from-emerald-500 to-lime-400',
    accent: 'hsl(142 70% 45%)',
    stage: '06',
    description: 'WorkWings Development 生成代码变更、迁移和工程实现',
    defaultPrompt: 'WorkWings Agent：development_agent',
  },
  security: {
    label: '安全审查',
    icon: '🔎',
    color: 'from-violet-500 to-indigo-400',
    accent: 'hsl(252 70% 55%)',
    stage: '08',
    description: 'WorkWings Security 审查密钥、权限、越权写入和阻断风险',
    defaultPrompt: 'WorkWings Agent：security_agent',
  },
  delivery: {
    label: '交付归档',
    icon: '🚀',
    color: 'from-rose-500 to-orange-400',
    accent: 'hsl(12 80% 55%)',
    stage: '09',
    description: 'WorkWings Delivery 归档交付包、变更摘要和验收说明',
    defaultPrompt: 'WorkWings Agent：project_delivery_agent',
  },
  deployment: {
    label: '部署上线',
    icon: '🚀',
    color: 'from-rose-500 to-orange-400',
    accent: 'hsl(12 80% 55%)',
    stage: '05',
    description: '对应 WorkWings Ship，禁止自动 git push',
    defaultPrompt: '配置部署与健康检查。',
  },
  document: {
    label: '文档生成',
    icon: '📚',
    color: 'from-cyan-500 to-blue-400',
    accent: 'hsl(195 90% 50%)',
    stage: '06',
    description: 'API、手册与交付文档',
    defaultPrompt: '生成项目文档。',
  },
};

export function isKernelPipeline(nodes: { type: string }[]): boolean {
  const types = new Set(nodes.map((n) => n.type));
  return KERNEL_PIPELINE_ORDER.every((t) => types.has(t));
}
