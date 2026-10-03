"""
test_walk_forward_validation.py

Tests the walk-forward validation configuration.

The objective is to prove that our historical validation
never trains on future seasons.
"""


from walk_forward_validation import (
    HISTORICAL_SEASONS,
    LIVE_SEASON,
    WalkForwardFold,
    get_walk_forward_folds,
    validate_walk_forward_folds,
)


# ============================================================
# TEST FOLD COUNT
# ============================================================

def test_fold_count() -> None:
    """
    There should be one test fold for every historical season
    after the first season.
    """

    folds = get_walk_forward_folds()

    expected_count = (
        len(HISTORICAL_SEASONS) - 1
    )

    assert len(folds) == expected_count


# ============================================================
# TEST EXPECTED FOLDS
# ============================================================

def test_expected_folds() -> None:
    """
    Verify the exact agreed walk-forward structure.
    """

    folds = get_walk_forward_folds()

    # --------------------------------------------------------
    # Fold 1
    # --------------------------------------------------------

    assert folds[0].fold_number == 1

    assert folds[0].training_seasons == (
        "2020/21",
    )

    assert folds[0].test_season == "2021/22"

    # --------------------------------------------------------
    # Fold 2
    # --------------------------------------------------------

    assert folds[1].fold_number == 2

    assert folds[1].training_seasons == (
        "2020/21",
        "2021/22",
    )

    assert folds[1].test_season == "2022/23"

    # --------------------------------------------------------
    # Fold 3
    # --------------------------------------------------------

    assert folds[2].fold_number == 3

    assert folds[2].training_seasons == (
        "2020/21",
        "2021/22",
        "2022/23",
    )

    assert folds[2].test_season == "2023/24"

    # --------------------------------------------------------
    # Fold 4
    # --------------------------------------------------------

    assert folds[3].fold_number == 4

    assert folds[3].training_seasons == (
        "2020/21",
        "2021/22",
        "2022/23",
        "2023/24",
    )

    assert folds[3].test_season == "2024/25"

    # --------------------------------------------------------
    # Fold 5
    # --------------------------------------------------------

    assert folds[4].fold_number == 5

    assert folds[4].training_seasons == (
        "2020/21",
        "2021/22",
        "2022/23",
        "2023/24",
        "2024/25",
    )

    assert folds[4].test_season == "2025/26"


# ============================================================
# NO LIVE-SEASON LEAKAGE
# ============================================================

def test_live_season_is_not_used() -> None:
    """
    2026/27 is the live season.

    It must not appear anywhere in the historical
    walk-forward folds.
    """

    folds = get_walk_forward_folds()

    for fold in folds:

        assert fold.test_season != LIVE_SEASON

        assert LIVE_SEASON not in (
            fold.training_seasons
        )


# ============================================================
# CHRONOLOGICAL TRAINING TEST
# ============================================================

def test_training_is_always_before_test() -> None:
    """
    Every training season must occur before the test season.
    """

    folds = get_walk_forward_folds()

    for fold in folds:

        test_index = HISTORICAL_SEASONS.index(
            fold.test_season
        )

        for training_season in (
            fold.training_seasons
        ):

            training_index = HISTORICAL_SEASONS.index(
                training_season
            )

            assert training_index < test_index


# ============================================================
# VALIDATION FUNCTION TEST
# ============================================================

def test_validation_accepts_correct_configuration() -> None:
    """
    The official configuration must pass validation.
    """

    folds = get_walk_forward_folds()

    # This should raise no exception.

    validate_walk_forward_folds(
        folds
    )


# ============================================================
# INVALID CONFIGURATION TEST
# ============================================================

def test_validation_rejects_future_training_data() -> None:
    """
    Deliberately create an invalid fold where the test season
    appears in the training data.

    The validator must reject it.
    """

    invalid_fold = WalkForwardFold(
        fold_number=1,
        training_seasons=(
            "2020/21",
            "2021/22",
        ),
        test_season="2021/22",
    )

    try:

        validate_walk_forward_folds(
            [
                invalid_fold,
                *get_walk_forward_folds()[1:],
            ]
        )

    except ValueError:

        # Expected behaviour.

        return

    # If no exception was raised, the test must fail.

    raise AssertionError(
        "Invalid walk-forward configuration was "
        "not rejected."
    )


# ============================================================
# TEST RUNNER
# ============================================================

if __name__ == "__main__":
    """
    Run all tests directly without requiring pytest.
    """

    test_fold_count()
    test_expected_folds()
    test_live_season_is_not_used()
    test_training_is_always_before_test()
    test_validation_accepts_correct_configuration()
    test_validation_rejects_future_training_data()

    print(
        "All walk-forward validation tests passed."
    )