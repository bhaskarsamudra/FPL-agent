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



def test_orchestrator_exposes_current_strategy_scenarios_without_future_transfer_claims():
    result = build_strategic_decision(
        manager_state=_state(),
        market_players=[
            {"id": 100, "name": "Target", "position_id": 3, "price": 60}
        ],
        projections=_projections(),
        horizon_gameweeks=list(range(6, 14)),
    )

    assert result.strategy_scenarios
    assert {item.initial_action.action_type for item in result.strategy_scenarios} == {
        "roll", "transfer"
    }
    for scenario in result.strategy_scenarios:
        assert scenario.target_gameweek == 6
        assert scenario.horizon_gameweeks == tuple(range(6, 14))
        assert tuple(point.gameweek for point in scenario.future_decision_points) == tuple(range(7, 14))
        assert all(point.action.action_type == "reassess" for point in scenario.future_decision_points)


def test_orchestrator_does_not_turn_chip_options_into_future_transfer_scenarios():
    projections = _projections()
    chip = SimpleNamespace(
        chip_instance_id="3xc_1",
        chip="3xc",
        target_gameweek=6,
        horizon_start_gameweek=6,
        horizon_end_gameweek=6,
        data_complete=True,
        incremental_value=10.0,
        chip_projected_points=100.0,
        warnings=(),
    )
    result = build_strategic_decision(
        manager_state=_state(),
        market_players=[{"id": 100, "name": "Target", "position_id": 3, "price": 60}],
        projections=projections,
        horizon_gameweeks=[6],
        chip_evaluations=[chip],
    )

    assert any(option.option_type == "chip" for option in result.options)
    assert all(scenario.initial_action.action_type in {"roll", "transfer"} for scenario in result.strategy_scenarios)
