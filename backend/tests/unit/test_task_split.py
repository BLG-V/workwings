"""大模块任务拆分 + 上下文截断：避免一次 LLM 调用超时后整期 fallback 模板。"""

from __future__ import annotations

from mawp.runtime.project_deliver import extract_tasks_from_ctx
from mawp.runtime.task_split import (
    compact_coding_payload,
    payload_char_count,
    prefer_split_tasks,
    should_retry_coding_task,
    split_phase_into_subtasks,
    srs_slice_for_task,
)


P4 = {
    "id": "p4",
    "title": "商城/团购/佣金最小闭环",
    "goal": "商品列表、下单占位、团长端入口、佣金结算",
}


def test_mall_commission_splits_into_four() -> None:
    tasks = split_phase_into_subtasks(P4)
    assert len(tasks) >= 4
    titles = " ".join(str(t.get("title") or "") for t in tasks)
    assert "商品" in titles
    assert "下单" in titles
    assert "团长" in titles
    assert "佣金" in titles


def test_deliverables_split_generic_phase() -> None:
    tasks = split_phase_into_subtasks(
        {
            "id": "p7",
            "title": "通知中心",
            "goal": "多种通知",
            "deliverables": ["站内信列表", "推送开关", "已读状态"],
        }
    )
    assert len(tasks) == 3
    assert "站内信" in tasks[0]["title"]


def test_prefer_injected_when_planner_collapses() -> None:
    injected = split_phase_into_subtasks(P4)
    planner = [{"id": "T1", "title": "一次性实现整个商城团购佣金模块"}]
    chosen = prefer_split_tasks(planner, injected)
    assert len(chosen) >= 4
    assert chosen[0]["title"] == injected[0]["title"]


def test_prefer_planner_when_already_granular() -> None:
    injected = split_phase_into_subtasks({"id": "p4", "title": "商城", "goal": "商品"})
    planner = [{"id": f"T{i}", "title": f"细任务{i}"} for i in range(1, 7)]
    chosen = prefer_split_tasks(planner, injected)
    assert len(chosen) == 6


def test_extract_tasks_keeps_injected_split() -> None:
    injected = split_phase_into_subtasks(P4)
    tasks = extract_tasks_from_ctx(
        {},
        {"planner": {"tasks": [{"id": "T1", "title": "整个 P4 商城一次性生成"}]}},
        goal="商城",
        params={"tasks": injected},
    )
    assert len(tasks) >= 4


def test_srs_slice_is_smaller_and_on_topic() -> None:
    srs = (
        "# 邻智云 SRS\n\n"
        "## 报修\n业主在线报修与接单流转，含照片上传。\n\n"
        "## 商城团购\n商品列表、下单、团长带货与佣金结算。SKU 含库存与价格。\n\n"
        "## 运营大屏\n社区运营指标可视化，含报修量与缴费率。\n"
    ) * 40
    task = {"title": "商品列表 API", "detail": "GET /api/products"}
    sliced = srs_slice_for_task(srs, task, max_chars=800)
    assert len(sliced) < len(srs)
    assert len(sliced) <= 800
    assert "商品" in sliced or "团购" in sliced
    assert sliced.count("大屏") <= srs.count("大屏")


def test_compact_payload_drops_full_srs_and_priors() -> None:
    huge_srs = "规格书" * 5000
    task = {"id": "T1", "title": "商品列表 API", "detail": "products"}
    naive = {
        "input": {"goal": "做完整个商城", "srs_excerpt": huge_srs},
        "params": {"srs_excerpt": huge_srs, "project_root": "ws/x"},
        "prior_outputs": {
            "requirement": {"summary": "长文" * 2000, "tasks": [{"id": "T1"}]}
        },
    }
    compact = compact_coding_payload(
        input_data={"instruction": "只做商品 API", "current_task": task},
        params={"srs_excerpt": huge_srs, "project_root": "ws/x", "project_mode": True},
        prior_outputs=naive["prior_outputs"],
        task=task,
    )
    assert payload_char_count(compact) < payload_char_count(naive) // 2
    summary = str((compact["prior_outputs"].get("requirement") or {}).get("summary") or "")
    assert len(summary) <= 400
    assert len(str(compact["params"].get("srs_excerpt") or "")) < len(huge_srs)


def test_timeout_error_retries_once() -> None:
    assert should_retry_coding_task("The read operation timed out", 1) is True
    assert should_retry_coding_task("The read operation timed out", 2) is False
    assert should_retry_coding_task("OpenAI API 错误 (402)", 1) is False


def test_plan_coding_resume_skips_successful_only() -> None:
    from mawp.runtime.task_split import plan_coding_resume

    tasks = [
        {"id": "T1", "title": "api"},
        {"id": "T2", "title": "page"},
        {"id": "T3", "title": "fee"},
    ]
    prior = {
        "tasks_done": ["T1"],
        "changed_files": ["ws/a.py"],
        "task_runs": [
            {
                "task_id": "T1",
                "success": True,
                "changed_files": ["ws/a.py"],
            },
            {
                "task_id": "T2",
                "success": False,
                "error": "timeout",
                "changed_files": [],
            },
        ],
    }
    plan = plan_coding_resume(tasks, prior)
    assert plan["resumed"] is True
    assert [t["id"] for t in plan["pending"]] == ["T2", "T3"]
    assert plan["skipped"][0]["task_id"] == "T1"
    assert plan["skipped"][0]["skipped"] is True
    assert "ws/a.py" in plan["carried_changed_files"]
    assert plan["carried_done"] == ["T1"]


def test_plan_coding_resume_rerun_all() -> None:
    from mawp.runtime.task_split import plan_coding_resume

    tasks = [{"id": "T1", "title": "a"}, {"id": "T2", "title": "b"}]
    prior = {
        "tasks_done": ["T1", "T2"],
        "task_runs": [
            {"task_id": "T1", "success": True},
            {"task_id": "T2", "success": True},
        ],
    }
    plan = plan_coding_resume(tasks, prior, rerun_all=True)
    assert plan["resumed"] is False
    assert len(plan["pending"]) == 2
    assert plan["skipped"] == []


def test_prior_coding_output_merges_nodes_and_input() -> None:
    from mawp.runtime.task_split import prior_coding_output

    prior = prior_coding_output(
        {"tasks_done": ["T2"], "changed_files": ["b.py"]},
        {
            "coding": {
                "tasks_done": ["T1"],
                "task_runs": [{"task_id": "T1", "success": True}],
                "changed_files": ["a.py"],
            }
        },
    )
    assert prior["tasks_done"] == ["T2"]
    assert prior["changed_files"] == ["b.py"]
    assert prior["task_runs"][0]["task_id"] == "T1"
