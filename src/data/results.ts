// EXPORTS: IResult, MOCK_RESULTS
export interface IResult {
  id: string
  projectId: string
  type: 'requirement' | 'architecture' | 'code' | 'test' | 'document' | 'deployment'
  title: string
  summary: string
  content: string
  stats?: {
    total: number
    passed: number
    failed: number
  }
  fileTree?: {
    name: string
    children?: { name: string }[]
  }[]
  deployMeta?: {
    version: string
    env: string
    url: string
    health: string
  }
}

export const MOCK_RESULTS: IResult[] = [
  {
    id: 'r1',
    projectId: '1',
    type: 'requirement',
    title: '电商后台管理系统 - 需求文档',
    summary: '完整的产品需求文档，包含功能模块、用户故事和优先级排序',
    content: `# 电商后台管理系统需求文档

## 1. 产品概述
本系统是一个面向电商企业的后台管理平台，支持商品管理、订单处理、用户管理、数据统计等核心功能。

## 2. 功能需求

### 2.1 商品管理
- 商品列表展示与搜索
- 商品新增/编辑/删除
- 商品分类管理
- 库存管理
- 价格调整

### 2.2 订单管理
- 订单列表与详情
- 订单状态流转
- 发货处理
- 退款处理

### 2.3 用户管理
- 用户列表
- 用户信息编辑
- 权限管理
- 黑名单管理

### 2.4 数据统计
- 销售数据看板
- 用户增长分析
- 商品销量排行
- 导出报表

## 3. 非功能需求
- 响应时间 < 200ms
- 支持 1000 并发用户
- 数据每日备份
- 支持移动端适配

## 4. 优先级
| 功能 | 优先级 |
|------|--------|
| 商品管理 | P0 |
| 订单管理 | P0 |
| 用户管理 | P1 |
| 数据统计 | P2 |
`,
  },
  {
    id: 'r-arch',
    projectId: '1',
    type: 'architecture',
    title: '电商后台 · 架构方案与流程图',
    summary: '系统架构图、模块依赖关系与部署拓扑',
    content: `# 系统架构设计

## 技术选型
- 前端：React 19 + TypeScript + Vite + Tailwind
- 后端：Node.js + NestJS
- 数据：PostgreSQL + Redis
- 部署：Docker + CI/CD

## 业务流程图

\`\`\`
用户下单 → 库存预占 → 支付确认 → 履约发货 → 售后闭环
   │           │           │           │           │
   └──── 风控校验 ── 消息通知 ── 数据落库 ── 指标回流 ──┘
\`\`\`

## 系统架构图

\`\`\`
┌─────────┐   ┌──────────┐   ┌────────────┐
│ 管理后台 │──▶│ API 网关 │──▶│  业务中台   │
└─────────┘   └──────────┘   └─────┬──────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
        ┌──────────┐        ┌──────────┐        ┌──────────┐
        │ 商品服务  │        │ 订单服务  │        │ 用户服务  │
        └────┬─────┘        └────┬─────┘        └────┬─────┘
             └─────────┬─────────┴─────────┬─────────┘
                       ▼                   ▼
                 ┌──────────┐        ┌──────────┐
                 │ PostgreSQL│        │  Redis   │
                 └──────────┘        └──────────┘
\`\`\`
`,
  },
  {
    id: 'r2',
    projectId: '1',
    type: 'code',
    title: '核心代码文件',
    summary: '项目核心源代码，包含前端组件和后端接口',
    content: `// src/components/ProductList.tsx
import { useState, useEffect } from 'react'
import { Table, Button, Input, Space } from 'antd'
import { PlusOutlined, SearchOutlined } from '@ant-design/icons'
import { productApi } from '@/api/product'

export default function ProductList() {
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')

  useEffect(() => {
    fetchProducts()
  }, [])

  const fetchProducts = async () => {
    setLoading(true)
    try {
      const res = await productApi.getList({ keyword })
      setProducts(res.data)
    } finally {
      setLoading(false)
    }
  }

  const columns = [
    { title: '商品ID', dataIndex: 'id', width: 100 },
    { title: '商品名称', dataIndex: 'name' },
    { title: '分类', dataIndex: 'category' },
    { title: '价格', dataIndex: 'price', render: (v) => \`¥\${v}\` },
    { title: '库存', dataIndex: 'stock' },
    { title: '状态', dataIndex: 'status' },
    { title: '操作', render: () => (
      <Space>
        <Button size="small">编辑</Button>
        <Button size="small" danger>删除</Button>
      </Space>
    )},
  ]

  return (
    <div className="p-6">
      <div className="flex justify-between mb-4">
        <Input
          placeholder="搜索商品"
          prefix={<SearchOutlined />}
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          style={{ width: 300 }}
        />
        <Button type="primary" icon={<PlusOutlined />}>
          新增商品
        </Button>
      </div>
      <Table
        columns={columns}
        dataSource={products}
        loading={loading}
        rowKey="id"
        pagination={{ pageSize: 20 }}
      />
    </div>
  )
}

// src/api/product.ts
import request from '@/utils/request'

export const productApi = {
  getList: (params) => request.get('/api/products', { params }),
  getDetail: (id) => request.get(\`/api/products/\${id}\`),
  create: (data) => request.post('/api/products', data),
  update: (id, data) => request.put(\`/api/products/\${id}\`, data),
  delete: (id) => request.delete(\`/api/products/\${id}\`),
}
`,
    fileTree: [
      {
        name: 'src',
        children: [
          { name: 'ProductList.tsx' },
          { name: 'OrderList.tsx' },
          { name: 'UserList.tsx' },
          { name: 'Dashboard.tsx' },
        ],
      },
      {
        name: 'api',
        children: [
          { name: 'product.ts' },
          { name: 'order.ts' },
          { name: 'user.ts' },
        ],
      },
    ],
  },
  {
    id: 'r3',
    projectId: '1',
    type: 'test',
    title: '测试报告',
    summary: '自动化测试执行报告，包含用例通过率和缺陷分析',
    content: `# 测试报告

## 测试概览
- 测试时间：2024-01-20
- 测试环境：测试环境 v1.2.0
- 测试人员：自动化测试Agent

## 测试结果统计

| 模块 | 用例数 | 通过 | 失败 | 通过率 |
|------|--------|------|------|--------|
| 商品管理 | 12 | 12 | 0 | 100% |
| 订单管理 | 15 | 14 | 1 | 93% |
| 用户管理 | 8 | 8 | 0 | 100% |
| 数据统计 | 5 | 4 | 1 | 80% |
| **总计** | **40** | **38** | **2** | **95%** |

## 失败用例详情

### 1. 订单退款流程异常
- 用例ID: TC-ORDER-015
- 严重程度: 中
- 描述: 部分退款后订单状态未正确更新
- 建议: 检查订单状态机逻辑

### 2. 数据导出超时
- 用例ID: TC-STAT-005
- 严重程度: 低
- 描述: 大数据量导出时接口超时
- 建议: 增加异步导出机制

## 结论
整体质量良好，核心功能通过率100%，建议修复2个中低优先级问题后发布。
`,
    stats: {
      total: 40,
      passed: 38,
      failed: 2,
    },
  },
  {
    id: 'r-deploy',
    projectId: '1',
    type: 'deployment',
    title: '生产环境部署记录',
    summary: '镜像构建、流水线发布与健康检查全部通过',
    content: `# 部署上线报告

## 发布流水线
1. ✅ 构建镜像 agentflow-admin:1.2.0
2. ✅ 安全扫描无高危漏洞
3. ✅ Staging 冒烟通过
4. ✅ 生产滚动发布 100%
5. ✅ 监控告警规则已生效

## 环境信息
- 版本：1.2.0
- 集群：cn-east-prod-01
- 副本：3
- 入口：https://admin.shop.example.com

## 回滚策略
一键回滚至上一稳定版本 1.1.8，预计 RTO < 3 分钟。
`,
    deployMeta: {
      version: '1.2.0',
      env: 'production',
      url: 'https://admin.shop.example.com',
      health: 'healthy',
    },
  },
  {
    id: 'r-doc',
    projectId: '1',
    type: 'document',
    title: '项目交付文档',
    summary: 'API 说明、运维手册与使用指南',
    content: `# 交付文档包

## 目录
1. OpenAPI 接口文档
2. 权限与角色模型
3. 部署与回滚手册
4. 常见问题 FAQ

## 快速启动
\`\`\`bash
npm install
npm run dev
\`\`\`
`,
  },
]
