# D ↔ A · branch-human YAML 字段对齐纪要（15 分钟会用）

> 分支：`feat/d-w3-branch-human-docs`（文档） / `feat/a-w3-condition-human`（引擎实现）  
> 样例：`examples/branch-human/workflow.yaml`  
> 接口：`docs/interfaces/w1-api-onepager.md` §5

## 已提议（请 A 拍板）

| 项 | 草案 | 备选（不推荐） |
|----|------|----------------|
| 图结构 | nodes 数组 + edges `from`/`to`（W2） | SRS 元组边 `[[a,b]]` |
| condition 条件 | **边**上 `when: "expr"` + 一条 `when: default` | 节点内 `when: [{expr,goto},{default}]` |
| 表达式 | `params.risk == 'high'` 等简单比较 | 完整 Python eval |
| human 文案 | 节点字段 `reason` | 仅用 `prompt`（旧 SRS） |
| 允许动作 | `allowed: [approve, reject, input]` | 写死三种不可配 |
| 恢复产出 | `outputs.decision` + `outputs.input` | 只写全局 vars |

## 请 A 确认的 4 个问题 — ✅ 已拍板（王振同 / 2026-08-13）

1. `when: default` 字面量是否接受？还是 `when: null` / 省略 when？  
   **→ 接受 `when: default`；validate 强制 condition 出边恰好一条 default。**
2. reject 后 Run → `FAILED` 还是走到专门 end？  
   **→ 沿 human 的出边继续（样例 `after_human`），并写入 `outputs.decision=reject`；不默认 FAILED。**
3. `platform run` 停在 WAITING_USER 时 exit code？  
   **→ `0`（合法暂停）；FAILED 等非法结束仍 ≠ 0。**
4. validate 是否强制：condition 出边必须含且仅含一条 default？  
   **→ 是。**

## 对齐后动作

- [x] A 回复确认或改 §5（本文件已记录拍板）
- [x] A 按冻结字段实现引擎 + 单测（`feat/a-w3-condition-human`）
- [x] D 按结论同步 README / 演示稿（`workflow.yaml` 无结构 diff；已合入 A 侧文档修订）
- [ ] C 按 exit=0 / approve|reject|input 联调 CLI 体验
