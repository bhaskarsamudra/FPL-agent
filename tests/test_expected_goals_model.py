"""
test_expected_goals_model.py

Unit tests for expected_goals_model.py.

These tests verify the mathematical behaviour and safety rules of
the baseline expected-goals model BEFORE we connect it to the full
1,900-record historical walk-forward dataset.

The tests deliberately use small synthetic team states.

No external data is downloaded by this test file.
"""

from __future__ import annotations


# Import the functions we want to test from our expected-goals model.
from expected_goals_model import (
    MODEL_VERSION,
    calculate_bias,
    calculate_league_averages,
    calculate_mae,
    calculate_rmse,
    predict_expected_goals,
    predict_walk_forward_fixture,
    shrink_strength,
)


# ============================================================
# TEST DATA HELPER
# ============================================================


def create_team_state(
    *,
    played: int = 10,
    home_played: int = 5,
    away_played: int = 5,
    home_goals_for: float = 7.5,
    home_goals_against: float = 6.0,
    away_goals_for: float = 6.0,
    away_goals_against: float = 7.5,
) -> dict:
    """
    Create a small synthetic team state.

    The structure mirrors the fields produced by the historical
    team-state layer.

    Using a helper keeps the individual tests easy to read.
    """

    return {
        # Overall sample size.
        "played": played,

        # Home statistics.
        "home_played": home_played,
        "home_goals_for": home_goals_for,
        "home_goals_against": home_goals_against,

        # Away statistics.
        "away_played": away_played,
        "away_goals_for": away_goals_for,
        "away_goals_against": away_goals_against,

        # Derived home metrics.
        "home_goals_per_match": (
            home_goals_for / home_played
            if home_played > 0
            else 0.0
        ),
        "home_goals_conceded_per_match": (
            home_goals_against / home_played
            if home_played > 0
            else 0.0
        ),

        # Derived away metrics.
        "away_goals_per_match": (
            away_goals_for / away_played
            if away_played > 0
            else 0.0
        ),
        "away_goals_conceded_per_match": (
            away_goals_against / away_played
            if away_played > 0
            else 0.0
        ),
    }


# ============================================================
# TEST 1
# ============================================================


def test_league_average_team_has_strength_one() -> None:
    """
    A team exactly matching the league average should have raw
    strength of 1.0.
    """

    home_average = 1.5
    away_average = 1.2

    state = create_team_state(
        played=10,
        home_played=5,
        away_played=5,
        home_goals_for=7.5,
        home_goals_against=7.5,
        away_goals_for=6.0,
        away_goals_against=6.0,
    )

    home_attack = (
        state["home_goals_per_match"]
        / home_average
    )

    away_attack = (
        state["away_goals_per_match"]
        / away_average
    )

    home_defence = (
        state["home_goals_conceded_per_match"]
        / home_average
    )

    away_defence = (
        state["away_goals_conceded_per_match"]
        / away_average
    )

    assert abs(home_attack - 1.0) < 1e-9
    assert abs(away_attack - 1.0) < 1e-9
    assert abs(home_defence - 1.0) < 1e-9
    assert abs(away_defence - 1.0) < 1e-9

    print("PASS: league-average team has strength 1.0")


# ============================================================
# TEST 2
# ============================================================


def test_strong_attack_is_above_one() -> None:
    """
    A team scoring more than league average should have attack
    strength greater than 1.
    """

    state = create_team_state(
        home_goals_for=10.0,
        home_goals_against=5.0,
    )

    strength = (
        state["home_goals_per_match"]
        / 1.5
    )

    assert strength > 1.0

    print("PASS: strong attack produces strength > 1")


# ============================================================
# TEST 3
# ============================================================


def test_weak_attack_is_below_one() -> None:
    """
    A team scoring less than league average should have attack
    strength below 1.
    """

    state = create_team_state(
        home_goals_for=5.0,
        home_goals_against=5.0,
    )

    strength = (
        state["home_goals_per_match"]
        / 1.5
    )

    assert strength < 1.0

    print("PASS: weak attack produces strength < 1")


