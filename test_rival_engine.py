from rival_engine import build_rival_snapshots, identify_nearest_rivals


def test_rivals_are_relative_to_user():
    standings = [
        {"entry": 1, "rank": 1, "entry_name": "A", "player_name": "A", "total": 300},
        {"entry": 2, "rank": 2, "entry_name": "B", "player_name": "B", "total": 295},
        {"entry": 3, "rank": 3, "entry_name": "C", "player_name": "C", "total": 250},
    ]

    rivals = build_rival_snapshots(
        standings=standings,
        user_team_id=2,
    )

    nearest = identify_nearest_rivals(rivals, limit=1)

    assert nearest[0].entry_id == 1
    assert nearest[0].gap_to_user == -5
