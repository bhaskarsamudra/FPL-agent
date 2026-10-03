from strategy_selection import (
    StrategyHorizonComparison,
    StrategyScenarioComparison,
    StrategySelection,
)
from strategy_selection_policy import (
    NO_COMPLETE_BASIS,
    POLICY_VERSION,
    SELECTION_BASIS,
    apply_strategy_selection_policy,
)


def _candidate(scenario_id, values, hit=0.0, flexibility=1, complete=True):
    scores = tuple(
        StrategyHorizonComparison(
            scenario_id=scenario_id,
            horizon_name=name,
            strategic_score=float(value),
            projected_points=float(value),
            transfer_hit_cost=hit,
            data_complete=complete,
        )
        for name, value in zip(("target", "short", "medium", "long"), values)
    )
    return StrategyScenarioComparison(
        scenario_id=scenario_id,
        initial_action_type="transfer",
        horizon_comparisons=scores,
        target_score=float(values[0]),
        short_score=float(values[1]),
        medium_score=float(values[2]),
        long_score=float(values[3]),
        target_to_long_delta=float(values[3] - values[0]),
        hit_cost=hit,
        remaining_transfer_flexibility=flexibility,
        horizon_wins=(),
        data_complete=complete,
    )


def _selection(*candidates, warnings=()):
    return StrategySelection(
        decision_gameweek=5,
        target_gameweek=6,
        candidates=tuple(candidates),
        horizon_leaders=(),
        tradeoffs=(),
        selected_scenario_id=None,
        data_complete=all(item.data_complete for item in candidates),
        warnings=warnings,
    )


def test_balanced_policy_selects_consistent_leader():
    result = apply_strategy_selection_policy(
        _selection(
            _candidate("A", (70, 180, 300, 450)),
            _candidate("B", (65, 170, 290, 440)),
        )
    )
    assert result.selected_scenario_id == "A"
    assert result.selection_basis == SELECTION_BASIS
    assert result.model_version == POLICY_VERSION
    assert result.selection_rationale


def test_long_horizon_does_not_automatically_dominate():
    result = apply_strategy_selection_policy(
        _selection(
            _candidate("A", (100, 200, 300, 401)),
            _candidate("B", (90, 199, 299, 500)),
        )
    )
    assert result.selected_scenario_id == "A"


def test_balanced_rank_profile_handles_horizon_tradeoff():
    result = apply_strategy_selection_policy(
        _selection(
            _candidate("A", (100, 200, 301, 401)),
            _candidate("B", (99, 201, 300, 400)),
        )
    )
    assert result.selected_scenario_id == "A"


def test_hit_cost_breaks_identical_horizon_profile():
    result = apply_strategy_selection_policy(
        _selection(
            _candidate("A", (100, 200, 300, 400), hit=4.0, flexibility=1),
            _candidate("B", (100, 200, 300, 400), hit=0.0, flexibility=1),
        )
    )
    assert result.selected_scenario_id == "B"


def test_flexibility_breaks_identical_horizon_and_hit_profile():
    result = apply_strategy_selection_policy(
        _selection(
            _candidate("A", (100, 200, 300, 400), flexibility=1),
            _candidate("B", (100, 200, 300, 400), flexibility=2),
        )
    )
    assert result.selected_scenario_id == "B"


def test_incomplete_candidate_is_not_selected_when_complete_candidate_exists():
    result = apply_strategy_selection_policy(
        _selection(
            _candidate("A", (100, 200, 300, 400), complete=False),
            _candidate("B", (90, 190, 290, 390), complete=True),
        )
    )
    assert result.selected_scenario_id == "B"
    assert result.data_complete


def test_no_complete_candidates_returns_no_selection():
    result = apply_strategy_selection_policy(
        _selection(_candidate("A", (100, 200, 300, 400), complete=False))
    )
    assert result.selected_scenario_id is None
    assert result.selection_basis == NO_COMPLETE_BASIS
    assert not result.data_complete


def test_policy_preserves_existing_warnings():
    result = apply_strategy_selection_policy(
        _selection(
            _candidate("A", (100, 200, 300, 400)),
            warnings=("Existing warning",),
        )
    )
    assert "Existing warning" in result.warnings
    assert all("Selected A" not in item for item in result.warnings)
