"""
walk_forward_data.py

Builds the historical walk-forward validation dataset.

Purpose
-------
Connect the walk-forward configuration to the canonical
historical Premier League match data.

For every historical test fixture, this module records:

    - validation fold
    - training seasons
    - test season
    - fixture identity
    - kickoff time
    - point-in-time cutoff
    - home team
    - away team
    - actual result
    - actual goals
    - home team state available BEFORE kickoff
    - away team state available BEFORE kickoff

Important
---------
This module does NOT:

    - predict match results
    - calculate expected goals
    - calculate expected FPL points
    - tune model parameters
    - select model weights
    - use future information

The purpose is to create a clean, leakage-controlled dataset
that future prediction models can consume.

Performance design
------------------
The first version of this module rebuilt the complete historical
team state separately for every fixture.

That was correct but inefficient.

For example, with 380 fixtures in a test season, the same
historical matches were repeatedly processed hundreds of times.

This version processes each test season chronologically only once.

For every fixture:

    1. Capture the current team state BEFORE the fixture.
    2. Store that snapshot for the validation record.
    3. Apply the fixture result to the running state.
    4. Move to the next fixture.

Therefore the target fixture can never enter its own state.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pandas as pd

from historical_team_state import (
    _assign_league_ranks,
    _calculate_derived_metrics,
    _calculate_recent_form,
    _create_empty_team_state,
    _update_team_from_match,
)

from historical_team_data import (
    load_historical_team_matches,
)

from walk_forward_validation import (
    WalkForwardFold,
    get_walk_forward_folds,
)


# ============================================================
# CONSTANTS
# ============================================================

# These are the fields required from the canonical historical
# match dataset.

REQUIRED_MATCH_COLUMNS = [
    "match_id",
    "season",
    "kickoff_datetime",
    "home_team",
    "away_team",
    "home_goals",
    "away_goals",
    "result",
]


# ============================================================
# VALIDATION HELPERS
# ============================================================

def _validate_historical_match_data(
    historical_matches: pd.DataFrame,
) -> None:
    """
    Validate that the supplied historical match data contains
    the fields required by the walk-forward dataset builder.
    """

    # Make sure the caller supplied a DataFrame.

    if not isinstance(
        historical_matches,
        pd.DataFrame,
    ):
        raise TypeError(
            "historical_matches must be a pandas DataFrame."
        )

    # Find any required columns that are missing.

    missing_columns = [
        column
        for column in REQUIRED_MATCH_COLUMNS
        if column not in historical_matches.columns
    ]

    if missing_columns:
        raise ValueError(
            "Historical match data is missing required "
            f"columns: {missing_columns}"
        )


def _validate_fold_data(
    fold: WalkForwardFold,
    historical_matches: pd.DataFrame,
) -> None:
    """
    Verify that all seasons referenced by a fold exist in the
    supplied historical dataset.
    """

    available_seasons = set(
        historical_matches["season"]
        .astype(str)
        .unique()
    )

    required_seasons = set(
        fold.training_seasons
    )

    required_seasons.add(
        fold.test_season
    )

    missing_seasons = (
        required_seasons
        - available_seasons
    )

    if missing_seasons:
        raise ValueError(
            "Historical match data does not contain the "
            f"following required seasons: {sorted(missing_seasons)}"
        )


# ============================================================
# STATE HELPERS
# ============================================================

def _build_empty_state_containers(
    teams: dict[str, dict[str, Any]],
    team_matches: dict[str, list[dict[str, Any]]],
) -> None:
    """
    Create empty containers.

    The containers are intentionally created lazily.

    This preserves the behaviour of historical_team_state.py:
    a team does not appear in the state until that team has
    actually appeared in a historical match.
    """

    # Nothing is returned because the dictionaries are mutable
    # objects and are updated directly.


def _ensure_team_exists(
    teams: dict[str, dict[str, Any]],
    team_matches: dict[str, list[dict[str, Any]]],
    team_name: str,
    season: str,
    cutoff_datetime: pd.Timestamp,
) -> None:
    """
    Create a team state the first time a team appears.

    This follows the same initialization logic used by
    historical_team_state.py.
    """

    if team_name not in teams:
        teams[team_name] = _create_empty_team_state(
            team_name,
            season,
            cutoff_datetime,
        )

        team_matches[team_name] = []


def _build_current_team_state_snapshot(
    teams: dict[str, dict[str, Any]],
    team_matches: dict[str, list[dict[str, Any]]],
    season: str,
    cutoff_datetime: pd.Timestamp,
) -> dict[str, dict[str, Any]]:
    """
    Build a point-in-time snapshot of the current running state.

    This function does NOT process any new match.

    It takes the state accumulated from matches that occurred
    before the current fixture and calculates:

        - recent-5 statistics
        - derived metrics
        - league rank

    The result is deep-copied so later matches cannot modify
    historical snapshots already stored in validation records.
    """

    # Start with a deep copy of the running cumulative state.

    snapshot = deepcopy(teams)

    # Recalculate recent form and derived metrics for every team.

    for team_name, team in snapshot.items():

        _calculate_recent_form(
            team=team,
            team_matches=team_matches[team_name],
        )

        _calculate_derived_metrics(
            team
        )

        # Make sure the metadata continues to represent the
        # exact point in time immediately before the fixture.

        team["season"] = season
        team["as_of_datetime"] = cutoff_datetime

    # Calculate league positions using ONLY the state available
    # before the current fixture.

    if snapshot:
        _assign_league_ranks(
            snapshot
        )

    return snapshot


def _apply_match_to_running_state(
    teams: dict[str, dict[str, Any]],
    team_matches: dict[str, list[dict[str, Any]]],
    match: pd.Series,
    season: str,
    cutoff_datetime: pd.Timestamp,
) -> None:
    """
    Apply one completed match to the running team state.

    IMPORTANT
    ---------
    This function is called ONLY AFTER the pre-match snapshot
    has been captured.

    Therefore the match being processed cannot leak into its own
    validation state.
    """

    # Extract the two teams.

    home_team = str(
        match["home_team"]
    )

    away_team = str(
        match["away_team"]
    )

    # Extract the actual goals.

    home_goals = int(
        match["home_goals"]
    )

    away_goals = int(
        match["away_goals"]
    )

    # Create the team containers if this is the first appearance
    # of either team in the season.

    _ensure_team_exists(
        teams=teams,
        team_matches=team_matches,
        team_name=home_team,
        season=season,
        cutoff_datetime=cutoff_datetime,
    )

    _ensure_team_exists(
        teams=teams,
        team_matches=team_matches,
        team_name=away_team,
        season=season,
        cutoff_datetime=cutoff_datetime,
    )

    # Update the home team.

    _update_team_from_match(
        team=teams[home_team],
        goals_for=home_goals,
        goals_against=away_goals,
        venue="home",
    )

    # Update the away team.

    _update_team_from_match(
        team=teams[away_team],
        goals_for=away_goals,
        goals_against=home_goals,
        venue="away",
    )

    # Store the completed match for future recent-5 calculations.

    match_record = {
        "match_id": match["match_id"],
        "season": season,
        "kickoff_datetime": match[
            "kickoff_datetime"
        ],
        "home_team": home_team,
        "away_team": away_team,
        "home_goals": home_goals,
        "away_goals": away_goals,
    }

    team_matches[home_team].append(
        match_record
    )

    team_matches[away_team].append(
        match_record
    )


# ============================================================
# VALIDATION RECORD BUILDER
# ============================================================

def _build_fixture_validation_record(
    fold: WalkForwardFold,
    match: pd.Series,
    home_state: dict[str, Any] | None,
    away_state: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Build one auditable validation record.

    The actual result is retained separately from the
    point-in-time team states.

    This is important because the actual result is the target
    that a future model will attempt to predict.
    """

    return {
        # ----------------------------------------------------
        # Validation metadata
        # ----------------------------------------------------

        "fold_number": fold.fold_number,

        "training_seasons": tuple(
            fold.training_seasons
        ),

        "test_season": fold.test_season,

        # ----------------------------------------------------
        # Fixture identity
        # ----------------------------------------------------

        "match_id": match["match_id"],

        "kickoff_datetime": match[
            "kickoff_datetime"
        ],

        # The state cutoff is exactly the fixture kickoff.

        # The state-building logic uses a strict '<' rule,
        # so the fixture itself cannot enter the state.

        "state_cutoff_datetime": match[
            "kickoff_datetime"
        ],

        "home_team": match["home_team"],
        "away_team": match["away_team"],

        # ----------------------------------------------------
        # Actual outcome
        # ----------------------------------------------------

        # These fields are the targets for future prediction
        # models.

        # They must never be used while constructing the
        # pre-kickoff team state.

        "actual_home_goals": int(
            match["home_goals"]
        ),

        "actual_away_goals": int(
            match["away_goals"]
        ),

        "actual_result": match["result"],

        # ----------------------------------------------------
        # Point-in-time team states
        # ----------------------------------------------------

        "home_team_state": home_state,

        "away_team_state": away_state,
    }


