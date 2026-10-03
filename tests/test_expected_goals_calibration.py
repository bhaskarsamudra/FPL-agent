"""
Tests for the leakage-safe expected-goals calibration layer.

These tests focus on the calibration process itself.

The most important property being tested is:

    Past folds -> calibrate K -> current fold -> evaluate

The current held-out fold must never influence K selection.
"""

from __future__ import annotations

from unittest.mock import patch

from expected_goals_calibration import (
    DEFAULT_CANDIDATE_K_VALUES,
    CalibrationResult,
    _calculate_calibration_score,
    _get_fold_numbers,
    _get_test_season,
    _validate_candidate_k_values,
    _validate_validation_records,
    calibrate_walk_forward_shrinkage,
    select_best_shrinkage_k,
)

from expected_goals_evaluation import (
    EvaluationResult,
    GoalPredictionMetrics,
)


# ============================================================
# TEST HELPERS
# ============================================================


def _build_test_record(
    fold_number: int,
    test_season: str,
    match_id: str,
) -> dict:
    """
    Build a minimal validation record compatible with the
    expected-goals walk-forward model.

    These records are synthetic test data. They are NOT used
    for football analysis.
    """

    return {
        # ----------------------------------------------------
        # Walk-forward metadata.
        # ----------------------------------------------------

        "fold_number": fold_number,
        "test_season": test_season,
        "match_id": match_id,

        # ----------------------------------------------------
        # Fixture metadata.
        # ----------------------------------------------------

        "kickoff_datetime": (
            f"{test_season[:4]}-08-20T15:00:00"
        ),

        "state_cutoff_datetime": (
            f"{test_season[:4]}-08-20T15:00:00"
        ),

        "home_team": "Test Home",
        "away_team": "Test Away",

        # ----------------------------------------------------
        # Actual match result.
        # ----------------------------------------------------

        "actual_home_goals": 1.0,
        "actual_away_goals": 1.0,

        "actual_result": "D",

        # ----------------------------------------------------
        # Point-in-time home-team state.
        #
        # These values are deliberately simple because the
        # tests are validating calibration mechanics rather
        # than football modelling quality.
        # ----------------------------------------------------

        "home_team_state": {
            "played": 5,
            "points": 7,
            "goal_difference": 0,
            "goals_scored": 6,
            "goals_conceded": 6,
            "home_played": 3,
            "home_goals_scored": 4,
            "home_goals_conceded": 3,
            "away_played": 2,
            "away_goals_scored": 2,
            "away_goals_conceded": 3,
            "home_goals_for_per_match": 1.5,
            "home_goals_against_per_match": 1.0,
            "away_goals_for_per_match": 1.0,
            "away_goals_against_per_match": 1.5,
        },

        # ----------------------------------------------------
        # Point-in-time away-team state.
        # ----------------------------------------------------

        "away_team_state": {
            "played": 5,
            "points": 7,
            "goal_difference": 0,
            "goals_scored": 6,
            "goals_conceded": 6,
            "home_played": 2,
            "home_goals_scored": 2,
            "home_goals_conceded": 3,
            "away_played": 3,
            "away_goals_scored": 4,
            "away_goals_conceded": 3,
            "home_goals_for_per_match": 1.0,
            "home_goals_against_per_match": 1.5,
            "away_goals_for_per_match": 1.3333333333333333,
            "away_goals_against_per_match": 1.0,
        },
    }


def _build_test_dataset() -> list[dict]:
    """
    Build a tiny three-fold dataset.

    Each fold contains two records so we can clearly verify
    which folds are used for calibration.
    """

    return [
        _build_test_record(
            fold_number=1,
            test_season="2021/22",
            match_id="F1-M1",
        ),
        _build_test_record(
            fold_number=1,
            test_season="2021/22",
            match_id="F1-M2",
        ),
        _build_test_record(
            fold_number=2,
            test_season="2022/23",
            match_id="F2-M1",
        ),
        _build_test_record(
            fold_number=2,
            test_season="2022/23",
            match_id="F2-M2",
        ),
        _build_test_record(
            fold_number=3,
            test_season="2023/24",
            match_id="F3-M1",
        ),
        _build_test_record(
            fold_number=3,
            test_season="2023/24",
            match_id="F3-M2",
        ),
    ]


