"""
test_walk_forward_data.py

Tests the historical walk-forward dataset builder.

These tests focus on:

    - correct number of validation records
    - correct test seasons
    - correct fold sizes
    - actual result preservation
    - strict point-in-time cutoff behaviour
    - no future-match leakage
    - chronological state progression
    - correct recent-form progression
    - summary output
"""

from datetime import datetime

import pandas as pd

from walk_forward_data import (
    build_walk_forward_dataset,
    summarize_walk_forward_dataset,
)


# ============================================================
# TEST DATA
# ============================================================

def create_test_matches() -> pd.DataFrame:
    """
    Create a small artificial historical dataset.

    The data contains all six seasons required by the
    production walk-forward configuration.

    Each artificial season contains two fixtures:

        EARLY
        LATE

    The LATE fixture is useful for testing whether the EARLY
    fixture appears in the pre-match state while the LATE
    fixture itself does not.
    """

    records = []

    # --------------------------------------------------------
    # Create the six required historical seasons.
    # --------------------------------------------------------

    seasons = [
        "2020/21",
        "2021/22",
        "2022/23",
        "2023/24",
        "2024/25",
        "2025/26",
    ]

    for season_number, season in enumerate(
        seasons,
        start=1,
    ):

        # Use a different month for each season so that the
        # artificial records remain easy to distinguish.

        month = season_number

        # ----------------------------------------------------
        # EARLY FIXTURE
        # ----------------------------------------------------

        records.append(
            {
                "match_id": (
                    f"{season}_"
                    "EARLY"
                ),

                "season": season,

                "kickoff_datetime": datetime(
                    2020 + season_number,
                    month,
                    1,
                    12,
                    0,
                ),

                "home_team": "Arsenal",
                "away_team": "Chelsea",

                "home_goals": 2,
                "away_goals": 0,

                "result": "H",
            }
        )

        # ----------------------------------------------------
        # LATE FIXTURE
        # ----------------------------------------------------

        records.append(
            {
                "match_id": (
                    f"{season}_"
                    "LATE"
                ),

                "season": season,

                "kickoff_datetime": datetime(
                    2020 + season_number,
                    month,
                    8,
                    12,
                    0,
                ),

                "home_team": "Arsenal",
                "away_team": "Liverpool",

                "home_goals": 0,
                "away_goals": 3,

                "result": "A",
            }
        )

    return pd.DataFrame(records)


# ============================================================
# BASIC DATASET TEST
# ============================================================

def test_walk_forward_dataset_size() -> None:
    """
    With the six-season production configuration there are:

        5 test folds
        2 fixtures per artificial test season

    Therefore:

        5 × 2 = 10 records
    """

    matches = create_test_matches()

    records = build_walk_forward_dataset(
        matches
    )

    assert len(records) == 10


# ============================================================
# TEST SEASONS
# ============================================================

def test_test_seasons() -> None:
    """
    Verify that only the five historical test seasons are used.

    2020/21 is the initial training-only season and therefore
    must not appear as a test season.
    """

    matches = create_test_matches()

    records = build_walk_forward_dataset(
        matches
    )

    test_seasons = sorted(
        {
            record["test_season"]
            for record in records
        }
    )

    assert test_seasons == [
        "2021/22",
        "2022/23",
        "2023/24",
        "2024/25",
        "2025/26",
    ]


# ============================================================
# FOLD SIZE TEST
# ============================================================

def test_records_per_fold() -> None:
    """
    Every artificial test season contains two fixtures.

    Therefore every validation fold must contain exactly
    two records.
    """

    matches = create_test_matches()

    records = build_walk_forward_dataset(
        matches
    )

    counts = {}

    for record in records:

        fold = record["fold_number"]

        counts[fold] = (
            counts.get(fold, 0)
            + 1
        )

    assert counts == {
        1: 2,
        2: 2,
        3: 2,
        4: 2,
        5: 2,
    }


# ============================================================
# ACTUAL RESULT TEST
# ============================================================

def test_actual_result_is_preserved() -> None:
    """
    Verify that the actual result of the target fixture is
    preserved separately from the pre-match team state.
    """

    matches = create_test_matches()

    records = build_walk_forward_dataset(
        matches
    )

    late_records = [
        record
        for record in records
        if record["match_id"].endswith(
            "_LATE"
        )
    ]

    assert len(late_records) == 5

    for record in late_records:

        assert record["actual_home_goals"] == 0

        assert record["actual_away_goals"] == 3

        assert record["actual_result"] == "A"


# ============================================================
# FIRST FIXTURE STATE TEST
# ============================================================

def test_first_fixture_has_no_prior_team_state() -> None:
    """
    The first fixture of a season has no previous matches.

    Therefore both teams should have no state yet.

    This verifies that we have not accidentally created zeroed
    team states before the teams actually appear in the data.
    """

    matches = create_test_matches()

    records = build_walk_forward_dataset(
        matches
    )

    early_records = [
        record
        for record in records
        if record["match_id"].endswith(
            "_EARLY"
        )
    ]

    assert len(early_records) == 5

    for record in early_records:

        assert record["home_team_state"] is None

        assert record["away_team_state"] is None


# ============================================================
# LEAKAGE TEST
# ============================================================

