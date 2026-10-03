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
    projections = {
        i: {
            "horizon_expected_points": 40.0,
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
        for i in range(1, 16)
    }
    projections[100] = {
        "horizon_expected_points": 60.0,
        "projection_complete": True,
        "fixtures": [
            {
                "gameweek": gw,
                "expected_points": 7.0,
                "data_complete": True,
                "warnings": (),
            }
            for gw in range(6, 14)
        ],
    }
    return projections


def test_orchestrator_exposes_cross_horizon_strategy_for_eight_gw_input():
    result = build_strategic_decision(
        manager_state=_state(),
        market_players=[
            {"id": 100, "name": "Target", "position_id": 3, "price": 60}
        ],
        projections=_projections(),
        horizon_gameweeks=list(range(6, 14)),
    )

    assert result.cross_horizon_strategy is not None
    plan = result.cross_horizon_strategy
    assert plan.data_complete
    assert plan.selected_option_id == result.selected_option.option_id
    assert dict(plan.horizons)["short"] == (6, 7, 8)
    assert dict(plan.horizons)["medium"] == (6, 7, 8, 9, 10)
    assert dict(plan.horizons)["long"] == (6, 7, 8, 9, 10, 11, 12, 13)
