from captain_engine import rank_captain_candidates, select_captain_pair


def test_highest_projected_player_is_first():
    squad = [
        {"id": 1, "name": "A", "selected_by_percent": "20.0"},
        {"id": 2, "name": "B", "selected_by_percent": "50.0"},
    ]
    projections = {
        1: {"horizon_expected_points": 20},
        2: {"horizon_expected_points": 15},
    }

    rows = rank_captain_candidates(squad=squad, projections=projections)
    assert rows[0].player_name == "A"


def test_target_gameweek_sums_double_gameweek_fixtures():
    squad = [
        {"id": 1, "name": "Double", "selected_by_percent": "30.0"},
        {"id": 2, "name": "Single", "selected_by_percent": "60.0"},
    ]
    projections = {
        1: {
            "fixtures": [
                {"gameweek": 6, "expected_points": 6, "data_complete": True, "warnings": ()},
                {"gameweek": 6, "expected_points": 5, "data_complete": True, "warnings": ()},
            ]
        },
        2: {
            "fixtures": [
                {"gameweek": 6, "expected_points": 9, "data_complete": True, "warnings": ()},
            ]
        },
    }

    rows = rank_captain_candidates(
        squad=squad, projections=projections, gameweek=6
    )

    assert rows[0].player_name == "Double"
    assert rows[0].expected_points == 11
    assert rows[0].fixture_count == 2


def test_incomplete_target_projection_is_exposed():
    squad = [{"id": 1, "name": "A", "selected_by_percent": "20.0"}]
    projections = {
        1: {
            "fixtures": [
                {"gameweek": 6, "expected_points": 8, "data_complete": False, "warnings": ("Missing xA",)},
            ]
        }
    }

    rows = rank_captain_candidates(squad=squad, projections=projections, gameweek=6)

    assert rows[0].data_complete is False
    assert "Missing xA" in rows[0].warnings


def test_captain_and_vice_captain_are_distinct():
    squad = [
        {"id": 1, "name": "A"},
        {"id": 2, "name": "B"},
        {"id": 3, "name": "C"},
    ]
    projections = {
        1: {"fixtures": [{"gameweek": 6, "expected_points": 10, "data_complete": True, "warnings": ()}]},
        2: {"fixtures": [{"gameweek": 6, "expected_points": 8, "data_complete": True, "warnings": ()}]},
        3: {"fixtures": [{"gameweek": 6, "expected_points": 6, "data_complete": True, "warnings": ()}]},
    }

    decision = select_captain_pair(squad=squad, projections=projections, gameweek=6)

    assert decision.captain.player_id == 1
    assert decision.vice_captain.player_id == 2
    assert decision.captain.player_id != decision.vice_captain.player_id
    assert decision.data_complete is True


def test_captain_pair_requires_two_candidates():
    squad = [{"id": 1, "name": "A"}]
    projections = {
        1: {"fixtures": [{"gameweek": 6, "expected_points": 10, "data_complete": True, "warnings": ()}]},
    }

    try:
        select_captain_pair(squad=squad, projections=projections, gameweek=6)
    except ValueError as exc:
        assert "two projected squad players" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
