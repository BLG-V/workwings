# hello-workflow

最小样例：`start → tool:echo → end`。

```bash
pip install -e ".[dev]"
platform validate examples/hello-workflow/workflow.yaml
platform run examples/hello-workflow/workflow.yaml
platform status <run_id>
```

成功时 exit 0，Run 落在工作区 `.mawp/runs/`。