def _build_fake_evaluation(
    mae: float,
) -> EvaluationResult:
    """
    Build a minimal EvaluationResult for mocked calibration tests.
    """

    metrics = GoalPredictionMetrics(
        observations=2,
        mae=mae,
        rmse=mae,
        bias=0.0,
    )

    return EvaluationResult(
        observations=2,
        records_available=2,
        records_with_predictions=2,
        records_without_predictions=0,
        home_model=metrics,
        away_model=metrics,
        home_naive=metrics,
        away_naive=metrics,
        home_mae_improvement_vs_naive=0.0,
        away_mae_improvement_vs_naive=0.0,
    )


# ============================================================
# VALIDATION TESTS
# ============================================================


def test_default_candidate_k_values_are_valid() -> None:
    """
    The default candidate K grid must contain valid non-negative
    numeric values.
    """

    _validate_candidate_k_values(
        DEFAULT_CANDIDATE_K_VALUES
    )

    assert DEFAULT_CANDIDATE_K_VALUES


def test_negative_candidate_k_is_rejected() -> None:
    """
    Negative shrinkage K values must be rejected.
    """

    try:
        _validate_candidate_k_values(
            (-1.0,)
        )

    except ValueError:
        return

    raise AssertionError(
        "Negative candidate K was not rejected."
    )


def test_empty_candidate_k_values_are_rejected() -> None:
    """
    An empty candidate grid cannot perform calibration.
    """

    try:
        _validate_candidate_k_values(
            ()
        )

    except ValueError:
        return

    raise AssertionError(
        "Empty candidate K values were not rejected."
    )


def test_empty_validation_records_are_rejected() -> None:
    """
    Calibration cannot operate on an empty dataset.
    """

    try:
        _validate_validation_records(
            []
        )

    except ValueError:
        return

    raise AssertionError(
        "Empty validation records were not rejected."
    )


# ============================================================
# FOLD HELPER TESTS
# ============================================================


def test_fold_numbers_are_sorted() -> None:
    """
    Fold numbers must be returned chronologically.
    """

    records = _build_test_dataset()

    # Reverse the input order deliberately.
    records.reverse()

    fold_numbers = _get_fold_numbers(
        records
    )

    assert fold_numbers == [
        1,
        2,
        3,
    ]


def test_each_fold_has_one_test_season() -> None:
    """
    A valid fold must represent exactly one test season.
    """

    records = _build_test_dataset()

    fold_one_records = [
        record
        for record in records
        if record["fold_number"] == 1
    ]

    assert (
        _get_test_season(
            fold_one_records
        )
        == "2021/22"
    )


# ============================================================
# CALIBRATION SCORE TEST
# ============================================================


def test_calibration_score_is_mean_home_and_away_mae() -> None:
    """
    Calibration score must be the arithmetic mean of home and
    away MAE.
    """

    home_metrics = GoalPredictionMetrics(
        observations=10,
        mae=1.0,
        rmse=1.2,
        bias=0.1,
    )

    away_metrics = GoalPredictionMetrics(
        observations=10,
        mae=0.8,
        rmse=1.0,
        bias=-0.1,
    )

    evaluation = EvaluationResult(
        observations=10,
        records_available=10,
        records_with_predictions=10,
        records_without_predictions=0,
        home_model=home_metrics,
        away_model=away_metrics,
        home_naive=home_metrics,
        away_naive=away_metrics,
        home_mae_improvement_vs_naive=0.0,
        away_mae_improvement_vs_naive=0.0,
    )

    score = _calculate_calibration_score(
        evaluation
    )

    assert score == 0.9


# ============================================================
# K SELECTION TESTS
# ============================================================


