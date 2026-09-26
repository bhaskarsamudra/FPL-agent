"""
Test suite for historical team match data.

This test file validates that historical Premier League match data
has been loaded and normalized correctly by historical_team_data.py.

The tests cover:
1. Total number of matches
2. Matches per season
3. Unique match IDs
4. Canonical schema
5. Required fields
6. Result values
7. Home/away team integrity
8. Numeric match statistics
9. Source provenance
10. Source retrieval timestamps
"""

import pandas as pd

from historical_team_data import load_historical_team_matches


# ---------------------------------------------------------------------------
# EXPECTED CANONICAL COLUMNS
# ---------------------------------------------------------------------------

EXPECTED_COLUMNS = [
    # Identity
    "match_id",
    "season",
    "match_date",
    "kickoff_datetime",
    "home_team",
    "away_team",

    # Result
    "home_goals",
    "away_goals",
    "result",
    "home_ht_goals",
    "away_ht_goals",
    "ht_result",

    # Match statistics
    "home_shots",
    "away_shots",
    "home_shots_on_target",
    "away_shots_on_target",
    "home_corners",
    "away_corners",
    "home_fouls",
    "away_fouls",
    "home_yellow_cards",
    "away_yellow_cards",
    "home_red_cards",
    "away_red_cards",

    # Provenance
    "source",
    "source_url",
    "source_season_code",
    "source_retrieved_at",
]


# ---------------------------------------------------------------------------
# TEST 1 — TOTAL MATCH COUNT
# ---------------------------------------------------------------------------

def test_total_match_count(historical_matches: pd.DataFrame) -> None:
    """
    Verify that all six historical seasons contain 2,280 matches.

    Premier League structure:
        6 seasons × 380 matches = 2,280 matches
    """

    expected_total = 6 * 380

    assert len(historical_matches) == expected_total, (
        f"Expected {expected_total} matches, "
        f"but found {len(historical_matches)}."
    )

    print(f"PASS: Total match count = {expected_total}")


# ---------------------------------------------------------------------------
# TEST 2 — MATCHES PER SEASON
# ---------------------------------------------------------------------------

def test_matches_per_season(historical_matches: pd.DataFrame) -> None:
    """
    Verify that every historical season contains exactly 380 matches.
    """

    season_counts = historical_matches.groupby("season").size()

    assert len(season_counts) == 6, (
        f"Expected 6 seasons, but found {len(season_counts)}."
    )

    assert (season_counts == 380).all(), (
        f"Unexpected season match counts:\n{season_counts}"
    )

    print("PASS: Every season contains 380 matches")


# ---------------------------------------------------------------------------
# TEST 3 — UNIQUE MATCH IDS
# ---------------------------------------------------------------------------

def test_unique_match_ids(historical_matches: pd.DataFrame) -> None:
    """
    Verify that every canonical match ID is unique.
    """

    duplicate_count = historical_matches["match_id"].duplicated().sum()

    assert duplicate_count == 0, (
        f"Found {duplicate_count} duplicate match IDs."
    )

    print("PASS: All match IDs are unique")


# ---------------------------------------------------------------------------
# TEST 4 — CANONICAL COLUMNS
# ---------------------------------------------------------------------------

def test_canonical_columns(historical_matches: pd.DataFrame) -> None:
    """
    Verify that every expected canonical column exists.
    """

    missing_columns = [
        column
        for column in EXPECTED_COLUMNS
        if column not in historical_matches.columns
    ]

    assert not missing_columns, (
        f"Missing canonical columns: {missing_columns}"
    )

    print("PASS: All canonical columns exist")


# ---------------------------------------------------------------------------
# TEST 5 — CANONICAL COLUMN COUNT
# ---------------------------------------------------------------------------

def test_canonical_column_count(historical_matches: pd.DataFrame) -> None:
    """
    Verify that the canonical DataFrame contains exactly 28 columns.

    This protects the canonical schema from accidental additions/removals.
    """

    expected_column_count = len(EXPECTED_COLUMNS)

    assert len(historical_matches.columns) == expected_column_count, (
        f"Expected {expected_column_count} columns, "
        f"but found {len(historical_matches.columns)}."
    )

    print(
        f"PASS: Canonical column count = {expected_column_count}"
    )


# ---------------------------------------------------------------------------
# TEST 6 — REQUIRED FIELDS
# ---------------------------------------------------------------------------

