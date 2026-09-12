# 高级项目生成能力 · 优化计划

> **核心目标已纠正**：升级的是「智流 MAWP 多 Agent 平台本身」，让它能支撑自己写出高级大项目。  
> 详见主文档：[`PLATFORM_LARGE_PROJECT_UPGRADE.md`](./PLATFORM_LARGE_PROJECT_UPGRADE.md)

旁路「高级项目」页只是 **SRS 入库 + 分期调度**；真正写代码必须走八 Agent Deliver。

## 现状缺口

| 缺口 | 影响 |
|------|------|
| Deliver 步数/单文件倾向 | 扛不住多模块工程 |
| 无 project_mode / 隔离工作区 | 容易污染平台仓库 |
| Advanced 曾用模板生成 | 与多 Agent 主链脱节 |

## 本轮平台升级（已落地方向）

1. Coding/Frontend 提高 max_steps；大项目提示词  
2. `write_files` 批量写  
3. `workspaces/` 前端策略放行  
4. Studio Deliver `project_mode`  
5. Advanced 生成默认调用 Deliver  
6. Coding 按任务循环 + 真实 `metric_command` 冒烟  
7. 高级项目 ZIP 导出 / 复制工作区路径  
8. Testing 失败 → Debug 回投 Coding 真修（最多 5 轮）  
9. Live `/health` 冒烟 + 工作区文件树/预览 + 期依赖图  
10. 「一键生成剩余里程碑」依赖波次调度（冒烟失败可提前停）  
11. 前端 build 级冒烟（缺依赖时可 `MAWP_SMOKE_WEB_INSTALL=1` 自动 install）  
12. 同波次无冲突里程碑：**沙箱并行生成再合并**（`parallel_workers`）  

## 仍待增强

- [ ] 并行合并冲突的精细三路 diff / 人工确认  
- [ ] 前端无网络环境的离线缓存镜像 install  

## 成功标准

Studio 勾选「大项目工程模式」或高级项目「生成当前期 / 一键生成剩余」后，产物落在 `workspaces/<id>/`，且经由 HybridAgentRunner / Deliver，而不是只堆静态模板；Testing 跑真实冒烟（API 语法 + Live health + 可选 web install/build）；依赖就绪的多期可沙箱并行；失败会自动修复再测。
