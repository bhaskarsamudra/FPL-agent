from future_horizon import build_future_horizon


def test_future_horizon_detects_double_and_blank_teams():
    fixtures = [
        {"gameweek": 11, "fixture_id": 101, "home_team_id": 1, "away_team_id": 2},
        {"gameweek": 11, "fixture_id": 102, "home_team_id": 1, "away_team_id": 3},
        {"gameweek": 11, "fixture_id": 103, "home_team_id": 4, "away_team_id": 5},
        {"gameweek": 12, "fixture_id": 104, "home_team_id": 1, "away_team_id": 2},
    ]
    horizon = build_future_horizon(
        decision_gameweek=10,
        gameweeks=[11, 12],
        fixtures=fixtures,
        known_team_ids=[1, 2, 3, 4, 5, 6],
    )
    gw11 = horizon.opportunities[0]
    assert gw11.total_fixtures == 3
    assert gw11.double_team_count == 1
    assert gw11.blank_team_count == 1
    assert horizon.data_complete is True


def test_future_horizon_requires_future_gameweeks():
    try:
        build_future_horizon(
            decision_gameweek=10,
            gameweeks=[10, 11],
            fixtures=[],
            known_team_ids=[1],
        )
    except ValueError as exc:
        assert "after decision_gameweek" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_future_horizon_flags_missing_fixture_data():
    horizon = build_future_horizon(
        decision_gameweek=10,
        gameweeks=[11],
        fixtures=[],
        known_team_ids=[1, 2],
    )
    assert horizon.data_complete is False
    assert horizon.opportunities[0].data_complete is False
