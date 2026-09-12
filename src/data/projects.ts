// EXPORTS: IProject, MOCK_PROJECTS
export interface IProject {
  id: string
  name: string
  description: string
  goal: string
  status: 'draft' | 'running' | 'completed' | 'failed'
  progress: number
  createdAt: string
  /** 最近一次内核 Deliver 的 run_id，切页后用来接上 */
  kernelRunId?: string | null
  /** WorkWings 后端项目 ID；业务事实源不再由 localStorage 持有 */
  workwingsProjectId?: string | null
}

export const MOCK_PROJECTS: IProject[] = [
  {
    id: '1',
    name: '电商后台管理系统',
    description: '基于React + Node.js的全栈电商后台',
    goal: '从0到1搭建完整的电商管理平台',
    status: 'running',
    progress: 65,
    createdAt: '2024-01-15T10:30:00Z',
  },
  {
    id: '2',
    name: 'AI 智能客服系统',
    description: '多轮对话 + 知识库检索的客服机器人',
    goal: '构建支持7x24小时的智能客服解决方案',
    status: 'completed',
    progress: 100,
    createdAt: '2024-01-10T08:00:00Z',
  },
  {
    id: '3',
    name: '团队协作工具',
    description: '类 Notion 的在线协作文档平台',
    goal: '打造轻量级团队知识管理与协作工具',
    status: 'draft',
    progress: 0,
    createdAt: '2024-01-20T14:20:00Z',
  },
  {
    id: '4',
    name: '数据可视化大屏',
    description: '企业运营数据实时展示大屏',
    goal: '完成核心指标监控与数据可视化展示',
    status: 'failed',
    progress: 35,
    createdAt: '2024-01-08T09:15:00Z',
  },
  {
    id: '5',
    name: '移动端社交 App',
    description: '基于 React Native 的社交应用',
    goal: '快速原型验证与核心功能开发',
    status: 'running',
    progress: 42,
    createdAt: '2024-01-18T16:45:00Z',
  },
]
