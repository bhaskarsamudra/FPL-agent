from expected_points import expected_points_for_fixture


def make_player():
    return {
        "id": 1,
        "name": "Test Player",
        "position_id": 3,
        "price": 70,
        "minutes": 450,
        "starts": 5,
        "chance_of_playing_this_round": 100,
        "status": "a",
    }


def test_expected_points_exposes_missing_data():
    result = expected_points_for_fixture(
        player=make_player(),
        gameweek=6,
        expected_goals=0.4,
        expected_assists=0.2,
        clean_sheet_probability=None,
        expected_bonus=None,
        bootstrap_data={"element_types": []},
    )

    assert result.expected_points > 0
    assert not result.data_complete
    assert "Clean-sheet probability unavailable." in result.warnings


def test_expected_points_uses_supplied_probabilities():
    result = expected_points_for_fixture(
        player=make_player(),
        gameweek=6,
        expected_goals=0.4,
        expected_assists=0.2,
        clean_sheet_probability=0.5,
        expected_bonus=0.5,
        bootstrap_data={"element_types": []},
    )

    assert result.data_complete
    assert result.expected_minutes == 90.0
    assert result.expected_points > 0


def test_expected_points_accepts_validated_minutes_projection():
    result = expected_points_for_fixture(
        player=make_player(),
        gameweek=6,
        expected_goals=0.4,
        expected_assists=0.2,
        clean_sheet_probability=0.5,
        expected_bonus=0.5,
        bootstrap_data={"element_types": []},
        start_probability=0.5,
        expected_minutes=45.0,
    )

    assert result.expected_minutes == 45.0
    assert result.expected_points > 0
