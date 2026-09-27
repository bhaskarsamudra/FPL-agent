"""
expected_goals_model.py

Baseline Expected-Goals Model
-----------------------------

Purpose
-------
Estimate expected home goals and expected away goals for a football
fixture using only information available BEFORE kickoff.

This is the first transparent statistical baseline for the FPL Agent.

The model is deliberately simple and auditable.

It does NOT yet use:
    - player-level information
    - injuries
    - suspensions
    - betting odds
    - FPL difficulty
    - LLM judgement
    - external xG/xGI
    - future information
    - arbitrary hand-selected feature weights

Model structure
---------------
For a home team:

    Expected Home Goals
        =
    League Average Home Goals
        ×
    Home Attack Strength
        ×
    Away Defensive Weakness

For an away team:

    Expected Away Goals
        =
    League Average Away Goals
        ×
    Away Attack Strength
        ×
    Home Defensive Weakness

IMPORTANT
---------
The defensive baselines are based on the goals that the OPPONENT
would normally score at that venue.

Therefore:

    Away defensive weakness
        =
    Away goals conceded per match
        /
    League average HOME goals per match

because the away team is defending against the home team's attack.

And:

    Home defensive weakness
        =
    Home goals conceded per match
        /
    League average AWAY goals per match

because the home team is defending against the away team's attack.

Early-season sample sizes are small, so team strengths are shrunk
towards league average.

The shrinkage parameter is configurable and will eventually be
calibrated using historical walk-forward validation.

Important
---------
This module should only receive point-in-time team states.

It must never receive a state containing information from the target
fixture or later fixtures.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any


# ============================================================
# CONSTANTS
# ============================================================

# Initial fallback league-average goals.
#
# These are only fallback values for situations where a league
# average cannot yet be calculated from historical data.
#
# The production historical model should calculate these values
# from the appropriate training data.

DEFAULT_LEAGUE_AVERAGE_HOME_GOALS = 1.50
DEFAULT_LEAGUE_AVERAGE_AWAY_GOALS = 1.20

# Default shrinkage sample size.
#
# This is a MODEL PARAMETER, not a permanent truth.
#
# Historical walk-forward validation will eventually determine
# whether this value should remain 5, become smaller, or become
# larger.

DEFAULT_SHRINKAGE_K = 5.0

# Model version is retained in every prediction so future versions
# can be compared and audited.

MODEL_VERSION = "eg_baseline_v1"


# ============================================================
# DATA STRUCTURE
# ============================================================


@dataclass
class ExpectedGoalsPrediction:
    """
    Store one expected-goals prediction.

    Keeping intermediate components makes every prediction
    auditable.
    """

    home_team: str
    away_team: str

    expected_home_goals: float
    expected_away_goals: float

    league_average_home_goals: float
    league_average_away_goals: float

    home_attack_strength: float
    away_defensive_weakness: float

    away_attack_strength: float
    home_defensive_weakness: float

    home_sample_size: int
    away_sample_size: int

    shrinkage_k: float

    model_version: str


# ============================================================
# BASIC VALIDATION HELPERS
# ============================================================


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Convert a value to a finite float safely.

    Invalid or missing values are replaced by the supplied default.
    """

    try:
        result = float(value)

    except (TypeError, ValueError):
        return default

    if not isfinite(result):
        return default

    return result


