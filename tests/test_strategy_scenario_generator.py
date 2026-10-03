from types import SimpleNamespace

import pytest

from strategy_scenario_generator import generate_strategy_scenarios


def _options():
    return [
        SimpleNamespace(
            option_id="ROLL",
            option_type="roll",
            description="Keep the squad.",
            transfer=None,
            chip=None,
            data_complete=True,
            warnings=(),
        ),
        SimpleNamespace(
            option_id="TRANSFER_C",
            option_type="transfer",
            description="Transfer A to C.",
            transfer=SimpleNamespace(
                sell_player_id=1,
                buy_player_id=3,
                net_cost=0.5,
            ),
            chip=None,
            data_complete=True,
            warnings=(),
        ),
    ]


def test_generator_creates_one_path_per_current_option_and_future_reassessment_points():
    result = generate_strategy_scenarios(
        decision_gameweek=5,
        target_gameweek=6,
        horizon_gameweeks=(6, 7, 8),
        options=_options(),
        free_transfers_before=1,
    )

    assert result.data_complete
    assert len(result.scenarios) == 2

    transfer = next(item for item in result.scenarios if "TRANSFER_C" in item.scenario_id)
    assert transfer.initial_action.action_type == "transfer"
    assert transfer.initial_action.buy_player_id == 3
    assert transfer.free_transfers_consumed == 1
    assert transfer.hits_taken == 0
    assert transfer.remaining_transfer_flexibility == 0
    assert transfer.reassessment_gameweeks == (7, 8)
    assert all(
        point.action.action_type == "reassess"
        for point in transfer.decision_points
        if point.is_reassessment
    )


def test_generator_does_not_claim_future_transfers_are_known():
    result = generate_strategy_scenarios(
        decision_gameweek=5,
        target_gameweek=6,
        horizon_gameweeks=(6, 7, 8),
        options=_options()[1:],
        free_transfers_before=1,
    )

    scenario = result.scenarios[0]
    future_actions = [
        point.action.action_type
        for point in scenario.decision_points
        if point.gameweek > scenario.target_gameweek
    ]
    assert future_actions == ["reassess", "reassess"]


def test_generator_records_hit_when_no_free_transfer_is_available():
    result = generate_strategy_scenarios(
        decision_gameweek=5,
        target_gameweek=6,
        horizon_gameweeks=(6, 7, 8),
        options=_options()[1:],
        free_transfers_before=0,
    )

    scenario = result.scenarios[0]
    assert scenario.hits_taken == 1
    assert scenario.hit_cost == 4.0
    assert scenario.remaining_transfer_flexibility == 0
    assert any("4-point hit" in warning for warning in scenario.warnings)


def test_generator_requires_target_gameweek_to_start_horizon():
    with pytest.raises(ValueError, match="start at target_gameweek"):
        generate_strategy_scenarios(
            decision_gameweek=5,
            target_gameweek=6,
            horizon_gameweeks=(7, 8),
            options=_options(),
            free_transfers_before=1,
        )


def test_generator_respects_max_scenarios():
    result = generate_strategy_scenarios(
        decision_gameweek=5,
        target_gameweek=6,
        horizon_gameweeks=(6, 7, 8),
        options=_options(),
        free_transfers_before=1,
        max_scenarios=1,
    )

    assert len(result.scenarios) == 1



def test_generator_from_options_filters_unsupported_future_state_types():
    from strategy_scenario_generator import generate_strategy_scenarios_from_options

    options = _options() + [
        SimpleNamespace(
            option_id="CHIP_TC",
            option_type="chip",
            description="Use Triple Captain.",
            transfer=None,
            chip=SimpleNamespace(chip_instance_id="TRIPLE_CAPTAIN"),
            data_complete=True,
            warnings=(),
        )
    ]
    result = generate_strategy_scenarios_from_options(
        decision_gameweek=5,
        target_gameweek=6,
        horizon_gameweeks=(6, 7, 8),
        options=options,
        free_transfers_before=1,
    )

    assert [item.initial_action.action_type for item in result.scenarios] == [
        "roll", "transfer"
    ]


def test_scenario_exposes_future_points_as_conditional_reassessments():
    result = generate_strategy_scenarios(
        decision_gameweek=5,
        target_gameweek=6,
        horizon_gameweeks=(6, 7, 8),
        options=_options()[:1],
        free_transfers_before=1,
    )

    scenario = result.scenarios[0]
    assert tuple(point.gameweek for point in scenario.future_decision_points) == (7, 8)
    assert all(point.is_reassessment for point in scenario.future_decision_points)
