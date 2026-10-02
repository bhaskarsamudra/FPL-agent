from player_minutes_model import (
    MODEL_VERSION,
    project_player_minutes,
    project_player_minutes_batch,
)


def make_player(**overrides):
    player = {
        "id": 1,
        "minutes": 900,
        "starts": 10,
        "chance_of_playing_this_round": 100,
        "status": "a",
    }
    player.update(overrides)
    return player


def test_regular_starter_gets_full_start_probability():
    result = project_player_minutes(player=make_player())

    assert result.start_probability == 1.0
    assert result.expected_minutes == 90.0
    assert result.availability_probability == 1.0
    assert result.data_complete


def test_doubtful_player_is_capped_by_official_chance():
    result = project_player_minutes(
        player=make_player(
            chance_of_playing_this_round=50,
        )
    )

    assert result.start_probability == 0.5
    assert result.expected_minutes == 45.0


def test_injured_player_gets_zero_expected_minutes():
    result = project_player_minutes(
        player=make_player(
            status="i",
            chance_of_playing_this_round=75,
        )
    )

    assert result.start_probability == 0.0
    assert result.expected_minutes == 0.0
    assert any("blocks expected minutes" in w for w in result.warnings)


def test_minutes_without_starts_are_not_promoted_to_starter():
    result = project_player_minutes(
        player=make_player(
            minutes=180,
            starts=0,
        )
    )

    assert result.start_probability == 0.0
    assert result.expected_minutes == 0.0
    assert result.data_complete


def test_missing_starting_evidence_is_degraded_not_invented():
    result = project_player_minutes(
        player=make_player(
            minutes=None,
            starts=None,
        )
    )

    assert result.data_complete is False
    assert result.start_probability == 0.0
    assert result.expected_minutes == 0.0
    assert any("Starting evidence unavailable" in w for w in result.warnings)


def test_null_fpl_chance_means_no_specific_availability_restriction():
    result = project_player_minutes(
        player=make_player(
            chance_of_playing_this_round=None,
        )
    )

    assert result.availability_probability == 1.0
    assert result.start_probability == 1.0
    assert result.data_complete


def test_model_version_is_explicit():
    result = project_player_minutes(player=make_player())

    assert result.model_version == MODEL_VERSION


def test_batch_returns_player_id_lookup():
    result = project_player_minutes_batch(
        [
            make_player(id=1),
            make_player(id=2, starts=5, minutes=450),
        ]
    )

    assert set(result) == {1, 2}
    assert result[2].expected_minutes == 90.0