def _safe_positive(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Convert a value to a non-negative finite float.

    Quantities such as goals and matches played cannot logically
    be negative.
    """

    result = _safe_float(
        value,
        default,
    )

    return max(
        result,
        0.0,
    )


def _validate_team_state(
    team_state: dict[str, Any] | None,
    team_name: str,
) -> None:
    """
    Validate the minimum team-state structure required by the model.
    """

    if team_state is None:
        raise ValueError(
            f"No point-in-time state is available for team "
            f"'{team_name}'."
        )

    if not isinstance(
        team_state,
        dict,
    ):
        raise TypeError(
            f"Team state for '{team_name}' must be a dictionary."
        )


# ============================================================
# ATTACK STRENGTH
# ============================================================


def _calculate_home_attack_strength(
    team_state: dict[str, Any],
    league_average_home_goals: float,
) -> float:
    """
    Calculate home attacking strength.

    Formula:

        Team home goals per match
        -------------------------
        League average home goals

    Interpretation:

        1.00 = league average
        >1.00 = stronger attack
        <1.00 = weaker attack
    """

    home_goals_per_match = _safe_positive(
        team_state.get(
            "home_goals_per_match"
        )
    )

    if league_average_home_goals <= 0:
        return 1.0

    return (
        home_goals_per_match
        / league_average_home_goals
    )


def _calculate_away_attack_strength(
    team_state: dict[str, Any],
    league_average_away_goals: float,
) -> float:
    """
    Calculate away attacking strength.

    Formula:

        Team away goals per match
        -------------------------
        League average away goals
    """

    away_goals_per_match = _safe_positive(
        team_state.get(
            "away_goals_per_match"
        )
    )

    if league_average_away_goals <= 0:
        return 1.0

    return (
        away_goals_per_match
        / league_average_away_goals
    )


# ============================================================
# DEFENSIVE WEAKNESS
# ============================================================


def _calculate_home_defensive_weakness(
    team_state: dict[str, Any],
    league_average_away_goals: float,
) -> float:
    """
    Calculate home defensive weakness.

    IMPORTANT
    ---------
    A home team is defending against an AWAY attack.

    Therefore the appropriate baseline is the league's average
    AWAY goals per match.

    Formula:

        Home goals conceded per match
        ------------------------------
        League average away goals

    Interpretation:

        1.00 = league-average home defence
        >1.00 = weaker defence
        <1.00 = stronger defence
    """

    home_goals_conceded = _safe_positive(
        team_state.get(
            "home_goals_conceded_per_match"
        )
    )

    if league_average_away_goals <= 0:
        return 1.0

    return (
        home_goals_conceded
        / league_average_away_goals
    )


def _calculate_away_defensive_weakness(
    team_state: dict[str, Any],
    league_average_home_goals: float,
) -> float:
    """
    Calculate away defensive weakness.

    IMPORTANT
    ---------
    An away team is defending against a HOME attack.

    Therefore the appropriate baseline is the league's average
    HOME goals per match.

    Formula:

        Away goals conceded per match
        ------------------------------
        League average home goals

    Interpretation:

        1.00 = league-average away defence
        >1.00 = weaker defence
        <1.00 = stronger defence
    """

    away_goals_conceded = _safe_positive(
        team_state.get(
            "away_goals_conceded_per_match"
        )
    )

    if league_average_home_goals <= 0:
        return 1.0

    return (
        away_goals_conceded
        / league_average_home_goals
    )


# ============================================================
# SAMPLE-SIZE SHRINKAGE
# ============================================================


def shrink_strength(
    observed_strength: float,
    sample_size: int,
    shrinkage_k: float = DEFAULT_SHRINKAGE_K,
) -> float:
    """
    Shrink observed team strength towards league-average strength.

    League-average strength is represented by 1.0.

    Formula:

        weight = sample_size / (sample_size + k)

        shrunk_strength =
            weight * observed_strength
            +
            (1 - weight) * 1.0

    Example with k = 5:

        0 matches  -> 0% observed
        5 matches  -> 50% observed
        10 matches -> 66.7% observed
        20 matches -> 80% observed

    The value of k will eventually be calibrated using historical
    walk-forward validation.
    """

    if shrinkage_k < 0:
        raise ValueError(
            "shrinkage_k cannot be negative."
        )

    sample = max(
        int(sample_size),
        0,
    )

    if shrinkage_k == 0:
        return observed_strength

    weight = (
        sample
        / (
            sample
            + shrinkage_k
        )
    )

    return (
        weight * observed_strength
        + (1.0 - weight) * 1.0
    )


# ============================================================
# LEAGUE AVERAGES
# ============================================================


def calculate_league_averages(
    team_states: list[dict[str, Any]],
) -> dict[str, float]:
    """
    Calculate league-average home and away goals.

    Each team's current home/away scoring rate contributes to the
    corresponding league average.

    This function is useful for historical calibration.

    It does not use the target fixture's actual result.
    """

    home_values: list[float] = []
    away_values: list[float] = []

    for state in team_states:

        if not isinstance(
            state,
            dict,
        ):
            continue

        home_played = _safe_positive(
            state.get(
                "home_played"
            )
        )

        away_played = _safe_positive(
            state.get(
                "away_played"
            )
        )

        home_goals = _safe_positive(
            state.get(
                "home_goals_for"
            )
        )

        away_goals = _safe_positive(
            state.get(
                "away_goals_for"
            )
        )

        if home_played > 0:
            home_values.append(
                home_goals
                / home_played
            )

        if away_played > 0:
            away_values.append(
                away_goals
                / away_played
            )

    home_average = (
        sum(home_values)
        / len(home_values)
        if home_values
        else DEFAULT_LEAGUE_AVERAGE_HOME_GOALS
    )

    away_average = (
        sum(away_values)
        / len(away_values)
        if away_values
        else DEFAULT_LEAGUE_AVERAGE_AWAY_GOALS
    )

    return {
        "home_goals_per_match": home_average,
        "away_goals_per_match": away_average,
    }


# ============================================================
# SINGLE FIXTURE PREDICTION
# ============================================================


def predict_expected_goals(
    home_team: str,
    away_team: str,
    home_team_state: dict[str, Any],
    away_team_state: dict[str, Any],
    league_average_home_goals: float,
    league_average_away_goals: float,
    shrinkage_k: float = DEFAULT_SHRINKAGE_K,
) -> ExpectedGoalsPrediction:
    """
    Predict expected goals for one fixture.

    Only pre-kickoff team states should be supplied.
    """

    # --------------------------------------------------------
    # Validate point-in-time states.
    # --------------------------------------------------------

    _validate_team_state(
        home_team_state,
        home_team,
    )

    _validate_team_state(
        away_team_state,
        away_team,
    )

    # --------------------------------------------------------
    # Calculate raw attack strengths.
    # --------------------------------------------------------

    raw_home_attack = (
        _calculate_home_attack_strength(
            home_team_state,
            league_average_home_goals,
        )
    )

    raw_away_attack = (
        _calculate_away_attack_strength(
            away_team_state,
            league_average_away_goals,
        )
    )

    # --------------------------------------------------------
    # Calculate raw defensive weaknesses.
    #
    # NOTE:
    #
    # Away defence is compared with HOME scoring baseline.
    #
    # Home defence is compared with AWAY scoring baseline.
    # --------------------------------------------------------

    raw_home_defence_weakness = (
        _calculate_home_defensive_weakness(
            home_team_state,
            league_average_away_goals,
        )
    )

    raw_away_defence_weakness = (
        _calculate_away_defensive_weakness(
            away_team_state,
            league_average_home_goals,
        )
    )

    # --------------------------------------------------------
    # Determine sample sizes.
    # --------------------------------------------------------

    home_sample_size = int(
        _safe_positive(
            home_team_state.get(
                "played"
            )
        )
    )

    away_sample_size = int(
        _safe_positive(
            away_team_state.get(
                "played"
            )
        )
    )

    # --------------------------------------------------------
    # Apply sample-size shrinkage.
    #
    # Every component is shrunk independently towards 1.0.
    # --------------------------------------------------------

    home_attack = shrink_strength(
        raw_home_attack,
        home_sample_size,
        shrinkage_k,
    )

    away_attack = shrink_strength(
        raw_away_attack,
        away_sample_size,
        shrinkage_k,
    )

    home_defence_weakness = shrink_strength(
        raw_home_defence_weakness,
        home_sample_size,
        shrinkage_k,
    )

    away_defence_weakness = shrink_strength(
        raw_away_defence_weakness,
        away_sample_size,
        shrinkage_k,
    )

    # --------------------------------------------------------
    # Expected HOME goals.
    #
    # The home team's attack interacts with the away team's
    # defensive weakness.
    # --------------------------------------------------------

    expected_home_goals = (
        league_average_home_goals
        * home_attack
        * away_defence_weakness
    )

    # --------------------------------------------------------
    # Expected AWAY goals.
    #
    # The away team's attack interacts with the home team's
    # defensive weakness.
    # --------------------------------------------------------

    expected_away_goals = (
        league_average_away_goals
        * away_attack
        * home_defence_weakness
    )

    # --------------------------------------------------------
    # Protect against invalid numerical output.
    # --------------------------------------------------------

    expected_home_goals = max(
        _safe_float(
            expected_home_goals
        ),
        0.0,
    )

    expected_away_goals = max(
        _safe_float(
            expected_away_goals
        ),
        0.0,
    )

    # --------------------------------------------------------
    # Return complete auditable prediction.
    # --------------------------------------------------------

    return ExpectedGoalsPrediction(
        home_team=home_team,
        away_team=away_team,

        expected_home_goals=(
            expected_home_goals
        ),

        expected_away_goals=(
            expected_away_goals
        ),

        league_average_home_goals=(
            league_average_home_goals
        ),

        league_average_away_goals=(
            league_average_away_goals
        ),

        home_attack_strength=(
            home_attack
        ),

        away_defensive_weakness=(
            away_defence_weakness
        ),

        away_attack_strength=(
            away_attack
        ),

        home_defensive_weakness=(
            home_defence_weakness
        ),

        home_sample_size=(
            home_sample_size
        ),

        away_sample_size=(
            away_sample_size
        ),

        shrinkage_k=(
            shrinkage_k
        ),

        model_version=(
            MODEL_VERSION
        ),
    )


# ============================================================
# WALK-FORWARD DATASET ADAPTER
# ============================================================


def predict_walk_forward_fixture(
    validation_record: dict[str, Any],
    league_average_home_goals: float,
    league_average_away_goals: float,
    shrinkage_k: float = DEFAULT_SHRINKAGE_K,
) -> dict[str, Any]:
    """
    Convert one walk-forward validation record into an expected-goals
    prediction.

    The validation record comes directly from walk_forward_data.py.

    Actual goals are NOT passed into the prediction calculation.

    They are retained separately only for later evaluation.
    """

    home_state = validation_record.get(
        "home_team_state"
    )

    away_state = validation_record.get(
        "away_team_state"
    )

    # --------------------------------------------------------
    # If one team has no pre-kickoff state, prediction is
    # unavailable.
    #
    # We do NOT invent league-average information.
    # --------------------------------------------------------

    if (
        home_state is None
        or away_state is None
    ):
        return {
            "model_version": MODEL_VERSION,
            "prediction_available": False,

            "match_id": validation_record.get(
                "match_id"
            ),

            "kickoff_datetime": validation_record.get(
                "kickoff_datetime"
            ),

            "home_team": validation_record.get(
                "home_team"
            ),

            "away_team": validation_record.get(
                "away_team"
            ),

            "expected_home_goals": None,
            "expected_away_goals": None,

            "actual_home_goals": validation_record.get(
                "actual_home_goals"
            ),

            "actual_away_goals": validation_record.get(
                "actual_away_goals"
            ),

            "reason": (
                "Point-in-time state unavailable for "
                "one or both teams."
            ),
        }

    # --------------------------------------------------------
    # Make prediction using ONLY pre-kickoff states.
    # --------------------------------------------------------

    prediction = predict_expected_goals(
        home_team=validation_record[
            "home_team"
        ],

        away_team=validation_record[
            "away_team"
        ],

        home_team_state=home_state,
        away_team_state=away_state,

        league_average_home_goals=(
            league_average_home_goals
        ),

        league_average_away_goals=(
            league_average_away_goals
        ),

        shrinkage_k=shrinkage_k,
    )

    # --------------------------------------------------------
    # Convert dataclass to dictionary.
    # --------------------------------------------------------

    return {
        "model_version": (
            prediction.model_version
        ),

        "prediction_available": True,

        "match_id": validation_record[
            "match_id"
        ],

        "kickoff_datetime": validation_record[
            "kickoff_datetime"
        ],

        "home_team": prediction.home_team,
        "away_team": prediction.away_team,

        "expected_home_goals": (
            prediction.expected_home_goals
        ),

        "expected_away_goals": (
            prediction.expected_away_goals
        ),

        "league_average_home_goals": (
            prediction.league_average_home_goals
        ),

        "league_average_away_goals": (
            prediction.league_average_away_goals
        ),

        "home_attack_strength": (
            prediction.home_attack_strength
        ),

        "away_defensive_weakness": (
            prediction.away_defensive_weakness
        ),

        "away_attack_strength": (
            prediction.away_attack_strength
        ),

        "home_defensive_weakness": (
            prediction.home_defensive_weakness
        ),

        "home_sample_size": (
            prediction.home_sample_size
        ),

        "away_sample_size": (
            prediction.away_sample_size
        ),

        "shrinkage_k": (
            prediction.shrinkage_k
        ),

        # Actual result is kept separate from prediction.
        "actual_home_goals": validation_record[
            "actual_home_goals"
        ],

        "actual_away_goals": validation_record[
            "actual_away_goals"
        ],
    }


# ============================================================
# ERROR METRICS
# ============================================================


def calculate_mae(
    actual: list[float],
    predicted: list[float],
) -> float:
    """
    Calculate Mean Absolute Error.

    MAE measures the average absolute prediction error.
    """

    if len(actual) != len(predicted):
        raise ValueError(
            "actual and predicted must have "
            "the same length."
        )

    if not actual:
        raise ValueError(
            "Cannot calculate MAE from an empty dataset."
        )

    errors = [
        abs(
            float(actual_value)
            - float(predicted_value)
        )
        for actual_value, predicted_value
        in zip(
            actual,
            predicted,
        )
    ]

    return (
        sum(errors)
        / len(errors)
    )


def calculate_rmse(
    actual: list[float],
    predicted: list[float],
) -> float:
    """
    Calculate Root Mean Squared Error.

    RMSE penalizes larger errors more heavily than MAE.
    """

    if len(actual) != len(predicted):
        raise ValueError(
            "actual and predicted must have "
            "the same length."
        )

    if not actual:
        raise ValueError(
            "Cannot calculate RMSE from an empty dataset."
        )

    squared_errors = [
        (
            float(actual_value)
            - float(predicted_value)
        ) ** 2
        for actual_value, predicted_value
        in zip(
            actual,
            predicted,
        )
    ]

    mean_squared_error = (
        sum(squared_errors)
        / len(squared_errors)
    )

    return (
        mean_squared_error ** 0.5
    )


def calculate_bias(
    actual: list[float],
    predicted: list[float],
) -> float:
    """
    Calculate mean prediction bias.

    Positive:
        model tends to under-predict.

    Negative:
        model tends to over-predict.

    Definition:

        mean(predicted - actual)
    """

    if len(actual) != len(predicted):
        raise ValueError(
            "actual and predicted must have "
            "the same length."
        )

    if not actual:
        raise ValueError(
            "Cannot calculate bias from an empty dataset."
        )

    errors = [
        float(predicted_value)
        - float(actual_value)
        for actual_value, predicted_value
        in zip(
            actual,
            predicted,
        )
    ]

    return (
        sum(errors)
        / len(errors)
    )


# ============================================================
# MANUAL SANITY CHECK
# ============================================================


if __name__ == "__main__":
    """
    Small standalone mathematical sanity check.

    This does NOT load historical data.

    The purpose is to confirm that the model behaves sensibly
    before connecting it to the 1,900-record walk-forward dataset.
    """

    example_home_state = {
        "played": 10,

        "home_played": 5,
        "home_goals_for": 10.0,
        "home_goals_against": 5.0,

        "home_goals_per_match": 2.0,
        "home_goals_conceded_per_match": 1.0,

        "away_played": 5,
        "away_goals_for": 6.0,
        "away_goals_against": 7.5,

        "away_goals_per_match": 1.2,
        "away_goals_conceded_per_match": 1.5,
    }

    example_away_state = {
        "played": 10,

        "home_played": 5,
        "home_goals_for": 7.5,
        "home_goals_against": 7.5,

        "home_goals_per_match": 1.5,
        "home_goals_conceded_per_match": 1.5,

        "away_played": 5,
        "away_goals_for": 6.0,
        "away_goals_against": 10.0,

        "away_goals_per_match": 1.2,
        "away_goals_conceded_per_match": 2.0,
    }

    prediction = predict_expected_goals(
        home_team="Example Home",
        away_team="Example Away",

        home_team_state=example_home_state,
        away_team_state=example_away_state,

        league_average_home_goals=1.5,
        league_average_away_goals=1.2,

        shrinkage_k=5.0,
    )

    print()
    print("=" * 60)
    print("EXPECTED-GOALS MODEL SANITY CHECK")
    print("=" * 60)

    print(
        f"Fixture: "
        f"{prediction.home_team} "
        f"vs "
        f"{prediction.away_team}"
    )

    print(
        f"Expected home goals: "
        f"{prediction.expected_home_goals:.3f}"
    )

    print(
        f"Expected away goals: "
        f"{prediction.expected_away_goals:.3f}"
    )

    print(
        f"Home attack strength: "
        f"{prediction.home_attack_strength:.3f}"
    )

    print(
        f"Away defensive weakness: "
        f"{prediction.away_defensive_weakness:.3f}"
    )

    print(
        f"Away attack strength: "
        f"{prediction.away_attack_strength:.3f}"
    )

    print(
        f"Home defensive weakness: "
        f"{prediction.home_defensive_weakness:.3f}"
    )

    print(
        f"Model version: "
        f"{prediction.model_version}"
    )