def test_required_fields(historical_matches: pd.DataFrame) -> None:
    """
    Verify that essential identity and result fields contain no missing data.
    """

    required_fields = [
        "match_id",
        "season",
        "match_date",
        "home_team",
        "away_team",
        "home_goals",
        "away_goals",
        "result",
    ]

    missing_counts = historical_matches[required_fields].isna().sum()

    assert missing_counts.sum() == 0, (
        f"Missing values found in required fields:\n{missing_counts}"
    )

    print("PASS: Required fields contain no missing values")


# ---------------------------------------------------------------------------
# TEST 7 — RESULT VALUES
# ---------------------------------------------------------------------------

def test_result_values(historical_matches: pd.DataFrame) -> None:
    """
    Verify that full-time results contain only:
        H = Home win
        D = Draw
        A = Away win
    """

    valid_results = {"H", "D", "A"}

    actual_results = set(
        historical_matches["result"].dropna().unique()
    )

    invalid_results = actual_results - valid_results

    assert not invalid_results, (
        f"Invalid result values found: {invalid_results}"
    )

    print("PASS: Result fields contain only H/D/A")


# ---------------------------------------------------------------------------
# TEST 8 — HOME/AWAY TEAM INTEGRITY
# ---------------------------------------------------------------------------

def test_home_away_teams(historical_matches: pd.DataFrame) -> None:
    """
    Verify that a team is never listed as both home and away
    in the same match.
    """

    invalid_rows = (
        historical_matches["home_team"]
        == historical_matches["away_team"]
    )

    invalid_count = invalid_rows.sum()

    assert invalid_count == 0, (
        f"Found {invalid_count} matches where home and away teams are identical."
    )

    print("PASS: Home and away teams are different")


# ---------------------------------------------------------------------------
# TEST 9 — NUMERIC MATCH STATISTICS
# ---------------------------------------------------------------------------

def test_numeric_statistics(historical_matches: pd.DataFrame) -> None:
    """
    Verify that numerical match statistics contain numeric values.

    These are the canonical fields currently sourced from Football-Data.co.uk.
    """

    numeric_fields = [
        "home_goals",
        "away_goals",
        "home_ht_goals",
        "away_ht_goals",
        "home_shots",
        "away_shots",
        "home_shots_on_target",
        "away_shots_on_target",
        "home_corners",
        "away_corners",
        "home_fouls",
        "away_fouls",
        "home_yellow_cards",
        "away_yellow_cards",
        "home_red_cards",
        "away_red_cards",
    ]

    non_numeric_fields = []

    for field in numeric_fields:
        if not pd.api.types.is_numeric_dtype(
            historical_matches[field]
        ):
            non_numeric_fields.append(field)

    assert not non_numeric_fields, (
        f"Non-numeric statistics found: {non_numeric_fields}"
    )

    print("PASS: Match statistics are numeric")


# ---------------------------------------------------------------------------
# TEST 10 — SOURCE PROVENANCE
# ---------------------------------------------------------------------------

def test_source_provenance(historical_matches: pd.DataFrame) -> None:
    """
    Verify that every record contains source provenance information.
    """

    provenance_fields = [
        "source",
        "source_url",
        "source_season_code",
    ]

    missing_counts = historical_matches[provenance_fields].isna().sum()

    assert missing_counts.sum() == 0, (
        f"Missing source provenance:\n{missing_counts}"
    )

    print("PASS: Source provenance is present")

    # Verify that every historical match has a valid retrieval timestamp.
    assert historical_matches["source_retrieved_at"].notna().all(), (
        "Some records have missing source_retrieved_at timestamps."
    )

    # Verify that pandas recognizes the field as a datetime column.
    assert pd.api.types.is_datetime64_any_dtype(
        historical_matches["source_retrieved_at"]
    ), "source_retrieved_at must contain datetime values."

    print("PASS: Source retrieval timestamps are valid")


# ---------------------------------------------------------------------------
# MAIN TEST RUNNER
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    print("\n" + "#" * 70)
    print("HISTORICAL TEAM DATA — TEST SUITE")
    print("#" * 70)

    # Load all six historical Premier League seasons.
    historical_matches = load_historical_team_matches()

    print(
        f"\nLoaded {len(historical_matches)} historical matches."
    )

    # Run all validation tests.
    test_total_match_count(historical_matches)
    test_matches_per_season(historical_matches)
    test_unique_match_ids(historical_matches)
    test_canonical_columns(historical_matches)
    test_canonical_column_count(historical_matches)
    test_required_fields(historical_matches)
    test_result_values(historical_matches)
    test_home_away_teams(historical_matches)
    test_numeric_statistics(historical_matches)
    test_source_provenance(historical_matches)

    print("\n" + "=" * 70)
    print("ALL HISTORICAL TEAM DATA TESTS PASSED")
    print("=" * 70)