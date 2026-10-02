from expected_points import expected_points_for_fixture


def make_player(position_id=3):
    return {
        "id": 1,
        "name": "Test Player",
        "position_id": position_id,
        "price": 70,
        "minutes": 450,
        "starts": 5,
        "chance_of_playing_this_round": 100,
        "status": "a",
    }


def test_expected_points_exposes_missing_core_data():
    result = expected_points_for_fixture(
        player=make_player(),
        gameweek=6,
        expected_goals=0.4,
        expected_assists=0.2,
        clean_sheet_probability=None,
        expected_bonus=None,
        expected_defensive_contribution=12,
        bootstrap_data={"element_types": []},
    )

    assert result.expected_points > 0
    assert not result.data_complete
    assert "Clean-sheet probability unavailable." in result.warnings


def test_expected_points_v2_uses_position_specific_inputs():
    result = expected_points_for_fixture(
        player=make_player(),
        gameweek=6,
        expected_goals=0.4,
        expected_assists=0.2,
        clean_sheet_probability=0.5,
        expected_bonus=0.5,
        expected_defensive_contribution=12,
        bootstrap_data={"element_types": []},
    )

    assert result.data_complete
    assert result.expected_minutes == 90.0
    assert result.expected_appearance_points == 2.0
    assert result.expected_defensive_contribution_points > 0
    assert result.expected_points > 0
    assert result.model_version == "xp_v2"


def test_expected_points_accepts_validated_minutes_projection():
    result = expected_points_for_fixture(
        player=make_player(),
        gameweek=6,
        expected_goals=0.4,
        expected_assists=0.2,
        clean_sheet_probability=0.5,
        expected_bonus=0.5,
        expected_defensive_contribution=12,
        bootstrap_data={"element_types": []},
        start_probability=0.5,
        expected_minutes=45.0,
    )

    assert result.expected_minutes == 45.0
    assert result.expected_appearance_points == 0.75
    assert result.expected_points > 0


def test_goalkeeper_v2_uses_saves_and_goals_conceded():
    result = expected_points_for_fixture(
        player=make_player(position_id=1),
        gameweek=6,
        expected_goals=0.1,
        expected_assists=0.0,
        clean_sheet_probability=0.5,
        expected_bonus=0.5,
        expected_saves=4.5,
        expected_goals_conceded=1.0,
        bootstrap_data={"element_types": []},
        start_probability=1.0,
        expected_minutes=90.0,
    )

    assert result.data_complete
    assert result.expected_saves == 4.5
    assert result.expected_goals_conceded_points < 0
    assert result.expected_points > 0
