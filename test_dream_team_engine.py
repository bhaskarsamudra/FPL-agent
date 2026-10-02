from dream_team_engine import (
    compare_gameweek_dream_team,
    compare_season_dream_team,
    parse_dream_team,
)


def test_parse_gameweek_dream_team():
    snapshot = parse_dream_team(
        {
            "team": [
                {"element": 1, "points": 12, "position": 1},
                {"element": 2, "points": 15, "position": 2},
            ],
            "top_player": {"element": 2, "points": 15},
        },
        scope="gameweek",
        gameweek=6,
        source_endpoint="dream-team/6/",
    )

    assert snapshot.total_points == 27
    assert snapshot.top_player_id == 2
    assert snapshot.data_complete


def test_gameweek_dream_team_gap_is_outcome_only():
    snapshot = parse_dream_team(
        {"team": [{"element": 1, "points": 12}, {"element": 2, "points": 15}]},
        scope="gameweek",
        gameweek=6,
        source_endpoint="dream-team/6/",
    )
    gap = compare_gameweek_dream_team(
        snapshot=snapshot,
        our_points=20,
        our_player_ids=[1, 3, 4],
    )

    assert gap.total_gap == 7
    assert gap.overlap_player_ids == (1,)
    assert gap.missed_player_ids == (2,)


def test_season_dream_team_gap_requires_same_point_in_time_reference():
    snapshot = parse_dream_team(
        {"team": [{"element": 1, "points": 80}, {"element": 2, "points": 75}]},
        scope="season_to_date",
        gameweek=None,
        source_endpoint="dream-team/",
    )
    gap = compare_season_dream_team(
        snapshot=snapshot,
        our_reference_points=130,
        our_player_ids=[1, 3],
    )

    assert gap.total_gap == 25
    assert gap.overlap_player_ids == (1,)
