from __future__ import annotations

from mawp.config.loader import AgentConfig, HealModelsConfig
from mawp.runtime.heal_models import select_heal_model


def test_keep_default_on_round_one_unknown() -> None:
    cfg = HealModelsConfig()
    agents = {"coding": "deepseek-v4-pro", "debug": "deepseek-v4-pro", "review": "deepseek-v4-flash"}
    picked = select_heal_model(
        category="unknown",
        agent="coding",
        heal_round=1,
        agent_models=agents,
        heal_cfg=cfg,
    )
    assert picked.model == "deepseek-v4-pro"
    assert picked.strategy == "keep"


def test_syntax_uses_flash_on_round_one() -> None:
    cfg = HealModelsConfig()
    agents = {"coding": "deepseek-v4-pro", "debug": "deepseek-v4-pro"}
    picked = select_heal_model(
        category="syntax_error",
        agent="debug",
        heal_round=1,
        agent_models=agents,
        heal_cfg=cfg,
    )
    assert picked.model == "deepseek-v4-flash"
    assert picked.strategy == "by_category"


def test_review_blocking_uses_pro() -> None:
    cfg = HealModelsConfig()
    agents = {"coding": "deepseek-v4-flash"}
    picked = select_heal_model(
        category="review_blocking",
        agent="coding",
        heal_round=1,
        agent_models=agents,
        heal_cfg=cfg,
    )
    assert picked.model == "deepseek-v4-pro"
    assert picked.strategy == "by_category"


def test_escalate_after_round_two() -> None:
    cfg = HealModelsConfig(escalate_after_round=2, escalate_to="deepseek-v4-pro")
    agents = {"coding": "deepseek-v4-flash", "debug": "deepseek-v4-flash"}
    first = select_heal_model(
        category="syntax_error",
        agent="coding",
        heal_round=1,
        agent_models=agents,
        heal_cfg=cfg,
    )
    second = select_heal_model(
        category="syntax_error",
        agent="coding",
        heal_round=2,
        agent_models=agents,
        heal_cfg=cfg,
    )
    assert first.model == "deepseek-v4-flash"
    assert second.model == "deepseek-v4-pro"
    assert second.strategy == "escalate"


def test_transient_failover_cycles() -> None:
    cfg = HealModelsConfig(
        failover=["deepseek-v4-flash", "deepseek-v4-pro"],
    )
    agents = {"coding": "deepseek-v4-pro"}
    a = select_heal_model(
        category="transient",
        agent="coding",
        heal_round=1,
        agent_models=agents,
        heal_cfg=cfg,
        failover_attempt=0,
    )
    b = select_heal_model(
        category="transient",
        agent="coding",
        heal_round=1,
        agent_models=agents,
        heal_cfg=cfg,
        failover_attempt=1,
    )
    assert a.model == "deepseek-v4-flash"
    assert b.model == "deepseek-v4-pro"
    assert a.strategy == "failover"


def test_agent_config_includes_heal_models_defaults() -> None:
    config = AgentConfig()
    assert config.heal_models.default == "keep"
    assert config.heal_models.by_category["syntax_error"] == "deepseek-v4-flash"
    assert config.heal_models.escalate_after_round == 2
