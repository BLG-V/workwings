from __future__ import annotations

from pathlib import Path

from mawp.agents.review_rules import ReviewContext, ReviewRulesAgent, scan_file_for_secrets
from mawp.config.loader import AgentConfig


def test_scan_secrets_detects_api_key(tmp_path: Path) -> None:
    bad = tmp_path / "src" / "config.py"
    bad.parent.mkdir(parents=True)
    bad.write_text('API_KEY = "sk-abcdefghijklmnopqrstuvwxyz123456"\n', encoding="utf-8")
    issues = scan_file_for_secrets(bad)
    assert any(i["level"] == "blocking" for i in issues)


def test_scan_secrets_ignores_placeholder(tmp_path: Path) -> None:
    ok = tmp_path / "src" / "config.py"
    ok.parent.mkdir(parents=True)
    ok.write_text('API_KEY = "your_key_here"\n', encoding="utf-8")
    issues = scan_file_for_secrets(ok)
    assert issues == []


def test_review_rules_blocking_on_secret(tmp_path: Path) -> None:
    target = tmp_path / "src" / "app.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        'token = "sk-abcdefghijklmnopqrstuvwxyz123456"\n',
        encoding="utf-8",
    )
    config = AgentConfig(workspace=str(tmp_path))
    agent = ReviewRulesAgent(config)
    ctx = ReviewContext(
        session_id="s1",
        workspace=tmp_path,
        coding_result={"files_changed": ["src/app.py"]},
        test_report={"passed": True},
    )
    result = agent.run(ctx)
    assert result.success
    assert result.output["blocking_count"] >= 1


def test_review_rules_passes_clean_file(tmp_path: Path) -> None:
    target = tmp_path / "src" / "app.py"
    target.parent.mkdir(parents=True)
    target.write_text("def hello():\n    return 1\n", encoding="utf-8")
    config = AgentConfig(workspace=str(tmp_path))
    agent = ReviewRulesAgent(config)
    ctx = ReviewContext(
        session_id="s2",
        workspace=tmp_path,
        coding_result={"files_changed": ["src/app.py"]},
        test_report={"passed": True},
    )
    result = agent.run(ctx)
    assert result.success
    assert result.output["blocking_count"] == 0
