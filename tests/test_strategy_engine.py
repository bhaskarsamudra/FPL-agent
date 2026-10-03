from manager_state import ManagerState
from strategy_engine import build_strategy


def test_strategy_engine_produces_structured_output():
    squad = tuple(
        {
            "id": i,
            "name": f"P{i}",
            "position_id": 3 if i <= 8 else 2,
            "price": 60,
            "squad_position": i,
            "selected_by_percent": "20.0",
        }
        for i in range(1, 16)
    )

    state = ManagerState(
        team_id=1,
        gameweek=5,
        team_name="Test FC",
        manager_name="Test",
        bank=2.0,
        team_value=100.0,
        free_transfers=1,
        overall_points=300,
        overall_rank=100000,
        squad=squad,
        chips_played={},
    )

    projections = {
        i: {
            "horizon_expected_points": 10.0 + i,
            "projection_complete": True,
        }
        for i in range(1, 16)
    }

    market = [
        {
            "id": 100,
            "name": "Target",
            "position_id": 3,
            "price": 60,
        }
    ]
    projections[100] = {
        "horizon_expected_points": 40.0,
        "projection_complete": True,
    }

    result = build_strategy(
        manager_state=state,
        market_players=market,
        projections=projections,
        available_chips=["wildcard", "freehit", "bboost", "3xc"],
        horizon_gameweeks=[6, 7, 8],
        fixture_count_by_gameweek={6: 10, 7: 10, 8: 10},
    )

    assert result.engine_version == "strategy_v1"
    assert result.recommendations
    assert result.transfers
    assert result.captains


def test_strategy_uses_next_gameweek_for_captain_candidates():
    squad = tuple(
        {
            "id": i,
            "name": f"P{i}",
            "position_id": 3,
            "price": 60,
            "squad_position": i,
            "selected_by_percent": "20.0",
        }
        for i in range(1, 16)
    )
    state = ManagerState(
        team_id=1, gameweek=5, team_name="Test FC", manager_name="Test",
        bank=2.0, team_value=100.0, free_transfers=1, overall_points=300,
        overall_rank=100000, squad=squad, chips_played={},
    )
    projections = {
        i: {
            "horizon_expected_points": 50.0,
            "projection_complete": True,
            "fixtures": [
                {"gameweek": 6, "expected_points": 5.0, "data_complete": True, "warnings": ()},
                {"gameweek": 7, "expected_points": 20.0, "data_complete": True, "warnings": ()},
            ],
        }
        for i in range(1, 16)
    }
    projections[1]["fixtures"][0]["expected_points"] = 12.0
    projections[2]["fixtures"][0]["expected_points"] = 10.0

    result = build_strategy(
        manager_state=state, market_players=[], projections=projections,
        available_chips=[], horizon_gameweeks=[6, 7],
    )

    assert result.captains[0].player_id == 1
    assert result.captains[0].gameweek == 6
    assert result.captains[0].expected_points == 12.0
