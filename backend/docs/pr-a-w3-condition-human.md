# PR：feat/a-w3-condition-human → main

## Summary
- 按 D 的 `branch-human` YAML / 一页纸 §5 对齐并实现 **condition（edges.when）**、**human_checkpoint**、**resume**
- 冻结 A 对四个对齐问题的拍板（见 `docs/w3-ad-yaml-align.md`）
- CLI 补齐 `approve|reject|input`、`--params`；WAITING_USER 合法暂停 exit 0
- 增加 P0 单测 `tests/unit/test_w3_branch_human.py`
- 增加 A→C 交接：`docs/handoff-a-to-c-w3.md`

## Test plan
- [x] `pytest tests/unit/test_w3_branch_human.py tests/unit/test_workflow_engine.py -q`
- [ ] `platform validate examples/branch-human/workflow.yaml`
- [ ] `platform run examples/branch-human/workflow.yaml` → WAITING_USER
- [ ] `platform approve <run_id>` → DONE
- [ ] `platform run ... --params risk=low` → 直接 DONE

## Notes for reviewers
- **否决**旧 SRS 节点内 `when:[{expr,goto}]` 形态，以 W2 `from/to` + 边上 `when` 为准
- reject：沿 human 出边继续并写 `decision=reject`（非默认 FAILED）
- C 同学请看 `docs/handoff-a-to-c-w3.md`，展示层可在 `feat/c-w3-approve-status` 继续打磨
