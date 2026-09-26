"""
walk_forward_validation.py

Defines the walk-forward validation structure for the FPL
Strategist Agent.

Purpose
-------
Historical model validation must respect time.

We must never train a model using information from a season
that occurs after the historical season being tested.

Our agreed validation design is:

    Train: 2020/21
    Test:  2021/22

    Train: 2020/21 + 2021/22
    Test:  2022/23

    Train: 2020/21 + 2021/22 + 2022/23
    Test:  2023/24

    Train: 2020/21 + 2021/22 + 2022/23 + 2023/24
    Test:  2024/25

    Train: 2020/21 + 2021/22 + 2022/23 + 2023/24 + 2024/25
    Test:  2025/26

The current 2026/27 season is LIVE and must not be used to
tune the historical model.

This module only defines and validates the walk-forward
configuration.

It does NOT:
    - calculate team strength
    - predict fixtures
    - calculate expected goals
    - calculate expected FPL points
    - tune model parameters
    - evaluate prediction accuracy
"""


from __future__ import annotations

from dataclasses import dataclass


# ============================================================
# CONSTANTS
# ============================================================

# Historical seasons available for our agreed validation
# exercise.
HISTORICAL_SEASONS = (
    "2020/21",
    "2021/22",
    "2022/23",
    "2023/24",
    "2024/25",
    "2025/26",
)


# The current live season is deliberately kept separate from
# historical validation.
LIVE_SEASON = "2026/27"


# ============================================================
# DATA STRUCTURE
# ============================================================

@dataclass(frozen=True)
class WalkForwardFold:
    """
    Represents one walk-forward validation fold.

    Example:

        training_seasons = ("2020/21",)
        test_season = "2021/22"

    means:

        Learn from 2020/21
        Test on 2021/22
    """

    fold_number: int

    training_seasons: tuple[str, ...]

    test_season: str


# ============================================================
# VALIDATION CONFIGURATION
# ============================================================

def build_walk_forward_folds() -> list[WalkForwardFold]:
    """
    Build the agreed walk-forward validation folds.

    Each test season can only use seasons that occurred
    before it.

    Returns
    -------
    list[WalkForwardFold]
        Five chronological validation folds.
    """

    folds: list[WalkForwardFold] = []

    # --------------------------------------------------------
    # Each historical season after the first becomes a test
    # season.
    #
    # The seasons before it become the training window.
    # --------------------------------------------------------

    for index in range(1, len(HISTORICAL_SEASONS)):

        test_season = HISTORICAL_SEASONS[index]

        training_seasons = HISTORICAL_SEASONS[
            :index
        ]

        fold = WalkForwardFold(
            fold_number=index,
            training_seasons=training_seasons,
            test_season=test_season,
        )

        folds.append(fold)

    return folds


# ============================================================
# VALIDATION HELPERS
# ============================================================

def validate_walk_forward_folds(
    folds: list[WalkForwardFold],
) -> None:
    """
    Validate the walk-forward configuration.

    Raises
    ------
    ValueError
        If the configuration violates chronological
        walk-forward rules.
    """

    # --------------------------------------------------------
    # We expect exactly one fold for every historical season
    # after the first.
    # --------------------------------------------------------

    expected_fold_count = (
        len(HISTORICAL_SEASONS) - 1
    )

    if len(folds) != expected_fold_count:

        raise ValueError(
            "Unexpected number of walk-forward folds: "
            f"{len(folds)}. Expected "
            f"{expected_fold_count}."
        )

    # --------------------------------------------------------
    # Check each fold individually.
    # --------------------------------------------------------

    for expected_number, fold in enumerate(
        folds,
        start=1,
    ):

        # Fold numbers must be sequential.

        if fold.fold_number != expected_number:

            raise ValueError(
                "Walk-forward fold numbers must be "
                "sequential."
            )

        # The test season must be one of our historical
        # seasons.

        if fold.test_season not in HISTORICAL_SEASONS:

            raise ValueError(
                "Test season is not in HISTORICAL_SEASONS: "
                f"{fold.test_season}"
            )

        # The live 2026/27 season must never accidentally
        # become part of historical validation.

        if fold.test_season == LIVE_SEASON:

            raise ValueError(
                "LIVE_SEASON cannot be used as a historical "
                "test season."
            )

        # ----------------------------------------------------
        # Determine where the test season occurs in the
        # chronological season list.
        # ----------------------------------------------------

        test_index = HISTORICAL_SEASONS.index(
            fold.test_season
        )

        expected_training = HISTORICAL_SEASONS[
            :test_index
        ]

        # ----------------------------------------------------
        # Training data must contain exactly the seasons
        # before the test season.
        # ----------------------------------------------------

        if fold.training_seasons != expected_training:

            raise ValueError(
                "Training seasons are not strictly "
                "chronological for test season "
                f"{fold.test_season}."
            )

        # ----------------------------------------------------
        # Training data must not contain the test season.
        # ----------------------------------------------------

        if fold.test_season in fold.training_seasons:

            raise ValueError(
                "Test season cannot also appear in "
                "training seasons."
            )

        # ----------------------------------------------------
        # Training data must not contain the live season.
        # ----------------------------------------------------

        if LIVE_SEASON in fold.training_seasons:

            raise ValueError(
                "LIVE_SEASON cannot appear in training "
                "seasons."
            )

        # ----------------------------------------------------
        # There must be at least one training season.
        # ----------------------------------------------------

        if not fold.training_seasons:

            raise ValueError(
                "Every validation fold must have at least "
                "one training season."
            )


# ============================================================
# PUBLIC FUNCTION
# ============================================================

def get_walk_forward_folds() -> list[WalkForwardFold]:
    """
    Return the validated walk-forward configuration.

    This is the main function that future validation code
    should call instead of constructing folds manually.
    """

    folds = build_walk_forward_folds()

    validate_walk_forward_folds(
        folds
    )

    return folds


# ============================================================
# SIMPLE MANUAL CHECK
# ============================================================

if __name__ == "__main__":
    """
    Print the configured folds when this file is executed
    directly.

    This is useful while learning the project because we can
    visually verify the chronological structure.
    """

    folds = get_walk_forward_folds()

    for fold in folds:

        print(
            f"Fold {fold.fold_number}: "
            f"Train {fold.training_seasons} "
            f"-> Test {fold.test_season}"
        )