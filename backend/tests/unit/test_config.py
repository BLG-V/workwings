from pathlib import Path

import pytest

from mawp.config.loader import AgentConfig, load_config


def test_load_default_config():
    config = AgentConfig()
    assert config.llm.model == "deepseek-v4-pro"
    assert config.llm.provider == "openai"


def test_load_example_config():
    example = Path("mawp.config.yaml.example")
    if not example.exists():
        pytest.skip("example config not found")
    config = load_config(example)
    assert config.llm.base_url == "https://api.deepseek.com"


def test_goal_workflow_defaults():
    config = AgentConfig()
    assert config.goal_workflow.base_path == ".goal"
    assert config.autoresearch.max_iterations == 25
    assert config.gstack.enabled is True
    assert config.heal_models.escalate_after_round == 2
    assert config.heal_models.by_category["syntax_error"] == "deepseek-v4-flash"