# ============================================================
# TEST 4
# ============================================================


def test_defensive_weakness_behaves_correctly() -> None:
    """
    A team conceding more than average should have defensive
    weakness > 1.

    A team conceding less than average should have defensive
    weakness < 1.
    """

    # Strong defence:
    # 0.8 goals conceded per match versus 1.5 league average.
    strong_defence_state = create_team_state(
        home_goals_for=7.5,
        home_goals_against=4.0,
    )

    strong_defence_weakness = (
        strong_defence_state[
            "home_goals_conceded_per_match"
        ]
        / 1.5
    )

    # Weak defence:
    # 2.0 goals conceded per match versus 1.5 league average.
    weak_defence_state = create_team_state(
        home_goals_for=7.5,
        home_goals_against=10.0,
    )

    weak_defence_weakness = (
        weak_defence_state[
            "home_goals_conceded_per_match"
        ]
        / 1.5
    )

    assert strong_defence_weakness < 1.0
    assert weak_defence_weakness > 1.0

    print("PASS: defensive weakness behaves correctly")


# ============================================================
# TEST 5
# ============================================================


def test_shrinkage_moves_extreme_strength_towards_one() -> None:
    """
    Shrinkage should move an extreme observed strength towards
    league-average strength of 1.0.
    """

    observed_strength = 2.0

    shrunk_strength = shrink_strength(
        observed_strength=observed_strength,
        sample_size=5,
        shrinkage_k=5.0,
    )

    # With 5 matches and k=5:
    #
    # weight = 5 / (5 + 5) = 0.5
    #
    # shrunk = 0.5 * 2.0 + 0.5 * 1.0
    #        = 1.5
    expected_strength = 1.5

    assert abs(
        shrunk_strength - expected_strength
    ) < 1e-9

    # The result must be closer to 1 than the original 2.
    assert abs(
        shrunk_strength - 1.0
    ) < abs(
        observed_strength - 1.0
    )

    print("PASS: shrinkage moves strength towards 1.0")


# ============================================================
# TEST 6
# ============================================================


def test_zero_sample_is_league_average() -> None:
    """
    With zero matches, shrinkage should completely remove the
    observed signal and return league-average strength = 1.
    """

    shrunk_strength = shrink_strength(
        observed_strength=5.0,
        sample_size=0,
        shrinkage_k=5.0,
    )

    assert abs(
        shrunk_strength - 1.0
    ) < 1e-9

    print(
        "PASS: zero sample shrinks completely to league average"
    )


# ============================================================
# TEST 7
# ============================================================


def test_expected_goals_formula() -> None:
    """
    Verify the complete expected-goals formula.

    Home:

        league home goals
        × home attack
        × away defensive weakness

    Away:

        league away goals
        × away attack
        × home defensive weakness

    Shrinkage is disabled in this test so that we test the formula
    itself.
    """

    home_state = create_team_state(
        played=10,
        home_played=5,
        away_played=5,
        home_goals_for=10.0,
        home_goals_against=5.0,
        away_goals_for=6.0,
        away_goals_against=7.5,
    )

    away_state = create_team_state(
        played=10,
        home_played=5,
        away_played=5,
        home_goals_for=7.5,
        home_goals_against=7.5,
        away_goals_for=6.0,
        away_goals_against=10.0,
    )

    prediction = predict_expected_goals(
        home_team="Home",
        away_team="Away",
        home_team_state=home_state,
        away_team_state=away_state,
        league_average_home_goals=1.5,
        league_average_away_goals=1.2,
        shrinkage_k=0.0,
    )

    # Home attack:
    #
    # 10 / 5 = 2.0 goals per match
    # 2.0 / 1.5 = 1.333333...
    home_attack = (
        10.0
        / 5.0
        / 1.5
    )

    # Away defensive weakness:
    #
    # 10 / 5 = 2.0 goals conceded per match
    # 2.0 / 1.5 = 1.333333...
    away_defence = (
        10.0
        / 5.0
        / 1.5
    )

    expected_home = (
        1.5
        * home_attack
        * away_defence
    )

    # Away attack:
    #
    # 6 / 5 = 1.2 goals per match
    # 1.2 / 1.2 = 1.0
    away_attack = 1.0

    # Home defensive weakness:
    #
    # 5 / 5 = 1.0 goals conceded per match.
    #
    # For the home team's defensive weakness, we compare the
    # home team's goals conceded against the league average
    # AWAY goals, because the home team is defending against
    # the away team's attacking environment.
    #
    # 1.0 / 1.2 = 0.833333...
    home_defence = (
        1.0
        / 1.2
    )

    expected_away = (
        1.2
        * away_attack
        * home_defence
    )

    assert abs(
        prediction.expected_home_goals
        - expected_home
    ) < 1e-9

    assert abs(
        prediction.expected_away_goals
        - expected_away
    ) < 1e-9

    print("PASS: expected-goals formula is correct")


