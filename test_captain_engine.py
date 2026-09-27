from captain_engine import rank_captain_candidates


def test_highest_projected_player_is_first():
    squad = [
        {"id": 1, "name": "A", "selected_by_percent": "20.0"},
        {"id": 2, "name": "B", "selected_by_percent": "50.0"},
    ]
    projections = {
        1: {"horizon_expected_points": 20},
        2: {"horizon_expected_points": 15},
    }

    rows = rank_captain_candidates(
        squad=squad,
        projections=projections,
    )

    assert rows[0].player_name == "A"
