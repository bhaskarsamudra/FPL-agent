from expected_goals_model import predict_expected_goals
from player_fixture_model import (
    build_fixture_player_projections,
    build_player_fixture_projection,
    clean_sheet_probability,
    aggregate_player_projections,
)


def make_player(player_id, team_id, xg, xa, bonus=10, starts=5):
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
        "bonus": bonus,
        "chance_of_playing_this_round": 100,
        "status": "a",
    }


def make_fixture():
    return {
        "fixture_id": 1001,
        "gameweek": 6,
        "home_team_id": 1,
        "away_team_id": 2,
    }


def test_clean_sheet_probability_is_poisson_zero_goal_probability():
    result = clean_sheet_probability(opponent_expected_goals=1.0)
    assert abs(result - 0.36787944117) < 1e-9


def test_player_xg_and_xa_are_allocated_by_team_share():
    players = [
        make_player(1, 1, 0.6, 0.3),
        make_player(2, 1, 0.4, 0.2),
        make_player(3, 2, 0.5, 0.4),
    ]

    result = build_player_fixture_projection(
        player=players[0],
        players=players,
        fixture=make_fixture(),
        team_expected_goals={1: 2.0, 2: 1.0},
        bootstrap_data={"element_types": []},
    )

    assert abs(result.player_xg_share - 0.6) < 1e-9
    assert abs(result.player_expected_goals - 1.2) < 1e-9
    assert abs(result.player_xa_share - 0.6) < 1e-9
    assert abs(result.player_expected_assists - 0.6) < 1e-9
    assert result.data_complete


def test_team_expected_assists_are_derived_from_current_xa_xg_ratio():
    players = [
        make_player(1, 1, 0.6, 0.3),
        make_player(2, 1, 0.4, 0.1),
        make_player(3, 2, 0.5, 0.4),
    ]

    result = build_player_fixture_projection(
        player=players[0],
        players=players,
        fixture=make_fixture(),
        team_expected_goals={1: 2.0, 2: 1.0},
        bootstrap_data={"element_types": []},
    )

    # Team xA/xG = 0.4/1.0, so expected team assists = 2.0 * 0.4.
    assert abs(result.team_expected_assists - 0.8) < 1e-9
    assert any("xA/xG ratio" in warning for warning in result.warnings)


def test_clean_sheet_probability_uses_opponent_team_xg():
    players = [make_player(1, 1, 0.5, 0.2), make_player(2, 2, 0.5, 0.2)]

    result = build_player_fixture_projection(
        player=players[0],
        players=players,
        fixture=make_fixture(),
        team_expected_goals={1: 1.5, 2: 0.8},
        bootstrap_data={"element_types": []},
    )

    assert abs(result.clean_sheet_probability - __import__("math").exp(-0.8)) < 1e-9


def test_missing_team_player_xg_is_degraded_not_fabricated():
    players = [
        make_player(1, 1, 0.0, 0.0),
        make_player(2, 2, 0.5, 0.2),
    ]

    result = build_player_fixture_projection(
        player=players[0],
        players=players,
        fixture=make_fixture(),
        team_expected_goals={1: 1.5, 2: 0.8},
        bootstrap_data={"element_types": []},
    )

    assert result.data_complete is False
    assert result.player_expected_goals == 0.0
    assert result.player_expected_assists == 0.0
    assert any("no usable expected_goals" in warning for warning in result.warnings)


def test_expected_points_increases_with_team_expected_goals_for_same_player():
    players = [
        make_player(1, 1, 0.6, 0.3),
        make_player(2, 1, 0.4, 0.2),
        make_player(3, 2, 0.5, 0.4),
    ]

    low = build_player_fixture_projection(
        player=players[0],
        players=players,
        fixture=make_fixture(),
        team_expected_goals={1: 1.0, 2: 1.2},
        bootstrap_data={"element_types": []},
    )

    high = build_player_fixture_projection(
        player=players[0],
        players=players,
        fixture=make_fixture(),
        team_expected_goals={1: 2.0, 2: 1.2},
        bootstrap_data={"element_types": []},
    )

    assert high.expected_points > low.expected_points


