"""失败分类：Runs 观测板依赖 classify_error。"""

from __future__ import annotations

from mawp.runtime.error_classifier import classify_error
from mawp.runtime.run_observe import summarize_run_observe


def test_quota_402_insufficient_balance() -> None:
    cls = classify_error(
        'OpenAI API 错误 (402): {"error":{"message":"Insufficient Balance"}}'
    )
    assert cls.category == "quota"


def test_llm_read_timeout() -> None:
    cls = classify_error("OpenAI 请求失败: The read operation timed out")
    assert cls.category == "timeout"


def test_truncated_smoke_fail() -> None:
    cls = classify_error(
        '[FAIL] attempt=2 exit=1 4500ms cmd="python \'workspaces/x/scripts/smoke_check.py\'"'
    )
    assert cls.category == "test_failed"


def test_syntax_still_wins_over_fail_wrapper() -> None:
    cls = classify_error(
        "[FAIL] attempt=2 exit=1\n  File \"main.py\", line 3\nSyntaxError: invalid syntax"
    )
    assert cls.category == "syntax_error"


def test_observe_classifies_truncated_run_error() -> None:
    obs = summarize_run_observe(
        [],
        status="FAILED",
        error='OpenAI API 错误 (402): {"error":{"message":"Insuffici...',
    )
    assert obs["error_category"] == "quota"


def test_observe_overrides_unknown_heal() -> None:
    obs = summarize_run_observe(
        [],
        status="FAILED",
        error="The read operation timed out",
        heal={"error_category": "unknown"},
    )
    assert obs["error_category"] == "timeout"
