"""
expected_goals_evaluation.py

Evaluates the baseline expected-goals model against the
historical walk-forward validation dataset.

Purpose
-------
This module connects three existing layers:

    1. Canonical historical match data
    2. Leakage-controlled walk-forward dataset
    3. Baseline expected-goals model

It answers:

    - How accurately does the model predict home goals?
    - How accurately does the model predict away goals?
    - Does the model beat a simple naive benchmark?
    - How does performance vary by historical season/fold?
    - How many fixtures had enough pre-kickoff information
      to make a prediction?

Important
---------
This is an EVALUATION module.

It does NOT:

    - tune model parameters
    - change the model
    - optimize shrinkage
    - use future information
    - use the actual result when making a prediction
    - modify the walk-forward dataset
    - modify the expected-goals model

The first baseline evaluation deliberately uses fixed league-average
goal rates:

    Home = 1.50
    Away = 1.20

This gives us a stable benchmark before introducing additional
calibration decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from expected_goals_model import (
    DEFAULT_LEAGUE_AVERAGE_AWAY_GOALS,
    DEFAULT_LEAGUE_AVERAGE_HOME_GOALS,
    DEFAULT_SHRINKAGE_K,
    MODEL_VERSION,
    calculate_bias,
    calculate_mae,
    calculate_rmse,
    predict_walk_forward_fixture,
)

from historical_team_data import (
    load_historical_team_matches,
)

from walk_forward_data import (
    build_walk_forward_dataset,
    summarize_walk_forward_dataset,
)


# ============================================================
# CONSTANTS
# ============================================================

# ------------------------------------------------------------
# These are the fixed league-average goal rates used for the
# first baseline evaluation.
#
# We deliberately keep them fixed at this stage.
#
# Later, we can test whether historically available league
# averages improve out-of-sample performance.
# ------------------------------------------------------------

BASELINE_LEAGUE_AVERAGE_HOME_GOALS = (
    DEFAULT_LEAGUE_AVERAGE_HOME_GOALS
)

BASELINE_LEAGUE_AVERAGE_AWAY_GOALS = (
    DEFAULT_LEAGUE_AVERAGE_AWAY_GOALS
)


# ============================================================
# DATA STRUCTURES
# ============================================================


@dataclass
class GoalPredictionMetrics:
    """
    Store prediction-quality metrics for one goal target.

    Example
    -------
    For home goals:

        actual = actual home goals
        predicted = expected home goals
    """

    observations: int

    mae: float

    rmse: float

    bias: float


@dataclass
class EvaluationResult:
    """
    Store the complete evaluation result for one dataset slice.

    A slice can represent:

        - the complete historical dataset
        - one validation fold
        - one historical season
    """

    observations: int

    records_available: int

    records_with_predictions: int

    records_without_predictions: int

    home_model: GoalPredictionMetrics

    away_model: GoalPredictionMetrics

    home_naive: GoalPredictionMetrics

    away_naive: GoalPredictionMetrics

    home_mae_improvement_vs_naive: float

    away_mae_improvement_vs_naive: float


# ============================================================
# VALIDATION HELPERS
# ============================================================


def _validate_validation_record(
    record: dict[str, Any],
) -> None:
    """
    Validate the minimum fields required by the evaluator.

    We fail loudly if a record is structurally invalid instead
    of silently producing misleading evaluation numbers.
    """

    if not isinstance(record, dict):
        raise TypeError(
            "Each validation record must be a dictionary."
        )

    required_fields = [
        "match_id",
        "home_team",
        "away_team",
        "actual_home_goals",
        "actual_away_goals",
        "home_team_state",
        "away_team_state",
    ]

    missing_fields = [
        field
        for field in required_fields
        if field not in record
    ]

    if missing_fields:
        raise ValueError(
            "Validation record is missing required fields: "
            f"{missing_fields}"
        )


# ============================================================
# NAIVE BENCHMARK
# ============================================================


def _build_naive_predictions(
    record_count: int,
    home_goals: float,
    away_goals: float,
) -> tuple[list[float], list[float]]:
    """
    Build predictions from a simple naive benchmark.

    The benchmark predicts the same league-average number of
    goals for every fixture.

    This gives us a meaningful baseline:

        Home = 1.50 goals
        Away = 1.20 goals

    The model must beat this benchmark before we consider its
    team-strength signal useful.
    """

    naive_home_predictions = [
        home_goals
        for _ in range(record_count)
    ]

    naive_away_predictions = [
        away_goals
        for _ in range(record_count)
    ]

    return (
        naive_home_predictions,
        naive_away_predictions,
    )


# ============================================================
# SINGLE-SLICE EVALUATION
# ============================================================


def evaluate_validation_records(
    validation_records: list[dict[str, Any]],
    *,
    league_average_home_goals: float = (
        BASELINE_LEAGUE_AVERAGE_HOME_GOALS
    ),
    league_average_away_goals: float = (
        BASELINE_LEAGUE_AVERAGE_AWAY_GOALS
    ),
    shrinkage_k: float = DEFAULT_SHRINKAGE_K,
) -> EvaluationResult:
    """
    Evaluate the expected-goals model on supplied validation records.

    Parameters
    ----------
    validation_records:
        Records produced by build_walk_forward_dataset().

    league_average_home_goals:
        Fixed baseline league-average home goals.

    league_average_away_goals:
        Fixed baseline league-average away goals.

    shrinkage_k:
        Sample-size shrinkage parameter.

    Returns
    -------
    EvaluationResult
        Complete model-versus-naive evaluation.

    Important
    ---------
    Records without both pre-kickoff team states are excluded from
    prediction-quality metrics.

    They are counted separately rather than being fabricated.
    """

    if not isinstance(
        validation_records,
        list,
    ):
        raise TypeError(
            "validation_records must be a list."
        )

    if not validation_records:
        raise ValueError(
            "Cannot evaluate an empty validation dataset."
        )

    # --------------------------------------------------------
    # Store actual values and model predictions.
    # --------------------------------------------------------

    actual_home_goals: list[float] = []

    actual_away_goals: list[float] = []

    model_home_predictions: list[float] = []

    model_away_predictions: list[float] = []

    records_without_predictions = 0

    # --------------------------------------------------------
    # Process every validation fixture.
    # --------------------------------------------------------

    for record in validation_records:

        _validate_validation_record(record)

        # ----------------------------------------------------
        # The expected-goals model deliberately returns an
        # unavailable prediction if either point-in-time state
        # is missing.
        #
        # We do NOT invent information here.
        # ----------------------------------------------------

        prediction = predict_walk_forward_fixture(
            validation_record=record,
            league_average_home_goals=(
                league_average_home_goals
            ),
            league_average_away_goals=(
                league_average_away_goals
            ),
            shrinkage_k=shrinkage_k,
        )

        if not prediction["prediction_available"]:

            records_without_predictions += 1

            continue

        # ----------------------------------------------------
        # Store the actual target separately.
        #
        # These values are used ONLY after the prediction has
        # been generated.
        # ----------------------------------------------------

        actual_home_goals.append(
            float(record["actual_home_goals"])
        )

        actual_away_goals.append(
            float(record["actual_away_goals"])
        )

        # ----------------------------------------------------
        # Store model predictions.
        # ----------------------------------------------------

        model_home_predictions.append(
            float(
                prediction["expected_home_goals"]
            )
        )

        model_away_predictions.append(
            float(
                prediction["expected_away_goals"]
            )
        )

    # --------------------------------------------------------
    # Make sure at least one prediction was possible.
    # --------------------------------------------------------

    records_with_predictions = len(
        actual_home_goals
    )

    if records_with_predictions == 0:
        raise ValueError(
            "No validation records had sufficient "
            "point-in-time state for evaluation."
        )

    # --------------------------------------------------------
    # Build the naive benchmark using the SAME number of
    # evaluable fixtures.
    # --------------------------------------------------------

    (
        naive_home_predictions,
        naive_away_predictions,
    ) = _build_naive_predictions(
        record_count=records_with_predictions,
        home_goals=league_average_home_goals,
        away_goals=league_average_away_goals,
    )

    # --------------------------------------------------------
    # Calculate model metrics.
    # --------------------------------------------------------

    home_model_metrics = GoalPredictionMetrics(
        observations=records_with_predictions,
        mae=calculate_mae(
            actual_home_goals,
            model_home_predictions,
        ),
        rmse=calculate_rmse(
            actual_home_goals,
            model_home_predictions,
        ),
        bias=calculate_bias(
            actual_home_goals,
            model_home_predictions,
        ),
    )

    away_model_metrics = GoalPredictionMetrics(
        observations=records_with_predictions,
        mae=calculate_mae(
            actual_away_goals,
            model_away_predictions,
        ),
        rmse=calculate_rmse(
            actual_away_goals,
            model_away_predictions,
        ),
        bias=calculate_bias(
            actual_away_goals,
            model_away_predictions,
        ),
    )

    # --------------------------------------------------------
    # Calculate naive benchmark metrics.
    # --------------------------------------------------------

    home_naive_metrics = GoalPredictionMetrics(
        observations=records_with_predictions,
        mae=calculate_mae(
            actual_home_goals,
            naive_home_predictions,
        ),
        rmse=calculate_rmse(
            actual_home_goals,
            naive_home_predictions,
        ),
        bias=calculate_bias(
            actual_home_goals,
            naive_home_predictions,
        ),
    )

    away_naive_metrics = GoalPredictionMetrics(
        observations=records_with_predictions,
        mae=calculate_mae(
            actual_away_goals,
            naive_away_predictions,
        ),
        rmse=calculate_rmse(
            actual_away_goals,
            naive_away_predictions,
        ),
        bias=calculate_bias(
            actual_away_goals,
            naive_away_predictions,
        ),
    )

    # --------------------------------------------------------
    # Calculate percentage improvement in MAE.
    #
    # Positive value:
    #     model has lower MAE than naive benchmark.
    #
    # Negative value:
    #     model is worse than naive benchmark.
    # --------------------------------------------------------

    home_mae_improvement = _calculate_mae_improvement(
        naive_mae=home_naive_metrics.mae,
        model_mae=home_model_metrics.mae,
    )

    away_mae_improvement = _calculate_mae_improvement(
        naive_mae=away_naive_metrics.mae,
        model_mae=away_model_metrics.mae,
    )

    return EvaluationResult(
        observations=len(validation_records),
        records_available=len(validation_records),
        records_with_predictions=(
            records_with_predictions
        ),
        records_without_predictions=(
            records_without_predictions
        ),
        home_model=home_model_metrics,
        away_model=away_model_metrics,
        home_naive=home_naive_metrics,
        away_naive=away_naive_metrics,
        home_mae_improvement_vs_naive=(
            home_mae_improvement
        ),
        away_mae_improvement_vs_naive=(
            away_mae_improvement
        ),
    )


# ============================================================
# IMPROVEMENT CALCULATION
# ============================================================


def _calculate_mae_improvement(
    *,
    naive_mae: float,
    model_mae: float,
) -> float:
    """
    Calculate percentage MAE improvement versus naive.

    Formula
    -------

        ((naive MAE - model MAE) / naive MAE) × 100

    Positive:
        model is better.

    Zero:
        model equals naive.

    Negative:
        model is worse.

    If the naive MAE is zero, return 0 because percentage
    improvement is undefined.
    """

    if naive_mae == 0:
        return 0.0

    return (
        (naive_mae - model_mae)
        / naive_mae
        * 100.0
    )


# ============================================================
# FOLD / SEASON FILTERING
# ============================================================


def _filter_by_fold(
    validation_records: list[dict[str, Any]],
    fold_number: int,
) -> list[dict[str, Any]]:
    """
    Return only validation records belonging to one fold.
    """

    return [
        record
        for record in validation_records
        if int(record["fold_number"]) == fold_number
    ]


def _filter_by_season(
    validation_records: list[dict[str, Any]],
    season: str,
) -> list[dict[str, Any]]:
    """
    Return only validation records belonging to one test season.
    """

    return [
        record
        for record in validation_records
        if record["test_season"] == season
    ]


# ============================================================
# COMPLETE HISTORICAL EVALUATION
# ============================================================


def evaluate_complete_walk_forward_dataset(
    validation_records: list[dict[str, Any]],
    *,
    league_average_home_goals: float = (
        BASELINE_LEAGUE_AVERAGE_HOME_GOALS
    ),
    league_average_away_goals: float = (
        BASELINE_LEAGUE_AVERAGE_AWAY_GOALS
    ),
    shrinkage_k: float = DEFAULT_SHRINKAGE_K,
) -> dict[str, Any]:
    """
    Evaluate the complete walk-forward dataset.

    Returns
    -------
    dict
        Contains:

            - overall evaluation
            - fold evaluations
            - season evaluations
            - dataset summary
            - model configuration

    This function is descriptive/evaluative only.

    It does not modify any model parameters.
    """

    # --------------------------------------------------------
    # Overall evaluation.
    # --------------------------------------------------------

    overall = evaluate_validation_records(
        validation_records,
        league_average_home_goals=(
            league_average_home_goals
        ),
        league_average_away_goals=(
            league_average_away_goals
        ),
        shrinkage_k=shrinkage_k,
    )

    # --------------------------------------------------------
    # Determine folds and seasons present in the dataset.
    # --------------------------------------------------------

    fold_numbers = sorted(
        {
            int(record["fold_number"])
            for record in validation_records
        }
    )

    seasons = sorted(
        {
            str(record["test_season"])
            for record in validation_records
        }
    )

    # --------------------------------------------------------
    # Evaluate every fold independently.
    # --------------------------------------------------------

    fold_results: dict[int, EvaluationResult] = {}

    for fold_number in fold_numbers:

        fold_records = _filter_by_fold(
            validation_records,
            fold_number,
        )

        fold_results[fold_number] = (
            evaluate_validation_records(
                fold_records,
                league_average_home_goals=(
                    league_average_home_goals
                ),
                league_average_away_goals=(
                    league_average_away_goals
                ),
                shrinkage_k=shrinkage_k,
            )
        )

    # --------------------------------------------------------
    # Evaluate every historical test season independently.
    # --------------------------------------------------------

    season_results: dict[
        str,
        EvaluationResult,
    ] = {}

    for season in seasons:

        season_records = _filter_by_season(
            validation_records,
            season,
        )

        season_results[season] = (
            evaluate_validation_records(
                season_records,
                league_average_home_goals=(
                    league_average_home_goals
                ),
                league_average_away_goals=(
                    league_average_away_goals
                ),
                shrinkage_k=shrinkage_k,
            )
        )

    # --------------------------------------------------------
    # Keep the existing dataset summary alongside model
    # evaluation metrics.
    # --------------------------------------------------------

    dataset_summary = summarize_walk_forward_dataset(
        validation_records
    )

    return {
        "model_version": MODEL_VERSION,
        "league_average_home_goals": (
            league_average_home_goals
        ),
        "league_average_away_goals": (
            league_average_away_goals
        ),
        "shrinkage_k": shrinkage_k,
        "dataset_summary": dataset_summary,
        "overall": overall,
        "fold_results": fold_results,
        "season_results": season_results,
    }


# ============================================================
# REPORTING HELPERS
# ============================================================


def _print_metric_line(
    label: str,
    metrics: GoalPredictionMetrics,
) -> None:
    """
    Print one compact metric line.
    """

    print(
        f"{label:<18}"
        f"MAE={metrics.mae:.4f}  "
        f"RMSE={metrics.rmse:.4f}  "
        f"Bias={metrics.bias:+.4f}"
    )


def _print_evaluation_block(
    title: str,
    result: EvaluationResult,
) -> None:
    """
    Print a readable evaluation block.
    """

    print()
    print("-" * 70)
    print(title)
    print("-" * 70)

    print(
        f"Records available:      "
        f"{result.records_available}"
    )

    print(
        f"Predictions available:  "
        f"{result.records_with_predictions}"
    )

    print(
        f"Predictions unavailable: "
        f"{result.records_without_predictions}"
    )

    print()
    print("MODEL")

    _print_metric_line(
        "Home goals",
        result.home_model,
    )

    _print_metric_line(
        "Away goals",
        result.away_model,
    )

    print()
    print("NAIVE BENCHMARK")

    _print_metric_line(
        "Home goals",
        result.home_naive,
    )

    _print_metric_line(
        "Away goals",
        result.away_naive,
    )

    print()
    print(
        "MAE improvement vs naive:"
    )

    print(
        f"Home: "
        f"{result.home_mae_improvement_vs_naive:+.2f}%"
    )

    print(
        f"Away: "
        f"{result.away_mae_improvement_vs_naive:+.2f}%"
    )


def print_evaluation_report(
    evaluation: dict[str, Any],
) -> None:
    """
    Print the complete historical evaluation report.
    """

    dataset_summary = evaluation[
        "dataset_summary"
    ]

    overall = evaluation["overall"]

    print()
    print("=" * 70)
    print("EXPECTED-GOALS BASELINE HISTORICAL EVALUATION")
    print("=" * 70)

    print()
    print(
        f"Model version: "
        f"{evaluation['model_version']}"
    )

    print(
        f"Home league average: "
        f"{evaluation['league_average_home_goals']:.2f}"
    )

    print(
        f"Away league average: "
        f"{evaluation['league_average_away_goals']:.2f}"
    )

    print(
        f"Shrinkage k: "
        f"{evaluation['shrinkage_k']:.2f}"
    )

    print()
    print("DATASET")
    print("-" * 70)

    print(
        f"Records: "
        f"{dataset_summary['records']}"
    )

    print(
        f"Folds: "
        f"{dataset_summary['folds']}"
    )

    print(
        f"Test seasons: "
        f"{dataset_summary['test_seasons']}"
    )

    print(
        f"Records by fold: "
        f"{dataset_summary['records_by_fold']}"
    )

    print(
        f"Home states available: "
        f"{dataset_summary['records_with_home_state']}"
    )

    print(
        f"Away states available: "
        f"{dataset_summary['records_with_away_state']}"
    )

    # --------------------------------------------------------
    # Overall evaluation.
    # --------------------------------------------------------

    _print_evaluation_block(
        "OVERALL HISTORICAL PERFORMANCE",
        overall,
    )

    # --------------------------------------------------------
    # Fold-level evaluation.
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("FOLD-BY-FOLD PERFORMANCE")
    print("=" * 70)

    for fold_number, result in (
        evaluation["fold_results"].items()
    ):

        _print_evaluation_block(
            f"Fold {fold_number}",
            result,
        )

    # --------------------------------------------------------
    # Season-level evaluation.
    #
    # Fold and test season correspond one-to-one in our current
    # validation design, but keeping both views makes the report
    # easier to extend later.
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("SEASON-BY-SEASON PERFORMANCE")
    print("=" * 70)

    for season, result in (
        evaluation["season_results"].items()
    ):

        _print_evaluation_block(
            season,
            result,
        )

    print()
    print("=" * 70)
    print("END OF EXPECTED-GOALS EVALUATION")
    print("=" * 70)


# ============================================================
# PUBLIC CONVENIENCE FUNCTION
# ============================================================


def run_complete_expected_goals_evaluation() -> dict[str, Any]:
    """
    Load the canonical historical data, build the leakage-controlled
    walk-forward dataset, evaluate the expected-goals model, and
    return the complete results.

    This is the main function used by the standalone script.
    """

    print(
        "Loading canonical historical team match data..."
    )

    historical_matches = (
        load_historical_team_matches()
    )

    print(
        "Building walk-forward validation dataset..."
    )

    validation_records = (
        build_walk_forward_dataset(
            historical_matches
        )
    )

    print(
        "Evaluating expected-goals baseline..."
    )

    evaluation = (
        evaluate_complete_walk_forward_dataset(
            validation_records
        )
    )

    return evaluation


# ============================================================
# MANUAL RUN
# ============================================================


if __name__ == "__main__":
    """
    Run the complete historical expected-goals evaluation.

    This should produce:

        1. Dataset summary
        2. Overall model performance
        3. Naive benchmark performance
        4. Model-vs-naive comparison
        5. Fold-level performance
        6. Season-level performance

    No model parameters are tuned by this script.
    """

    evaluation = (
        run_complete_expected_goals_evaluation()
    )

    print_evaluation_report(
        evaluation
    )