def test_all_fixture_players_are_projected():
    players = [
        make_player(1, 1, 0.6, 0.3),
        make_player(2, 1, 0.4, 0.2),
        make_player(3, 2, 0.5, 0.4),
        make_player(4, 3, 1.0, 0.5),
    ]

    results = build_fixture_player_projections(
        players=players,
        fixture=make_fixture(),
        team_expected_goals={1: 2.0, 2: 1.0},
        bootstrap_data={"element_types": []},
    )

    assert [row.player_id for row in results] == [1, 2, 3]


def test_multi_fixture_aggregation_sums_expected_points():
    players = [
        make_player(1, 1, 0.6, 0.3),
        make_player(2, 1, 0.4, 0.2),
        make_player(3, 2, 0.5, 0.4),
    ]

    fixture_one = make_fixture()
    fixture_two = {
        "fixture_id": 1002,
        "gameweek": 7,
        "home_team_id": 2,
        "away_team_id": 1,
    }

    rows = build_fixture_player_projections(
        players=players,
        fixture=fixture_one,
        team_expected_goals={1: 2.0, 2: 1.0},
        bootstrap_data={"element_types": []},
    ) + build_fixture_player_projections(
        players=players,
        fixture=fixture_two,
        team_expected_goals={1: 1.2, 2: 1.6},
        bootstrap_data={"element_types": []},
    )

    aggregated = aggregate_player_projections(rows)

    player_one = aggregated[1]
    expected = sum(row.expected_points for row in rows if row.player_id == 1)

    assert abs(player_one["expected_points"] - expected) < 1e-9
    assert len(player_one["fixtures"]) == 2


def test_existing_expected_goals_model_can_feed_team_expectations():
    home_state = {
        "played": 10,
        "home_goals_per_match": 2.0,
        "home_goals_conceded_per_match": 1.0,
    }
    away_state = {
        "played": 10,
        "away_goals_per_match": 1.2,
        "away_goals_conceded_per_match": 2.0,
    }

    prediction = predict_expected_goals(
        home_team="Home",
        away_team="Away",
        home_team_state=home_state,
        away_team_state=away_state,
        league_average_home_goals=1.5,
        league_average_away_goals=1.2,
        shrinkage_k=0.0,
    )

    assert prediction.expected_home_goals > 0
    assert prediction.expected_away_goals > 0


def test_projection_keeps_model_version():
    players = [make_player(1, 1, 0.6, 0.3), make_player(2, 2, 0.5, 0.4)]

    result = build_player_fixture_projection(
        player=players[0],
        players=players,
        fixture=make_fixture(),
        team_expected_goals={1: 1.5, 2: 1.0},
        bootstrap_data={"element_types": []},
    )

    assert result.model_version == "player_fixture_xp_v1"


def test_projection_exposes_batch9_start_probability():
    players = [
        make_player(1, 1, 0.6, 0.3, starts=5),
        make_player(2, 1, 0.4, 0.2, starts=5),
        make_player(3, 2, 0.5, 0.4, starts=5),
    ]

    result = build_player_fixture_projection(
        player=players[0],
        players=players,
        fixture=make_fixture(),
        team_expected_goals={1: 2.0, 2: 1.0},
        bootstrap_data={"element_types": []},
    )

    assert result.start_probability == 1.0
    assert result.expected_minutes == 90.0


def test_projection_respects_player_availability_probability():
    players = [
        make_player(1, 1, 0.6, 0.3),
        make_player(2, 1, 0.4, 0.2),
        make_player(3, 2, 0.5, 0.4),
    ]
    players[0]["chance_of_playing_this_round"] = 50

    result = build_player_fixture_projection(
        player=players[0],
        players=players,
        fixture=make_fixture(),
        team_expected_goals={1: 2.0, 2: 1.0},
        bootstrap_data={"element_types": []},
    )

    assert result.start_probability == 0.5
    assert result.expected_minutes == 45.0