# ============================================================
# PUBLIC FUNCTION
# ============================================================

def build_walk_forward_dataset(
    historical_matches: pd.DataFrame,
) -> list[dict[str, Any]]:
    """
    Build the complete historical walk-forward validation
    dataset.

    Parameters
    ----------
    historical_matches:
        Canonical historical match data produced by
        historical_team_data.py.

    Returns
    -------
    list[dict[str, Any]]
        One validation record per historical test fixture.

    Expected production size
    ------------------------
    Five test seasons × 380 fixtures = 1,900 records.

    Important
    ---------
    The actual match result is stored as the target.

    It is NOT used when constructing the pre-kickoff team state.

    Performance
    -----------
    Each test season is processed chronologically once.

    The previous implementation rebuilt the complete historical
    team state separately for every fixture.

    This implementation instead maintains one running state and
    snapshots it immediately before each fixture.
    """

    # --------------------------------------------------------
    # Validate input.
    # --------------------------------------------------------

    _validate_historical_match_data(
        historical_matches
    )

    # --------------------------------------------------------
    # Work on a copy so that the caller's DataFrame is never
    # modified by this function.
    # --------------------------------------------------------

    data = historical_matches.copy()

    # Normalize the kickoff timestamp.

    data["kickoff_datetime"] = pd.to_datetime(
        data["kickoff_datetime"],
        errors="raise",
    )

    # Normalize season representation.

    data["season"] = (
        data["season"]
        .astype(str)
    )

    # --------------------------------------------------------
    # Get the validated chronological folds.
    # --------------------------------------------------------

    folds = get_walk_forward_folds()

    validation_records: list[
        dict[str, Any]
    ] = []

    # --------------------------------------------------------
    # Process each fold.
    # --------------------------------------------------------

    for fold in folds:

        _validate_fold_data(
            fold,
            data,
        )

        # ----------------------------------------------------
        # Select ONLY the test season fixtures.
        #
        # Training seasons are deliberately not mixed into the
        # test fixture set.
        # ----------------------------------------------------

        test_matches = data[
            data["season"]
            == fold.test_season
        ].copy()

        # Sort chronologically.

        test_matches = test_matches.sort_values(
            [
                "kickoff_datetime",
                "match_id",
            ]
        )

        # ----------------------------------------------------
        # Running state for this test season.
        #
        # IMPORTANT:
        #
        # This follows the methodology of the existing
        # historical_team_state.py implementation, which builds
        # the state from matches within the requested test season.
        #
        # We are optimizing HOW that state is calculated, not
        # changing WHICH matches are used.
        # ----------------------------------------------------

        teams: dict[
            str,
            dict[str, Any],
        ] = {}

        team_matches: dict[
            str,
            list[dict[str, Any]],
        ] = {}

        # ----------------------------------------------------
        # Process every test fixture chronologically.
        # ----------------------------------------------------

        for _, match in test_matches.iterrows():

            cutoff = pd.Timestamp(
                match["kickoff_datetime"]
            )

            # ------------------------------------------------
            # STEP 1
            #
            # Capture the state BEFORE the target fixture.
            #
            # The target fixture has NOT been applied yet.
            # Therefore its result cannot leak into the state.
            # ------------------------------------------------

            team_state = (
                _build_current_team_state_snapshot(
                    teams=teams,
                    team_matches=team_matches,
                    season=fold.test_season,
                    cutoff_datetime=cutoff,
                )
            )

            # ------------------------------------------------
            # STEP 2
            #
            # Retrieve the home team's state.
            #
            # A team can legitimately be absent at the very
            # beginning of a season if it has not played yet.
            #
            # None is therefore meaningful.
            # ------------------------------------------------

            home_state = team_state.get(
                str(match["home_team"])
            )

            # ------------------------------------------------
            # STEP 3
            #
            # Retrieve the away team's state.
            # ------------------------------------------------

            away_state = team_state.get(
                str(match["away_team"])
            )

            # ------------------------------------------------
            # STEP 4
            #
            # Build the validation record using the PRE-MATCH
            # state and the actual target result.
            # ------------------------------------------------

            validation_record = (
                _build_fixture_validation_record(
                    fold=fold,
                    match=match,
                    home_state=home_state,
                    away_state=away_state,
                )
            )

            validation_records.append(
                validation_record
            )

            # ------------------------------------------------
            # STEP 5
            #
            # ONLY NOW apply the actual match.
            #
            # This is the key leakage-control mechanism.
            #
            # The current fixture can affect future fixtures,
            # but it can never affect its own validation record.
            # ------------------------------------------------

            _apply_match_to_running_state(
                teams=teams,
                team_matches=team_matches,
                match=match,
                season=fold.test_season,
                cutoff_datetime=cutoff,
            )

    return validation_records