def test_target_match_is_not_in_team_state() -> None:
    """
    Verify that the target fixture itself is excluded from the
    team state.

    For every LATE fixture:

        Arsenal already played EARLY.

    Therefore Arsenal should have:

        played = 1

    The LATE fixture must not make that:

        played = 2
    """

    matches = create_test_matches()

    records = build_walk_forward_dataset(
        matches
    )

    late_records = [
        record
        for record in records
        if record["match_id"].endswith(
            "_LATE"
        )
    ]

    for record in late_records:

        home_state = record[
            "home_team_state"
        ]

        assert home_state is not None

        # Arsenal played exactly one match before the LATE
        # fixture.

        assert home_state["played"] == 1

        # The previous result was:
        #
        # Arsenal 2-0 Chelsea
        #

        assert home_state["goals_for"] == 2

        assert home_state["goals_against"] == 0

        # The target result was:
        #
        # Arsenal 0-3 Liverpool
        #
        # Those target goals must not appear in the state.

        assert home_state["goals_for"] != 0

        assert home_state["goals_against"] != 3


# ============================================================
# AWAY TEAM LEAKAGE TEST
# ============================================================

def test_away_team_state_is_pre_match_state() -> None:
    """
    Verify the away team's state for the LATE fixture.

    Liverpool is appearing for the first time in the artificial
    season, so it should not have a state before its first match.

    This confirms that the target fixture itself did not create
    a Liverpool state before kickoff.
    """

    matches = create_test_matches()

    records = build_walk_forward_dataset(
        matches
    )

    late_records = [
        record
        for record in records
        if record["match_id"].endswith(
            "_LATE"
        )
    ]

    for record in late_records:

        away_state = record[
            "away_team_state"
        ]

        assert away_state is None


# ============================================================
# STATE CUTOFF TEST
# ============================================================

def test_state_cutoff_matches_fixture_kickoff() -> None:
    """
    Every validation record must use the fixture kickoff as
    the point-in-time cutoff.
    """

    matches = create_test_matches()

    records = build_walk_forward_dataset(
        matches
    )

    for record in records:

        assert (
            record["state_cutoff_datetime"]
            == record["kickoff_datetime"]
        )


# ============================================================
# PREVIOUS MATCH STATE TEST
# ============================================================

def test_previous_match_is_available_to_later_fixture() -> None:
    """
    Verify the chronological nature of the running state.

    The EARLY fixture happens before the LATE fixture.

    Therefore Arsenal's state for the LATE fixture must include
    the EARLY fixture.
    """

    matches = create_test_matches()

    records = build_walk_forward_dataset(
        matches
    )

    late_records = [
        record
        for record in records
        if record["match_id"].endswith(
            "_LATE"
        )
    ]

    for record in late_records:

        home_state = record[
            "home_team_state"
        ]

        assert home_state is not None

        # Arsenal won the EARLY fixture 2-0.

        assert home_state["played"] == 1

        assert home_state["wins"] == 1

        assert home_state["draws"] == 0

        assert home_state["losses"] == 0

        assert home_state["points"] == 3

        assert home_state["goals_for"] == 2

        assert home_state["goals_against"] == 0

        assert home_state["goal_difference"] == 2


# ============================================================
# RECENT FORM TEST
# ============================================================

def test_recent_form_uses_only_prior_matches() -> None:
    """
    Verify that recent-form statistics also respect the
    point-in-time cutoff.

    For Arsenal before the LATE fixture there is exactly one
    completed previous match:

        Arsenal 2-0 Chelsea

    Therefore:

        recent_5_played = 1
        recent_5_wins = 1
        recent_5_points = 3
        recent_5_goals_for = 2
        recent_5_goals_against = 0
    """

    matches = create_test_matches()

    records = build_walk_forward_dataset(
        matches
    )

    late_records = [
        record
        for record in records
        if record["match_id"].endswith(
            "_LATE"
        )
    ]

    for record in late_records:

        home_state = record[
            "home_team_state"
        ]

        assert home_state is not None

        assert home_state["recent_5_played"] == 1

        assert home_state["recent_5_wins"] == 1

        assert home_state["recent_5_draws"] == 0

        assert home_state["recent_5_losses"] == 0

        assert home_state["recent_5_points"] == 3

        assert home_state["recent_5_goals_for"] == 2

        assert home_state["recent_5_goals_against"] == 0


# ============================================================
# SUMMARY TEST
# ============================================================

def test_summary() -> None:
    """
    Verify that the summary function reports the expected
    structure.
    """

    matches = create_test_matches()

    records = build_walk_forward_dataset(
        matches
    )

    summary = summarize_walk_forward_dataset(
        records
    )

    assert summary["records"] == 10

    assert summary["folds"] == 5

    assert summary["test_seasons"] == [
        "2021/22",
        "2022/23",
        "2023/24",
        "2024/25",
        "2025/26",
    ]

    assert summary["records_by_fold"] == {
        1: 2,
        2: 2,
        3: 2,
        4: 2,
        5: 2,
    }

    assert summary["records_with_home_state"] == 5

    assert summary["records_with_away_state"] == 0


# ============================================================
# TEST RUNNER
# ============================================================

if __name__ == "__main__":
    """
    Run all tests directly without requiring pytest.
    """

    test_walk_forward_dataset_size()

    test_test_seasons()

    test_records_per_fold()

    test_actual_result_is_preserved()

    test_first_fixture_has_no_prior_team_state()

    test_target_match_is_not_in_team_state()

    test_away_team_state_is_pre_match_state()

    test_state_cutoff_matches_fixture_kickoff()

    test_previous_match_is_available_to_later_fixture()

    test_recent_form_uses_only_prior_matches()

    test_summary()

    print(
        "All walk-forward data tests passed."
    )