# 内部工单台 · 本地 IT 工单

本地可打开的内部 IT 工单台小应用：创建工单、查看列表、在「待处理 / 处理中 / 已完成」间切换状态、删除单条工单，刷新页面后数据仍保留在本机浏览器（localStorage）。无需登录、无需后端、无外部依赖、无云端账号体系。

## 本地打开方式

任选其一：

1. **直接打开**：用浏览器（Chrome / Edge / Firefox / Safari）直接打开 `apps/demo-code-agent/frontend/index.html`。

2. **本地静态服务（推荐）**：

   ```bash
   cd apps/demo-code-agent/frontend
   npx serve -l 5175
   ```

   然后访问 <http://localhost:5175/>。

3. **或使用 Python**：

   ```bash
   cd apps/demo-code-agent/frontend
   python -m http.server 8000
   ```

   然后访问 <http://localhost:8000/>。

## 功能

| 功能 | 说明 |
|------|------|
| 创建工单 | 输入标题（必填）与备注（可选）后点击「提交」，新工单置顶且默认「待处理」 |
| 工单列表 | 展示全部工单：标题、状态、创建时间；有备注时一并显示 |
| 状态切换 | 每条工单通过状态下拉在「待处理 / 处理中 / 已完成」间切换，列表立即更新 |
| 删除工单 | 每条工单右侧「删除」按钮，删除后列表立即更新 |
| 持久化 | 数据保存在本机 `localStorage`（键 `it-ticket-desk.tickets.v1`），刷新页面不丢失 |
| 空态提示 | 无工单时显示「还没有工单」 |
| 状态计数 / 筛选 | 顶部展示待处理条数；筛选按钮展示各状态数量并可按状态过滤 |

## 文件说明

| 文件 | 说明 |
|------|------|
| `index.html` | 内部工单台主页（功能入口卡片 + 工单创建 / 列表 / 筛选操作区） |
| `status.html` | 交付状态页（验收标准 + 人工确认） |
| `shell.css` | Admin Shell 布局（深蓝侧栏 + 白顶栏） |
| `theme.css` | Civic Trust 主题（深蓝 #1B4F9C + 青绿 #0D9488） |
| `style.css` | 工单台与状态页组件样式 |
| `shell.js` | 导航注册 `window.MAWP_NAV` 与壳渲染 |
| `app.js` | 工单增删、状态切换、筛选计数与 localStorage 持久化逻辑 |

## 说明

- 所有 `localStorage` 读写均带 `try/catch` 兜底；隐私模式或存储被禁用时降级为「仅本次会话有效」。
- 本仓库不执行自动 git push / merge。
