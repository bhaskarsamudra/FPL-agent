"""Tests for Batch 18D-E2 conditional multi-GW strategy reassessment."""

from strategy_future_plan import build_conditional_strategy_plan
from strategy_reassessment import (
    EXECUTE_INITIAL_ACTION,
    HOLD_CURRENT_STRATEGY,
    NO_ACTION_DATA_INCOMPLETE,
    NO_ACTION_NO_REASSESSMENT_POINT,
    REASSESS_AND_REGENERATE,
    StrategyReassessmentContext,
    resolve_strategy_step,
)
from strategy_scenario import StrategyAction, StrategyDecisionPoint, StrategyScenario
from strategy_selection import StrategySelection


def _scenario(*, future=True):
    points = [
        StrategyDecisionPoint(
            gameweek=6,
            action=StrategyAction(
                action_type="transfer",
                description="Sell A and buy B.",
                sell_player_id=1,
                buy_player_id=2,
                data_complete=True,
            ),
        )
    ]
    if future:
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
        scenario_id="S1",
        description="Test scenario",
        decision_gameweek=5,
        target_gameweek=6,
        horizon_gameweeks=(6, 7, 8),
        decision_points=tuple(points),
        free_transfers_consumed=1,
        hits_taken=0,
        hit_cost=0.0,
        remaining_transfer_flexibility=1,
        data_complete=True,
    )


def _plan(*, future=True):
    scenario = _scenario(future=future)
    selection = StrategySelection(
        decision_gameweek=5,
        target_gameweek=6,
        candidates=(),
        horizon_leaders=(),
        tradeoffs=(),
        selected_scenario_id="S1",
        selection_basis="TEST",
        data_complete=True,
    )
    return build_conditional_strategy_plan(selection=selection, scenarios=(scenario,))


def test_target_gameweek_exposes_initial_action():
    decision = resolve_strategy_step(
        plan=_plan(), context=StrategyReassessmentContext(gameweek=6)
    )
    assert decision.decision_type == EXECUTE_INITIAL_ACTION
    assert "Sell A" in decision.action_description
    assert decision.future_action_committed is False


def test_future_gameweek_without_trigger_holds_strategy():
    decision = resolve_strategy_step(
        plan=_plan(), context=StrategyReassessmentContext(gameweek=7)
    )
    assert decision.decision_type == HOLD_CURRENT_STRATEGY
    assert decision.triggered_rules == ()


def test_future_trigger_requests_fresh_strategy_generation():
    decision = resolve_strategy_step(
        plan=_plan(),
        context=StrategyReassessmentContext(
            gameweek=7,
            observed_triggers=("availability_change",),
        ),
    )
    assert decision.decision_type == REASSESS_AND_REGENERATE
    assert decision.triggered_rules == ("availability_change",)
    assert decision.future_action_committed is False


def test_future_trigger_does_not_commit_specific_transfer():
    decision = resolve_strategy_step(
        plan=_plan(),
        context=StrategyReassessmentContext(
            gameweek=7,
            observed_triggers=("new_projection_information",),
        ),
    )
    assert decision.decision_type == REASSESS_AND_REGENERATE
    assert "Sell A" not in decision.action_description
    assert decision.future_action_committed is False


def test_missing_reassessment_input_blocks_new_action():
    decision = resolve_strategy_step(
        plan=_plan(),
        context=StrategyReassessmentContext(
            gameweek=7,
            observed_triggers=("availability_change",),
            available_inputs=("manager_state", "fixture_state"),
        ),
    )
    assert decision.decision_type == NO_ACTION_DATA_INCOMPLETE
    assert "player_availability" in decision.required_inputs
    assert "refreshed_projections" in decision.required_inputs
    assert decision.data_complete is False


def test_context_data_incomplete_blocks_any_new_action():
    decision = resolve_strategy_step(
        plan=_plan(),
        context=StrategyReassessmentContext(gameweek=7, data_complete=False),
    )
    assert decision.decision_type == NO_ACTION_DATA_INCOMPLETE
    assert decision.future_action_committed is False


def test_before_target_gameweek_does_not_execute_early():
    decision = resolve_strategy_step(
        plan=_plan(), context=StrategyReassessmentContext(gameweek=5)
    )
    assert decision.decision_type == NO_ACTION_NO_REASSESSMENT_POINT
    assert decision.future_action_committed is False


def test_future_gameweek_without_defined_reassessment_point_is_explicit():
    decision = resolve_strategy_step(
        plan=_plan(future=False),
        context=StrategyReassessmentContext(gameweek=7),
    )
    assert decision.decision_type == NO_ACTION_NO_REASSESSMENT_POINT
    assert decision.future_action_committed is False


def test_required_inputs_are_preserved_for_reassessment():
    decision = resolve_strategy_step(
        plan=_plan(), context=StrategyReassessmentContext(gameweek=7)
    )
    assert decision.required_inputs == (
        "manager_state",
        "player_availability",
        "fixture_state",
        "refreshed_projections",
    )