def test_best_k_is_selected_from_calibration_data() -> None:
    """
    The candidate K with the lowest calibration score must be
    selected.
    """

    records = _build_test_dataset()

    calibration_records = [
        record
        for record in records
        if record["fold_number"] == 1
    ]

    # Candidate 1.0 will receive the lowest mocked error.
    def fake_evaluate(
        validation_records,
        *,
        league_average_home_goals,
        league_average_away_goals,
        shrinkage_k,
    ):
        scores = {
            0.0: 1.00,
            1.0: 0.80,
            2.0: 0.90,
        }

        return _build_fake_evaluation(
            scores[float(shrinkage_k)]
        )

    with patch(
        "expected_goals_calibration.evaluate_validation_records",
        side_effect=fake_evaluate,
    ):

        selected_k, score = (
            select_best_shrinkage_k(
                calibration_records,
                candidate_k_values=(
                    0.0,
                    1.0,
                    2.0,
                ),
            )
        )

    assert selected_k == 1.0
    assert score == 0.8


def test_k_selection_uses_smaller_k_on_exact_tie() -> None:
    """
    When two candidate K values have exactly the same score,
    the smaller K must be selected.
    """

    records = _build_test_dataset()

    calibration_records = [
        record
        for record in records
        if record["fold_number"] == 1
    ]

    def fake_evaluate(
        validation_records,
        *,
        league_average_home_goals,
        league_average_away_goals,
        shrinkage_k,
    ):
        return _build_fake_evaluation(
            0.80
        )

    with patch(
        "expected_goals_calibration.evaluate_validation_records",
        side_effect=fake_evaluate,
    ):

        selected_k, score = (
            select_best_shrinkage_k(
                calibration_records,
                candidate_k_values=(
                    1.0,
                    2.0,
                ),
            )
        )

    assert selected_k == 1.0
    assert score == 0.80


# ============================================================
# LEAKAGE TESTS
# ============================================================


def test_first_fold_uses_default_k() -> None:
    """
    The first fold has no prior fold available.

    Therefore it must use the default K.
    """

    records = _build_test_dataset()

    result = calibrate_walk_forward_shrinkage(
        records,
        candidate_k_values=(
            0.0,
            1.0,
            2.0,
        ),
        default_k=5.0,
    )

    first_fold = result.fold_results[0]

    assert first_fold.fold_number == 1

    assert first_fold.calibration_folds == ()

    assert first_fold.calibration_observations == 0

    assert first_fold.selected_k == 5.0

    assert (
        first_fold.selection_method
        == "default_no_prior_fold"
    )


def test_second_fold_uses_only_first_fold_for_calibration() -> None:
    """
    Fold 2 must use Fold 1 only.

    Fold 2 itself and Fold 3 must not be included.
    """

    records = _build_test_dataset()

    captured_calibration_records = []

    def fake_select_best_k(
        calibration_records,
        *,
        candidate_k_values,
        league_average_home_goals,
        league_average_away_goals,
    ):
        captured_calibration_records.append(
            calibration_records
        )

        return 1.0, 0.5

    with patch(
        "expected_goals_calibration.select_best_shrinkage_k",
        side_effect=fake_select_best_k,
    ):

        calibrate_walk_forward_shrinkage(
            records,
            candidate_k_values=(
                0.0,
                1.0,
            ),
        )

    # The first call to the calibration selector corresponds
    # to Fold 2.
    fold_two_calibration = (
        captured_calibration_records[0]
    )

    fold_numbers = {
        record["fold_number"]
        for record in fold_two_calibration
    }

    assert fold_numbers == {1}

    assert len(
        fold_two_calibration
    ) == 2


