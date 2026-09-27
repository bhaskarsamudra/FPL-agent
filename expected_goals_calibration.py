"""
Leakage-safe calibration for the baseline expected-goals model.

Purpose
-------
This module selects the sample-size shrinkage parameter K using only
historical folds that occur BEFORE the fold being tested.

The key rule is:

    Earlier folds -> calibrate K -> current fold -> evaluate

The current held-out fold is NEVER used to select its own K.

This module does not change the expected-goals model itself.
It only determines which shrinkage parameter should be supplied to it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from expected_goals_evaluation import (
    EvaluationResult,
    evaluate_validation_records,
)

from expected_goals_model import (
    DEFAULT_LEAGUE_AVERAGE_AWAY_GOALS,
    DEFAULT_LEAGUE_AVERAGE_HOME_GOALS,
    DEFAULT_SHRINKAGE_K,
)

from historical_team_data import (
    load_historical_team_matches,
)

from walk_forward_data import (
    build_walk_forward_dataset,
)


# ============================================================
# CALIBRATION CONFIGURATION
# ============================================================

# Candidate K values are deliberately explicit and transparent.
#
# K controls how strongly small samples are shrunk toward
# neutral team strength = 1.0.
#
# K = 0 means no shrinkage.
# Larger K means stronger shrinkage for small samples.
# Candidate shrinkage values used during historical calibration.
#
# The broader search established that K=20 was selected repeatedly.
# We now use a finer grid around that region to understand whether
# the calibration objective has a clear minimum near K=20.
DEFAULT_CANDIDATE_K_VALUES = (
    0.0,
    1.0,
    2.0,
    3.0,
    5.0,
    7.5,
    10.0,
    12.0,
    14.0,
    16.0,
    18.0,
    19.0,
    20.0,
    21.0,
    22.0,
    24.0,
    26.0,
    28.0,
    30.0,
    40.0,
    50.0,
)


# ============================================================
# DATA STRUCTURES
# ============================================================


@dataclass(frozen=True)
class CalibrationSelection:
    """
    Store the K-selection result for one held-out fold.

    A fold either:

    1. uses the default K because no earlier fold exists, or
    2. selects K using only earlier folds.
    """

    fold_number: int

    test_season: str

    calibration_folds: tuple[int, ...]

    calibration_observations: int

    selected_k: float

    selection_method: str

    calibration_score: float | None

    held_out_evaluation: EvaluationResult


@dataclass(frozen=True)
class CalibrationResult:
    """
    Store the complete leakage-safe calibration experiment.
    """

    candidate_k_values: tuple[float, ...]

    fold_results: tuple[CalibrationSelection, ...]

    default_k: float


# ============================================================
# VALIDATION HELPERS
# ============================================================


def _validate_candidate_k_values(
    candidate_k_values: tuple[float, ...],
) -> None:
    """
    Validate the candidate shrinkage values.

    K must never be negative because the underlying shrinkage
    implementation rejects negative values.
    """

    if not candidate_k_values:
        raise ValueError(
            "candidate_k_values must contain at least one value."
        )

    for k in candidate_k_values:

        if not isinstance(k, (int, float)):
            raise TypeError(
                "Every candidate K must be numeric."
            )

        if k < 0:
            raise ValueError(
                f"Candidate K cannot be negative: {k}"
            )


def _validate_validation_records(
    validation_records: list[dict[str, Any]],
) -> None:
    """
    Validate the top-level walk-forward dataset.
    """

    if not isinstance(validation_records, list):
        raise TypeError(
            "validation_records must be a list."
        )

    if not validation_records:
        raise ValueError(
            "validation_records cannot be empty."
        )

    required_fields = {
        "fold_number",
        "test_season",
        "actual_home_goals",
        "actual_away_goals",
        "home_team_state",
        "away_team_state",
    }

    for record in validation_records:

        if not isinstance(record, dict):
            raise TypeError(
                "Every validation record must be a dictionary."
            )

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
# FOLD HELPERS
# ============================================================


def _get_fold_numbers(
    validation_records: list[dict[str, Any]],
) -> list[int]:
    """
    Return fold numbers in chronological order.
    """

    return sorted(
        {
            int(record["fold_number"])
            for record in validation_records
        }
    )


def _get_fold_records(
    validation_records: list[dict[str, Any]],
    fold_number: int,
) -> list[dict[str, Any]]:
    """
    Return all validation records belonging to one fold.
    """

    return [
        record
        for record in validation_records
        if int(record["fold_number"]) == fold_number
    ]


def _get_test_season(
    fold_records: list[dict[str, Any]],
) -> str:
    """
    Return the test season represented by a fold.

    A fold must contain exactly one test season.
    """

    seasons = {
        str(record["test_season"])
        for record in fold_records
    }

    if len(seasons) != 1:
        raise ValueError(
            "Each fold must contain exactly one test season."
        )

    return next(iter(seasons))


# ============================================================
# CALIBRATION OBJECTIVE
# ============================================================


def _calculate_calibration_score(
    evaluation: EvaluationResult,
) -> float:
    """
    Calculate the objective used to select K.

    We use the mean of home-goal MAE and away-goal MAE.

    This keeps the objective:

        - transparent
        - symmetric between home and away goals
        - directly tied to prediction error

    Lower is better.
    """

    return (
        evaluation.home_model.mae
        + evaluation.away_model.mae
    ) / 2.0


# ============================================================
# K SELECTION
# ============================================================


def select_best_shrinkage_k(
    calibration_records: list[dict[str, Any]],
    *,
    candidate_k_values: tuple[float, ...] = (
        DEFAULT_CANDIDATE_K_VALUES
    ),
    league_average_home_goals: float = (
        DEFAULT_LEAGUE_AVERAGE_HOME_GOALS
    ),
    league_average_away_goals: float = (
        DEFAULT_LEAGUE_AVERAGE_AWAY_GOALS
    ),
) -> tuple[float, float]:
    """
    Select the K value with the lowest calibration error.

    IMPORTANT
    ---------
    This function must only receive records that occur BEFORE
    the held-out test fold.

    It has no knowledge of the future test fold.

    Returns
    -------
    tuple[float, float]
        Selected K and its calibration score.
    """

    _validate_candidate_k_values(
        candidate_k_values
    )

    if not calibration_records:
        raise ValueError(
            "Cannot select K without calibration records."
        )

    best_k: float | None = None
    best_score: float | None = None

    for candidate_k in candidate_k_values:

        evaluation = evaluate_validation_records(
            calibration_records,
            league_average_home_goals=(
                league_average_home_goals
            ),
            league_average_away_goals=(
                league_average_away_goals
            ),
            shrinkage_k=float(candidate_k),
        )

        score = _calculate_calibration_score(
            evaluation
        )

        # ----------------------------------------------------
        # Lower prediction error is better.
        #
        # If two K values have exactly the same score,
        # prefer the smaller K.
        #
        # This gives us a deterministic tie-breaker.
        # ----------------------------------------------------

        if (
            best_score is None
            or score < best_score
            or (
                score == best_score
                and (
                    best_k is None
                    or float(candidate_k) < best_k
                )
            )
        ):
            best_k = float(candidate_k)
            best_score = float(score)

    if best_k is None or best_score is None:
        raise RuntimeError(
            "Unable to select a shrinkage K."
        )

    return best_k, best_score


# ============================================================
# LEAKAGE-SAFE WALK-FORWARD CALIBRATION
# ============================================================


def calibrate_walk_forward_shrinkage(
    validation_records: list[dict[str, Any]],
    *,
    candidate_k_values: tuple[float, ...] = (
        DEFAULT_CANDIDATE_K_VALUES
    ),
    default_k: float = DEFAULT_SHRINKAGE_K,
    league_average_home_goals: float = (
        DEFAULT_LEAGUE_AVERAGE_HOME_GOALS
    ),
    league_average_away_goals: float = (
        DEFAULT_LEAGUE_AVERAGE_AWAY_GOALS
    ),
) -> CalibrationResult:
    """
    Perform leakage-safe walk-forward calibration.

    Fold N is evaluated using a K selected ONLY from folds
    1 through N-1.

    The first fold has no historical calibration fold available,
    so it uses the documented default K.

    Example
    -------
    Fold 1:
        K = default K

    Fold 2:
        calibrate using Fold 1
        test using selected K

    Fold 3:
        calibrate using Folds 1 + 2
        test using selected K

    And so on.

    The held-out fold is never included in K selection.
    """

    _validate_validation_records(
        validation_records
    )

    _validate_candidate_k_values(
        candidate_k_values
    )

    if default_k < 0:
        raise ValueError(
            "default_k cannot be negative."
        )

    fold_numbers = _get_fold_numbers(
        validation_records
    )

    fold_results: list[CalibrationSelection] = []

    # --------------------------------------------------------
    # Process each fold chronologically.
    # --------------------------------------------------------

    for fold_number in fold_numbers:

        current_fold_records = _get_fold_records(
            validation_records,
            fold_number,
        )

        test_season = _get_test_season(
            current_fold_records
        )

        # ----------------------------------------------------
        # Earlier folds are the ONLY allowed calibration data.
        # ----------------------------------------------------

        earlier_fold_numbers = [
            number
            for number in fold_numbers
            if number < fold_number
        ]

        calibration_records: list[
            dict[str, Any]
        ] = []

        for earlier_fold_number in earlier_fold_numbers:

            calibration_records.extend(
                _get_fold_records(
                    validation_records,
                    earlier_fold_number,
                )
            )

        # ----------------------------------------------------
        # First fold:
        #
        # There is no earlier data available, so use the
        # predefined baseline K.
        # ----------------------------------------------------

        if not calibration_records:

            selected_k = float(default_k)

            calibration_score = None

            selection_method = (
                "default_no_prior_fold"
            )

        # ----------------------------------------------------
        # Later folds:
        #
        # Select K using ONLY earlier folds.
        # ----------------------------------------------------

        else:

            (
                selected_k,
                calibration_score,
            ) = select_best_shrinkage_k(
                calibration_records,
                candidate_k_values=(
                    candidate_k_values
                ),
                league_average_home_goals=(
                    league_average_home_goals
                ),
                league_average_away_goals=(
                    league_average_away_goals
                ),
            )

            selection_method = (
                "expanding_prior_folds"
            )

        # ----------------------------------------------------
        # Evaluate the current fold ONLY AFTER K has been
        # selected.
        #
        # Therefore the current fold remains genuinely held
        # out from the calibration process.
        # ----------------------------------------------------

        held_out_evaluation = (
            evaluate_validation_records(
                current_fold_records,
                league_average_home_goals=(
                    league_average_home_goals
                ),
                league_average_away_goals=(
                    league_average_away_goals
                ),
                shrinkage_k=selected_k,
            )
        )

        fold_results.append(
            CalibrationSelection(
                fold_number=fold_number,
                test_season=test_season,
                calibration_folds=tuple(
                    earlier_fold_numbers
                ),
                calibration_observations=len(
                    calibration_records
                ),
                selected_k=selected_k,
                selection_method=selection_method,
                calibration_score=calibration_score,
                held_out_evaluation=(
                    held_out_evaluation
                ),
            )
        )

    return CalibrationResult(
        candidate_k_values=tuple(
            float(k)
            for k in candidate_k_values
        ),
        fold_results=tuple(
            fold_results
        ),
        default_k=float(default_k),
    )


# ============================================================
# REPORTING
# ============================================================


def print_calibration_report(
    result: CalibrationResult,
) -> None:
    """
    Print a concise human-readable calibration report.
    """

    print()
    print("=" * 72)
    print(
        "EXPECTED-GOALS WALK-FORWARD CALIBRATION"
    )
    print("=" * 72)

    print()
    print(
        "Candidate K values:",
        result.candidate_k_values,
    )

    print(
        "Default K:",
        result.default_k,
    )

    print()

    for fold_result in result.fold_results:

        evaluation = (
            fold_result.held_out_evaluation
        )

        print("-" * 72)

        print(
            f"Fold {fold_result.fold_number} "
            f"| Test season: {fold_result.test_season}"
        )

        print(
            "Calibration folds:",
            (
                fold_result.calibration_folds
                if fold_result.calibration_folds
                else "None"
            ),
        )

        print(
            "Calibration observations:",
            fold_result.calibration_observations,
        )

        print(
            "Selected K:",
            fold_result.selected_k,
        )

        print(
            "Selection method:",
            fold_result.selection_method,
        )

        if (
            fold_result.calibration_score
            is not None
        ):
            print(
                "Calibration score:",
                f"{fold_result.calibration_score:.6f}",
            )

        print(
            "Held-out observations:",
            evaluation.records_with_predictions,
        )

        print(
            "Held-out Home MAE:",
            f"{evaluation.home_model.mae:.4f}",
        )

        print(
            "Held-out Away MAE:",
            f"{evaluation.away_model.mae:.4f}",
        )

        print(
            "Held-out Home improvement vs naive:",
            (
                f"{evaluation.home_mae_improvement_vs_naive:.2f}%"
            ),
        )

        print(
            "Held-out Away improvement vs naive:",
            (
                f"{evaluation.away_mae_improvement_vs_naive:.2f}%"
            ),
        )

    print()
    print("=" * 72)
    print("END CALIBRATION REPORT")
    print("=" * 72)
    print()


# ============================================================
# COMPLETE CALIBRATION RUNNER
# ============================================================


def run_expected_goals_calibration() -> CalibrationResult:
    """
    Build the canonical historical dataset and run calibration.

    This is the convenience entry point for local experimentation.
    """

    print()
    print(
        "Loading canonical historical team matches..."
    )

    historical_matches = (
        load_historical_team_matches()
    )

    print(
        "Historical matches loaded:",
        len(historical_matches),
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
        "Validation records built:",
        len(validation_records),
    )

    result = calibrate_walk_forward_shrinkage(
        validation_records
    )

    print_calibration_report(
        result
    )

    return result


# ============================================================
# SCRIPT ENTRY POINT
# ============================================================


if __name__ == "__main__":
    run_expected_goals_calibration()