# ============================================================
# SUMMARY FUNCTION
# ============================================================

def summarize_walk_forward_dataset(
    validation_records: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Produce a compact summary of the generated validation
    dataset.

    This function is descriptive only.

    It does not evaluate prediction quality.
    """

    if not isinstance(
        validation_records,
        list,
    ):
        raise TypeError(
            "validation_records must be a list."
        )

    if not validation_records:
        return {
            "records": 0,
            "folds": 0,
            "test_seasons": [],
            "records_by_fold": {},
            "records_with_home_state": 0,
            "records_with_away_state": 0,
        }

    records_by_fold: dict[
        int,
        int,
    ] = {}

    test_seasons: set[str] = set()

    records_with_home_state = 0
    records_with_away_state = 0

    for record in validation_records:

        fold_number = int(
            record["fold_number"]
        )

        records_by_fold[fold_number] = (
            records_by_fold.get(
                fold_number,
                0,
            )
            + 1
        )

        test_seasons.add(
            record["test_season"]
        )

        if record["home_team_state"] is not None:
            records_with_home_state += 1

        if record["away_team_state"] is not None:
            records_with_away_state += 1

    return {
        "records": len(
            validation_records
        ),

        "folds": len(
            records_by_fold
        ),

        "test_seasons": sorted(
            test_seasons
        ),

        "records_by_fold": records_by_fold,

        "records_with_home_state": (
            records_with_home_state
        ),

        "records_with_away_state": (
            records_with_away_state
        ),
    }


# ============================================================
# SIMPLE MANUAL CHECK
# ============================================================

if __name__ == "__main__":
    """
    Build the complete historical validation dataset and print
    a compact summary.

    Expected:

        5 folds
        1,900 test fixtures
        380 fixtures per test season
    """

    print(
        "Loading historical team match data..."
    )

    historical_matches = (
        load_historical_team_matches()
    )

    print(
        "\nBuilding walk-forward dataset..."
    )

    validation_records = (
        build_walk_forward_dataset(
            historical_matches
        )
    )

    summary = (
        summarize_walk_forward_dataset(
            validation_records
        )
    )

    print(
        "\n" + "=" * 70
    )

    print(
        "WALK-FORWARD DATASET SUMMARY"
    )

    print(
        "=" * 70
    )

    print(
        f"Records: {summary['records']}"
    )

    print(
        f"Folds: {summary['folds']}"
    )

    print(
        f"Test seasons: {summary['test_seasons']}"
    )

    print(
        f"Records by fold: {summary['records_by_fold']}"
    )

    print(
        "Records with home team state: "
        f"{summary['records_with_home_state']}"
    )

    print(
        "Records with away team state: "
        f"{summary['records_with_away_state']}"
    )