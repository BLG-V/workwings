from __future__ import annotations

from mawp.goal.models import IssueDocument, PrdDocument, SpecDocument


def _bullet_list(items: list[str]) -> str:
    if not items:
        return "- （待补充）\n"
    return "".join(f"- {item}\n" for item in items)


def _checkbox_list(items: list[str]) -> str:
    if not items:
        return "- [ ] （待补充）\n"
    return "".join(f"- [ ] {item}\n" for item in items)


def render_prd(doc: PrdDocument) -> str:
    return f"""# PRD: {doc.title}

## 元信息
- Slug: {doc.slug}
- 状态: draft
- 描述: {doc.description}

## 背景
{doc.description}

## 目标
{_bullet_list(doc.goals)}

## 非目标
{_bullet_list(doc.non_goals)}

## 用户故事
{_bullet_list(doc.user_stories)}

## 功能需求
{_bullet_list(doc.functional_requirements)}

## 非功能需求
{_bullet_list(doc.non_functional_requirements)}

## 验收标准
{_checkbox_list(doc.acceptance_criteria)}

## 影响模块
{_bullet_list(doc.affected_modules)}

## 风险
{_bullet_list(doc.risks)}

## 关联文件
{_bullet_list(doc.related_files)}

## 开放问题
{_bullet_list(doc.open_questions)}
"""


def render_spec(doc: SpecDocument) -> str:
    plan = _bullet_list(doc.implementation_plan)
    return f"""# SPEC: {doc.title}

## 元信息
- Slug: {doc.slug}
- 关联 PRD: {doc.prd_ref}
- 状态: draft

## 架构设计
{doc.architecture or "（待补充）"}

## API 契约
{doc.api_contracts or "（无 API 变更或待补充）"}

## 数据模型
{doc.data_model or "（待补充）"}

## 错误处理
{doc.error_handling or "（待补充）"}

## 安全策略
{doc.security or "（待补充）"}

## 测试策略
{doc.testing_strategy or "（待补充）"}

## 实施计划
{plan}
"""


def render_issue(doc: IssueDocument) -> str:
    deps = ", ".join(doc.depends_on) if doc.depends_on else "无"
    verify = doc.verify_command or "pytest -q"
    scope = _bullet_list(doc.scope_files) if doc.scope_files else "- （实现时确定）\n"
    return f"""# Issue {doc.id}: {doc.title}

## 元信息
- 状态: {doc.status.value}
- 优先级: {doc.priority}
- 依赖: {deps}
- 关联 PRD: {doc.prd_ref or "—"}
- 关联 SPEC: {doc.spec_ref or "—"}

## 描述
{doc.description}

## 验收标准
{_checkbox_list(doc.acceptance_criteria)}

## 验证命令
```bash
{verify}
```

## 影响文件（预估）
{scope}
"""
