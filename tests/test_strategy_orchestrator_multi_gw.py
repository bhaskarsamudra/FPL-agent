from types import SimpleNamespace

from strategy_orchestrator import build_strategic_decision


def _state():
    squad = tuple(
        {
            "id": i,
            "name": f"P{i}",
            "position_id": 3,
            "price": 60,
            "squad_position": i,
        }
        for i in range(1, 16)
    )
    return SimpleNamespace(
        team_id=1,
        gameweek=5,
        bank=2.0,
        free_transfers=1,
        squad=squad,
    )


def _projections():
    return {
        i: {
            "horizon_expected_points": 10.0 + i,
            "projection_complete": True,
            "fixtures": [
                {"gameweek": 6, "expected_points": 5.0 + i, "data_complete": True, "warnings": ()},
                {"gameweek": 7, "expected_points": 4.0 + i, "data_complete": True, "warnings": ()},
            ],
        }
        for i in range(1, 16)
    }


def test_orchestrator_exposes_multi_gw_plan_and_uses_it_for_selection():
    result = build_strategic_decision(
        manager_state=_state(),
        market_players=[],
        projections=_projections(),
        horizon_gameweeks=[6, 7],
    )

    assert result.multi_gw_plan is not None
    assert result.multi_gw_plan.horizon_gameweeks == (6, 7)
    assert result.multi_gw_plan.selected_option_id == result.selected_option.option_id
    assert result.multi_gw_plan.engine_version == "multi_gw_strategy_v1_1"