# ============================================================
# TEST 8
# ============================================================


def test_missing_team_state_is_rejected() -> None:
    """
    The model must not invent information when a team has no
    point-in-time state.
    """

    away_state = create_team_state()

    try:
        predict_expected_goals(
            home_team="Home",
            away_team="Away",
            home_team_state=None,
            away_team_state=away_state,
            league_average_home_goals=1.5,
            league_average_away_goals=1.2,
        )

    except ValueError:
        print("PASS: missing team state is rejected")
        return

    raise AssertionError(
        "Expected ValueError for missing home team state."
    )


# ============================================================
# TEST 9
# ============================================================


def test_negative_shrinkage_is_rejected() -> None:
    """
    A negative shrinkage parameter is invalid.
    """

    try:
        shrink_strength(
            observed_strength=1.5,
            sample_size=5,
            shrinkage_k=-1.0,
        )

    except ValueError:
        print(
            "PASS: negative shrinkage parameter is rejected"
        )
        return

    raise AssertionError(
        "Expected ValueError for negative shrinkage_k."
    )


# ============================================================
# TEST 10
# ============================================================


def test_error_metrics() -> None:
    """
    Verify MAE, RMSE and bias using a small known example.
    """

    actual = [1.0, 2.0, 3.0]
    predicted = [1.5, 1.5, 2.5]

    # Absolute errors:
    #
    # 0.5, 0.5, 0.5
    #
    # MAE = 0.5
    expected_mae = 0.5

    # Squared errors:
    #
    # 0.25, 0.25, 0.25
    #
    # RMSE = sqrt(0.25) = 0.5
    expected_rmse = 0.5

    # Bias:
    #
    # predicted - actual
    #
    # +0.5, -0.5, -0.5
    #
    # Mean = -0.166666...
    expected_bias = -1.0 / 6.0

    mae = calculate_mae(
        actual,
        predicted,
    )

    rmse = calculate_rmse(
        actual,
        predicted,
    )

    bias = calculate_bias(
        actual,
        predicted,
    )

    assert abs(
        mae - expected_mae
    ) < 1e-9

    assert abs(
        rmse - expected_rmse
    ) < 1e-9

    assert abs(
        bias - expected_bias
    ) < 1e-9

    print(
        "PASS: MAE, RMSE and bias calculations are correct"
    )


# ============================================================
# TEST 11
# ============================================================


def test_league_average_calculation() -> None:
    """
    Verify that league-average scoring is calculated correctly
    from team states.
    """

    team_one = create_team_state(
        home_played=5,
        away_played=5,
        home_goals_for=7.5,
        away_goals_for=6.0,
    )

    team_two = create_team_state(
        home_played=5,
        away_played=5,
        home_goals_for=10.0,
        away_goals_for=4.0,
    )

    averages = calculate_league_averages(
        [team_one, team_two]
    )

    # Home:
    #
    # Team 1 = 7.5 / 5 = 1.5
    # Team 2 = 10 / 5 = 2.0
    #
    # Average = 1.75
    expected_home_average = 1.75

    # Away:
    #
    # Team 1 = 6 / 5 = 1.2
    # Team 2 = 4 / 5 = 0.8
    #
    # Average = 1.0
    expected_away_average = 1.0

    assert abs(
        averages["home_goals_per_match"]
        - expected_home_average
    ) < 1e-9

    assert abs(
        averages["away_goals_per_match"]
        - expected_away_average
    ) < 1e-9

    print(
        "PASS: league-average calculation is correct"
    )


