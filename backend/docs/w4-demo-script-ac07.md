# W4 演示剧本草稿 · AC-08（8 Agent + 生成页）

> 口述约 6 分钟。投屏：`apps/demo-code-agent/README.md`。

---

## 0. 开场

「AC-08：交付主链补上 Requirement 与 Frontend，Testing 可回环 Debug，Review blocking 必须人工确认后再 Ship。禁止自动 push。」

---

## 1. 拓扑（1 分钟）

```text
Planner → Requirement → Coding → Frontend → Testing ↔ Debug → Review → Ship
                                                      └ blocking → human → Ship
```

对照 A：`examples/deliver/workflow.yaml`；App 侧多了 Requirement / Frontend。

---

## 2. validate + 快乐路径（2 分钟）

```bash
platform validate apps/demo-code-agent/workflows/deliver.yaml
platform run apps/demo-code-agent/workflows/deliver.yaml
```

**口述：** Frontend mock 产出页路径；Ship `auto_push=false`。

可打开：`apps/demo-code-agent/frontend/index.html`。

---

## 3. 回环与人工（2 分钟）

```bash
platform run apps/demo-code-agent/workflows/deliver.yaml --params pass_on_attempt=2
platform run apps/demo-code-agent/workflows/deliver.yaml --params review_status=blocking
platform approve <run_id>
```

---

## 4. 收尾

「字段契约见 `docs/w4-ad-deliver-yaml-align.md`；outputs 键名已与 A 冻结。」

## 检查清单

- [ ] validate 绿  
- [ ] 快乐路径 DONE  
- [ ] pass_on_attempt=2 回环 DONE  
- [ ] review_status=blocking → approve → DONE  
- [ ] README 标题为 8 Agent + 生成页 / AC-08  
