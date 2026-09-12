from mawp.tools.test_parsing import parse_pytest_output


def test_parse_pytest_output_summary() -> None:
    stdout = """
tests/test_app.py::test_ok PASSED
tests/test_app.py::test_fail FAILED

2 failed, 3 passed, 1 skipped in 0.12s
""".strip()
    stats = parse_pytest_output(stdout)
    assert stats["failed_count"] == 2
    assert stats["passed_count"] == 3
    assert len(stats["failures"]) >= 1


def test_parse_pytest_output_captures_node_id_and_assertion() -> None:
    stdout = """
tests/test_math_add.py::test_add FAILED

================================== FAILURES ===================================
_______________________________ test_add ___________________________________

    def test_add() -> None:
>       assert add(1, 2) == 3
E       assert -1 == 3

tests/test_math_add.py:4: AssertionError
1 failed in 0.05s
""".strip()
    stats = parse_pytest_output(stdout)
    assert stats["failed_count"] == 1
    assert stats["failures"][0]["name"] == "tests/test_math_add.py::test_add"
    assert "assert -1 == 3" in stats["failures"][0]["detail"]


def test_summarize_test_failures() -> None:
    from mawp.tools.test_parsing import summarize_test_failures

    summary = summarize_test_failures(
        [{"name": "tests/test_math_add.py::test_add", "detail": "E assert -1 == 3"}]
    )
    assert "test_math_add.py::test_add" in summary
    assert "assert -1 == 3" in summary


def test_parse_pytest_short_summary_line() -> None:
    stdout = """
=========================== short test summary info ===========================
FAILED tests/test_math_add.py::test_add - assert -1 == 3
1 failed, 12 passed in 0.92s
""".strip()
    stats = parse_pytest_output(stdout)
    assert stats["failed_count"] == 1
    assert stats["failures"][0]["name"] == "tests/test_math_add.py::test_add"