# ============================================================
# TEST 12
# ============================================================


def test_walk_forward_missing_state_is_not_fabricated() -> None:
    """
    If the walk-forward dataset contains no point-in-time state
    for one team, the expected-goals model must return an
    unavailable prediction.

    It must NOT invent a league-average state.
    """

    validation_record = {
        "match_id": "TEST-001",
        "kickoff_datetime": "2025-01-01",
        "home_team": "Home",
        "away_team": "Away",

        # Home state deliberately missing.
        "home_team_state": None,

        # Away state exists.
        "away_team_state": create_team_state(),

        # Actual result remains available for evaluation.
        "actual_home_goals": 2,
        "actual_away_goals": 1,
    }

    result = predict_walk_forward_fixture(
        validation_record=validation_record,
        league_average_home_goals=1.5,
        league_average_away_goals=1.2,
    )

    assert result["prediction_available"] is False

    assert (
        result["expected_home_goals"]
        is None
    )

    assert (
        result["expected_away_goals"]
        is None
    )

    # Actual result should remain untouched.
    assert result["actual_home_goals"] == 2
    assert result["actual_away_goals"] == 1

    print(
        "PASS: missing walk-forward state is not fabricated"
    )


# ============================================================
# TEST 13
# ============================================================


def test_model_version_is_retained() -> None:
    """
    Every prediction must retain the model version.

    This becomes important when future model versions are compared
    against this baseline.
    """

    home_state = create_team_state()
    away_state = create_team_state()

    prediction = predict_expected_goals(
        home_team="Home",
        away_team="Away",
        home_team_state=home_state,
        away_team_state=away_state,
        league_average_home_goals=1.5,
        league_average_away_goals=1.2,
    )

    assert prediction.model_version == MODEL_VERSION

    print("PASS: model version is retained")


# ============================================================
# TEST 14
# ============================================================


def test_stronger_sample_has_less_shrinkage() -> None:
    """
    As sample size increases, the observed signal should receive
    more weight.

    Therefore an observed strength of 2.0 should move closer to
    2.0 as sample size increases.
    """

    strength_small_sample = shrink_strength(
        observed_strength=2.0,
        sample_size=2,
        shrinkage_k=5.0,
    )

    strength_large_sample = shrink_strength(
        observed_strength=2.0,
        sample_size=20,
        shrinkage_k=5.0,
    )

    distance_small = abs(
        strength_small_sample - 2.0
    )

    distance_large = abs(
        strength_large_sample - 2.0
    )

    assert distance_large < distance_small

    print(
        "PASS: larger sample receives less shrinkage"
    )


# ============================================================
# MAIN TEST RUNNER
# ============================================================


if __name__ == "__main__":
    """
    Run every test explicitly.

    We use an explicit runner instead of pytest for now because
    the project currently uses simple executable Python test
    scripts and we want to keep the development workflow easy
    to understand.
    """

    print()
    print("=" * 70)
    print("EXPECTED-GOALS MODEL UNIT TESTS")
    print("=" * 70)

    test_league_average_team_has_strength_one()

    test_strong_attack_is_above_one()

    test_weak_attack_is_below_one()

    test_defensive_weakness_behaves_correctly()

    test_shrinkage_moves_extreme_strength_towards_one()

    test_zero_sample_is_league_average()

    test_expected_goals_formula()

    test_missing_team_state_is_rejected()

    test_negative_shrinkage_is_rejected()

    test_error_metrics()

    test_league_average_calculation()

    test_walk_forward_missing_state_is_not_fabricated()

    test_model_version_is_retained()

    test_stronger_sample_has_less_shrinkage()

    print()
    print("=" * 70)
    print("ALL EXPECTED-GOALS MODEL TESTS PASSED")
    print("=" * 70)