def test_third_fold_uses_first_and_second_folds_only() -> None:
    """
    Fold 3 must use Folds 1 and 2.

    Fold 3 itself must never enter calibration.
    """

    records = _build_test_dataset()

    captured_calibration_records = []

    def fake_select_best_k(
        calibration_records,
        *,
        candidate_k_values,
        league_average_home_goals,
        league_average_away_goals,
    ):
        captured_calibration_records.append(
            calibration_records
        )

        return 1.0, 0.5

    with patch(
        "expected_goals_calibration.select_best_shrinkage_k",
        side_effect=fake_select_best_k,
    ):

        calibrate_walk_forward_shrinkage(
            records,
            candidate_k_values=(
                0.0,
                1.0,
            ),
        )

    # The second call to the calibration selector corresponds
    # to Fold 3.
    fold_three_calibration = (
        captured_calibration_records[1]
    )

    fold_numbers = {
        record["fold_number"]
        for record in fold_three_calibration
    }

    assert fold_numbers == {
        1,
        2,
    }

    assert len(
        fold_three_calibration
    ) == 4


def test_current_fold_is_evaluated_after_k_selection() -> None:
    """
    Verify that the K selected by the calibration step is passed
    to the held-out evaluation step.
    """

    records = _build_test_dataset()

    evaluation_k_values = []

    def fake_select_best_k(
        calibration_records,
        *,
        candidate_k_values,
        league_average_home_goals,
        league_average_away_goals,
    ):
        return 7.5, 0.42

    def fake_evaluate(
        validation_records,
        *,
        league_average_home_goals,
        league_average_away_goals,
        shrinkage_k,
    ):
        evaluation_k_values.append(
            float(shrinkage_k)
        )

        return _build_fake_evaluation(
            1.0
        )

    with patch(
        "expected_goals_calibration.select_best_shrinkage_k",
        side_effect=fake_select_best_k,
    ), patch(
        "expected_goals_calibration.evaluate_validation_records",
        side_effect=fake_evaluate,
    ):

        calibrate_walk_forward_shrinkage(
            records,
            candidate_k_values=(
                0.0,
                1.0,
            ),
            default_k=5.0,
        )

    # Fold 1 uses the default K.
    assert evaluation_k_values[0] == 5.0

    # Later folds use the K selected from prior folds.
    assert evaluation_k_values[1] == 7.5
    assert evaluation_k_values[2] == 7.5


# ============================================================
# RESULT STRUCTURE TEST
# ============================================================


def test_calibration_result_contains_all_folds() -> None:
    """
    The calibration result must contain one result for each
    chronological validation fold.
    """

    records = _build_test_dataset()

    result = calibrate_walk_forward_shrinkage(
        records,
        candidate_k_values=(
            0.0,
            1.0,
        ),
    )

    assert isinstance(
        result,
        CalibrationResult,
    )

    assert len(
        result.fold_results
    ) == 3

    assert [
        fold.fold_number
        for fold in result.fold_results
    ] == [
        1,
        2,
        3,
    ]


# ============================================================
# TEST RUNNER
# ============================================================


def run_all_tests() -> None:
    """
    Run every calibration test explicitly.
    """

    tests = [
        test_default_candidate_k_values_are_valid,
        test_negative_candidate_k_is_rejected,
        test_empty_candidate_k_values_are_rejected,
        test_empty_validation_records_are_rejected,
        test_fold_numbers_are_sorted,
        test_each_fold_has_one_test_season,
        test_calibration_score_is_mean_home_and_away_mae,
        test_best_k_is_selected_from_calibration_data,
        test_k_selection_uses_smaller_k_on_exact_tie,
        test_first_fold_uses_default_k,
        test_second_fold_uses_only_first_fold_for_calibration,
        test_third_fold_uses_first_and_second_folds_only,
        test_current_fold_is_evaluated_after_k_selection,
        test_calibration_result_contains_all_folds,
    ]

    passed = 0

    for test in tests:
        test()

        print(
            f"PASS: {test.__name__}"
        )

        passed += 1

    print()

    print(
        f"ALL EXPECTED-GOALS CALIBRATION TESTS PASSED "
        f"({passed}/{len(tests)})"
    )


# ============================================================
# SCRIPT ENTRY POINT
# ============================================================


if __name__ == "__main__":
    run_all_tests()