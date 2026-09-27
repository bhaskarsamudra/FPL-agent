"""Tests for the data-driven FPL Rules Engine."""

import pytest

from fpl_rules import (
    FALLBACK_2026_27_RULES,
    RulesEngine,
    RulesUnavailableError,
)
from fpl_squad_rules import validate_squad, validate_starting_xi


def test_fallback_contains_current_2026_27_baseline():
    rules = FALLBACK_2026_27_RULES
    assert rules.season == "2026/27"
    assert rules.max_free_transfers == 5
    assert rules.chip_sets == 2
    assert rules.max_chips_per_gameweek == 1
    assert rules.position_limits == {"GK": 2, "DEF": 5, "MID": 5, "FWD": 3}


def test_engine_consumes_typed_rules():
    engine = RulesEngine(FALLBACK_2026_27_RULES)
    assert engine.goal_points("GK") == 10
    assert engine.goal_points("DEF") == 6
    assert engine.goal_points("MID") == 5
    assert engine.goal_points("FWD") == 4
    assert engine.clean_sheet_points("MID") == 1
    assert engine.defensive_contribution_threshold("DEF") == 10
    assert engine.transfer_hit(4, 2) == -8
    assert engine.captain_multiplier() == 2
    assert engine.captain_multiplier("triple_captain") == 3


def test_live_rules_require_authoritative_source():
    engine = RulesEngine(FALLBACK_2026_27_RULES, authoritative=False)
    with pytest.raises(RulesUnavailableError):
        engine.require_authoritative()


def test_authoritative_rules_can_be_required():
    engine = RulesEngine(FALLBACK_2026_27_RULES, authoritative=True)
    assert engine.require_authoritative().season == "2026/27"


def test_invalid_inputs_raise():
    engine = RulesEngine(FALLBACK_2026_27_RULES)
    with pytest.raises(ValueError):
        engine.goal_points("BAD")
    with pytest.raises(ValueError):
        engine.transfer_hit(-1, 1)
