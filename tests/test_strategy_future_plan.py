"""Tests for Batch 18D-E1 conditional future strategy plans."""

from dataclasses import replace

import pytest

from strategy_future_plan import build_conditional_strategy_plan
from strategy_scenario import StrategyAction, StrategyDecisionPoint, StrategyScenario
from strategy_selection import StrategySelection


def _scenario(*, scenario_id="S1", data_complete=True, future_points=True):
    points = [
        StrategyDecisionPoint(
            gameweek=6,
            action=StrategyAction(
                action_type="transfer",
                description="Sell A and buy B.",
                sell_player_id=1,
                buy_player_id=2,
                data_complete=data_complete,
            ),
        )
    ]
    if future_points:
        points.append(
            StrategyDecisionPoint(
                gameweek=7,
                action=StrategyAction(
                    action_type="reassess",
                    description="Reassess refreshed information.",
                ),
                is_reassessment=True,
                triggers=("availability_change", "new_projection_information"),
            )
        )
    return StrategyScenario(
        scenario_id=scenario_id,
        description="Test scenario",
        decision_gameweek=5,
        target_gameweek=6,
        horizon_gameweeks=(6, 7, 8),
        decision_points=tuple(points),
        free_transfers_consumed=1,
        hits_taken=0,
        hit_cost=0.0,
        remaining_transfer_flexibility=1,
        data_complete=data_complete,
    )


def _selection(selected="S1", complete=True):
    return StrategySelection(
        decision_gameweek=5,
        target_gameweek=6,
        candidates=(),
        horizon_leaders=(),
        tradeoffs=(),
        selected_scenario_id=selected,
        selection_basis="TEST",
        data_complete=complete,
    )


def test_builds_plan_for_selected_scenario():
    plan = build_conditional_strategy_plan(
        selection=_selection(), scenarios=(_scenario(),)
    )

    assert plan is not None
    assert plan.selected_scenario_id == "S1"
    assert plan.initial_action.action_type == "transfer"
    assert plan.future_decision_points[0].gameweek == 7
    assert plan.conditional_rules[0].gameweek == 7


def test_future_actions_are_never_committed():
    plan = build_conditional_strategy_plan(
        selection=_selection(), scenarios=(_scenario(),)
    )

    assert plan.future_actions_committed is False
    assert all(rule.future_action_committed is False for rule in plan.conditional_rules)


def test_no_selection_returns_no_plan():
    assert build_conditional_strategy_plan(
        selection=_selection(selected=None), scenarios=(_scenario(),)
    ) is None


def test_missing_selected_scenario_fails_explicitly():
    with pytest.raises(ValueError, match="not supplied"):
        build_conditional_strategy_plan(
            selection=_selection(selected="MISSING"), scenarios=(_scenario(),)
        )


def test_duplicate_selected_scenario_fails_explicitly():
    with pytest.raises(ValueError, match="more than once"):
        build_conditional_strategy_plan(
            selection=_selection(), scenarios=(_scenario(), _scenario())
        )


def test_selection_and_scenario_completeness_are_combined():
    plan = build_conditional_strategy_plan(
        selection=_selection(complete=True),
        scenarios=(_scenario(data_complete=False),),
    )

    assert plan is not None
    assert plan.data_complete is False


def test_selection_warning_and_scenario_warning_are_preserved():
    scenario = replace(_scenario(), warnings=("scenario warning",))
    selection = replace(_selection(), warnings=("selection warning",))

    plan = build_conditional_strategy_plan(selection=selection, scenarios=(scenario,))

    assert plan is not None
    assert plan.warnings == ("selection warning", "scenario warning")


def test_extended_horizon_without_reassessment_is_explicit_warning():
    scenario = _scenario(future_points=False)
    plan = build_conditional_strategy_plan(
        selection=_selection(), scenarios=(scenario,)
    )

    assert plan is not None
    assert any("no future reassessment point" in warning for warning in plan.warnings)
