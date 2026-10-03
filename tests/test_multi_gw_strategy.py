from types import SimpleNamespace

from multi_gw_strategy import evaluate_multi_gw_options


def _option(option_id, option_type, points, complete=True, warnings=()):
    return SimpleNamespace(
        option_id=option_id,
        option_type=option_type,
        projected_horizon_points=points,
        projected_first_gameweek_points=points / 3,
        transfer=None,
        data_complete=complete,
        warnings=warnings,
    )


def test_multi_gw_plan_selects_on_common_horizon_not_first_gw_only():
    result = evaluate_multi_gw_options(
        decision_gameweek=5,
        horizon_gameweeks=[6, 7, 8],
        options=[
            _option("A", "roll", 30),
            _option("B", "transfer", 36),
        ],
        projections={},
        free_transfers_before=1,
    )

    assert result.selected_option_id == "B"
    assert result.options[0].horizon_end_gameweek == 8


def test_roll_retains_explicit_future_flexibility_value():
    result = evaluate_multi_gw_options(
        decision_gameweek=5,
        horizon_gameweeks=[6, 7],
        options=[_option("ROLL", "roll", 20), _option("T", "transfer", 20.2)],
        projections={},
        free_transfers_before=1,
        retained_ft_value=0.5,
    )

    roll = next(row for row in result.options if row.option_id == "ROLL")
    transfer = next(row for row in result.options if row.option_id == "T")
    assert roll.retained_free_transfer_value == 0.5
    assert roll.strategic_score > transfer.strategic_score


def test_transfer_hit_is_explicit_when_no_free_transfer_exists():
    result = evaluate_multi_gw_options(
        decision_gameweek=5,
        horizon_gameweeks=[6, 7],
        options=[_option("T", "transfer", 20)],
        projections={},
        free_transfers_before=0,
        transfer_hit_points=4.0,
    )

    option = result.options[0]
    assert option.transfer_hit_cost == 4.0
    assert option.strategic_score == 16.0
    assert not option.data_complete
    assert any("hit applies" in warning for warning in option.warnings)


def test_incomplete_option_cannot_be_selected():
    result = evaluate_multi_gw_options(
        decision_gameweek=5,
        horizon_gameweeks=[6, 7],
        options=[
            _option("GOOD", "roll", 20),
            _option("INCOMPLETE", "transfer", 100, complete=False),
        ],
        projections={},
        free_transfers_before=1,
    )

    assert result.selected_option_id == "GOOD"
    incomplete = next(row for row in result.options if row.option_id == "INCOMPLETE")
    assert incomplete.opportunity_cost == 0.0


def test_multi_gw_strategy_includes_captaincy_bonus_from_authoritative_engine():
    from captain_engine import build_captaincy_horizon

    squad = [
        {"id": 1, "name": "Captain A"},
        {"id": 2, "name": "Captain B"},
    ]
    projections = {
        1: {"fixtures": [
            {"gameweek": 6, "expected_points": 10, "data_complete": True, "warnings": ()},
            {"gameweek": 7, "expected_points": 10, "data_complete": True, "warnings": ()},
        ]},
        2: {"fixtures": [
            {"gameweek": 6, "expected_points": 8, "data_complete": True, "warnings": ()},
            {"gameweek": 7, "expected_points": 12, "data_complete": True, "warnings": ()},
        ]},
    }
    context = build_captaincy_horizon(
        squad=squad,
        projections=projections,
        horizon_gameweeks=[6, 7],
    )

    result = evaluate_multi_gw_options(
        decision_gameweek=5,
        horizon_gameweeks=[6, 7],
        options=[_option("ROLL", "roll", 40)],
        projections=projections,
        free_transfers_before=1,
        captaincy_context=context,
    )

    option = result.options[0]
    assert option.captaincy_projected_points == 22
    assert option.projected_total_points == 62
    assert option.strategic_score == 62.5
    assert result.captaincy_context is context
