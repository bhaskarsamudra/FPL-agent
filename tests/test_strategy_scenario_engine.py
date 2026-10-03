from types import SimpleNamespace

from strategy_scenario_engine import (
    build_strategy_horizons,
    evaluate_cross_horizon_strategies,
    SELECTION_BASIS,
)


def _squad():
    return tuple(
        {
            "id": i,
            "name": f"P{i}",
            "position_id": 3,
            "price": 60,
            "squad_position": i,
        }
        for i in range(1, 16)
    )


def _projections():
    rows = {}
    for player_id in range(1, 16):
        rows[player_id] = {
            "projection_complete": True,
            "fixtures": [
                {
                    "gameweek": gw,
                    "expected_points": 5.0,
                    "data_complete": True,
                    "warnings": (),
                }
                for gw in range(6, 14)
            ],
        }
    # Target B wins GW6; target C wins the cumulative longer horizon.
    rows[100] = {
        "projection_complete": True,
        "fixtures": [
            {
                "gameweek": gw,
                "expected_points": 9.0 if gw == 6 else 5.0,
                "data_complete": True,
                "warnings": (),
            }
            for gw in range(6, 14)
        ],
    }
    rows[101] = {
        "projection_complete": True,
        "fixtures": [
            {
                "gameweek": gw,
                "expected_points": 7.0 if gw == 6 else 8.0,
                "data_complete": True,
                "warnings": (),
            }
            for gw in range(6, 14)
        ],
    }
    return rows


def _options():
    return [
        SimpleNamespace(
            option_id="ROLL",
            option_type="roll",
            description="Keep current squad.",
            transfer=None,
            data_complete=True,
            warnings=(),
        ),
        SimpleNamespace(
            option_id="TRANSFER_B",
            option_type="transfer",
            description="Sell P1 for B.",
            transfer=SimpleNamespace(
                sell_player_id=1,
                buy_player_id=100,
                buy_name="B",
                position_id=3,
                net_cost=0.0,
            ),
            data_complete=True,
            warnings=(),
        ),
        SimpleNamespace(
            option_id="TRANSFER_C",
            option_type="transfer",
            description="Sell P1 for C.",
            transfer=SimpleNamespace(
                sell_player_id=1,
                buy_player_id=101,
                buy_name="C",
                position_id=3,
                net_cost=0.0,
            ),
            data_complete=True,
            warnings=(),
        ),
    ]


def test_strategy_horizons_are_target_three_five_eight():
    assert build_strategy_horizons(6) == (
        ("target", (6,)),
        ("short", (6, 7, 8)),
        ("medium", (6, 7, 8, 9, 10)),
        ("long", (6, 7, 8, 9, 10, 11, 12, 13)),
    )


def test_cross_horizon_plan_keeps_horizon_winners_explicit():
    result = evaluate_cross_horizon_strategies(
        decision_gameweek=5,
        target_gameweek=6,
        manager_squad=_squad(),
        projections=_projections(),
        options=_options(),
        free_transfers_before=1,
    )

    assert result.data_complete
    assert result.winner_for("target") == "TRANSFER_B"
    assert result.winner_for("short") == "TRANSFER_C"
    assert result.winner_for("medium") == "TRANSFER_C"
    assert result.winner_for("long") == "TRANSFER_C"
    assert result.selected_option_id == "TRANSFER_C"
    assert result.reconciliation == "LONG_HORIZON_LEADER_WITH_EXPLICIT_TRADE_OFFS"
    assert result.selection_basis == SELECTION_BASIS
    assert result.selection_basis == "PROVISIONAL_LONG_HORIZON_EVALUATION_ANCHOR"
    assert any("TRANSFER_B" in reason for reason in result.rationale)


def test_cross_horizon_does_not_fabricate_missing_long_horizon_data():
    projections = _projections()
    for row in projections.values():
        row["fixtures"] = [fixture for fixture in row["fixtures"] if fixture["gameweek"] <= 10]

    result = evaluate_cross_horizon_strategies(
        decision_gameweek=5,
        target_gameweek=6,
        manager_squad=_squad(),
        projections=projections,
        options=_options(),
        free_transfers_before=1,
    )

    assert result.selected_option_id is None
    assert not result.data_complete
    assert result.reconciliation == "NO_COMPLETE_STRATEGY"
    assert result.winner_for("target") is not None
    assert result.winner_for("long") is None
