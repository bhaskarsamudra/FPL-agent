from production_projection import build_production_projections


def make_player(player_id, team_id, xg, xa, starts=5):
    return {
        "id": player_id,
        "name": f"Player {player_id}",
        "team_id": team_id,
        "position_id": 3,
        "price": 70,
        "minutes": starts * 90,
        "starts": starts,
        "expected_goals": xg,
        "expected_assists": xa,
        "bonus": 5,
        "defensive_contribution": 12,
        "chance_of_playing_this_round": 100,
        "status": "a",
    }


def make_fixtures():
    return [
        {
            "fixture_id": 1,
            "gameweek": 1,
            "finished": True,
            "home_team_id": 1,
            "away_team_id": 2,
            "home_team": "Home FC",
            "away_team": "Away FC",
            "home_score": 2,
            "away_score": 0,
        },
        {
            "fixture_id": 2,
            "gameweek": 2,
            "finished": True,
            "home_team_id": 2,
            "away_team_id": 1,
            "home_team": "Away FC",
            "away_team": "Home FC",
            "home_score": 1,
            "away_score": 1,
        },
        {
            "fixture_id": 3,
            "gameweek": 6,
            "finished": False,
            "home_team_id": 1,
            "away_team_id": 2,
            "home_team": "Home FC",
            "away_team": "Away FC",
            "home_difficulty": 3,
            "away_difficulty": 3,
        },
        {
            "fixture_id": 4,
            "gameweek": 7,
            "finished": False,
            "home_team_id": 2,
            "away_team_id": 1,
            "home_team": "Away FC",
            "away_team": "Home FC",
            "home_difficulty": 3,
            "away_difficulty": 3,
        },
    ]


def test_production_projection_builds_multi_gw_player_projections():
    players = [
        make_player(1, 1, 0.6, 0.3),
        make_player(2, 2, 0.5, 0.2),
    ]

    result = build_production_projections(
        players=players,
        fixtures=make_fixtures(),
        target_gameweek=6,
        horizon_gameweeks=[6, 7],
        bootstrap_data={"element_types": []},
    )

    assert result.data_complete
    assert set(result.projections) == {1, 2}
    assert all(
        len(row["fixtures"]) == 2
        for row in result.projections.values()
    )
    assert all(
        row["projection_complete"]
        and row["horizon_expected_points"] == row["expected_points"]
        for row in result.projections.values()
    )
    assert all(
        row["horizon_expected_points"] > 0
        for row in result.projections.values()
    )


def test_production_projection_uses_only_pre_target_completed_fixtures():
    players = [
        make_player(1, 1, 0.6, 0.3),
        make_player(2, 2, 0.5, 0.2),
    ]
    fixtures = make_fixtures()
    fixtures.append(
        {
            "fixture_id": 99,
            "gameweek": 7,
            "finished": True,
            "home_team_id": 1,
            "away_team_id": 2,
            "home_team": "Home FC",
            "away_team": "Away FC",
            "home_score": 99,
            "away_score": 0,
        }
    )

    baseline = build_production_projections(
        players=players,
        fixtures=make_fixtures(),
        target_gameweek=6,
        horizon_gameweeks=[6],
        bootstrap_data={"element_types": []},
    )
    contaminated = build_production_projections(
        players=players,
        fixtures=fixtures,
        target_gameweek=6,
        horizon_gameweeks=[6],
        bootstrap_data={"element_types": []},
    )

    assert baseline.team_expected_goals == contaminated.team_expected_goals


def test_future_finished_fixture_is_not_used_as_forecast_input():
    players = [
        make_player(1, 1, 0.6, 0.3),
        make_player(2, 2, 0.5, 0.2),
    ]
    fixtures = make_fixtures()
    fixtures[2]["finished"] = True
    fixtures[2]["home_score"] = 5
    fixtures[2]["away_score"] = 0

    result = build_production_projections(
        players=players,
        fixtures=fixtures,
        target_gameweek=6,
        horizon_gameweeks=[6, 7],
        bootstrap_data={"element_types": []},
    )

    assert result.data_complete
    assert all(
        projection.gameweek == 7
        for projection in result.fixture_projections
    )


def test_double_gameweek_fixtures_are_aggregated():
    players = [
        make_player(1, 1, 0.6, 0.3),
        make_player(2, 2, 0.5, 0.2),
    ]
    fixtures = make_fixtures()
    fixtures.extend(
        [
            {
                "fixture_id": 5,
                "gameweek": 6,
                "finished": False,
                "home_team_id": 1,
                "away_team_id": 2,
                "home_team": "Home FC",
                "away_team": "Away FC",
            },
            {
                "fixture_id": 6,
                "gameweek": 6,
                "finished": False,
                "home_team_id": 2,
                "away_team_id": 1,
                "home_team": "Away FC",
                "away_team": "Home FC",
            },
        ]
    )

    result = build_production_projections(
        players=players,
        fixtures=fixtures,
        target_gameweek=6,
        horizon_gameweeks=[6],
        bootstrap_data={"element_types": []},
    )

    assert result.data_complete
    assert len(result.projections[1]["fixtures"]) == 3


def test_missing_pre_target_team_state_blocks_complete_projection():
    players = [
        make_player(1, 1, 0.6, 0.3),
        make_player(2, 2, 0.5, 0.2),
        make_player(3, 3, 0.4, 0.2),
    ]
    fixtures = make_fixtures()
    fixtures.append(
        {
            "fixture_id": 7,
            "gameweek": 6,
            "finished": False,
            "home_team_id": 3,
            "away_team_id": 1,
            "home_team": "New FC",
            "away_team": "Home FC",
        }
    )

    result = build_production_projections(
        players=players,
        fixtures=fixtures,
        target_gameweek=6,
        horizon_gameweeks=[6],
        bootstrap_data={"element_types": []},
    )

    assert not result.data_complete
    assert any("No point-in-time team state" in warning for warning in result.warnings)
    assert set(result.projections) == {1, 2}


def test_projection_rejects_horizon_not_starting_at_target_gameweek():
    players = [make_player(1, 1, 0.6, 0.3)]

    try:
        build_production_projections(
            players=players,
            fixtures=make_fixtures(),
            target_gameweek=6,
            horizon_gameweeks=[7, 8],
            bootstrap_data={"element_types": []},
        )
    except ValueError as exc:
        assert "first horizon Gameweek" in str(exc)
    else:
        raise AssertionError("Expected ValueError was not raised.")
