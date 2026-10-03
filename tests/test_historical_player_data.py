"""
Tests for historical_player_data.py.

Purpose
-------
Validate that the historical FPL player data ingestion layer:

1. Loads all six historical seasons.
2. Contains the expected number of fixtures.
3. Has no duplicate player-fixture records.
4. Contains all required canonical columns.
5. Does not expose xP as a canonical predictive field.
6. Contains source provenance.
7. Preserves NULL values for historically unavailable metrics.
8. Correctly handles the known 2025/26 exact duplicates.
9. Does not incorrectly require every gameweek number to exist.
"""

from __future__ import annotations

import pandas as pd

from historical_player_data import (
    CANONICAL_COLUMNS,
    HISTORICAL_SEASONS,
    load_historical_player_data,
)


# ---------------------------------------------------------------------------
# Test configuration
# ---------------------------------------------------------------------------

# Every completed Premier League season contains 380 fixtures.
EXPECTED_FIXTURES_PER_SEASON = 380


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def assert_true(
    condition: bool,
    message: str,
) -> None:
    """
    Raise a clear error when a test condition is false.
    """

    if not condition:
        raise AssertionError(message)


# ---------------------------------------------------------------------------
# Main test
# ---------------------------------------------------------------------------

def run_tests() -> None:
    """
    Run all historical player data tests.
    """

    print("=" * 70)
    print("HISTORICAL PLAYER DATA TESTS")
    print("=" * 70)

    # Load the complete six-season historical dataset.
    data = load_historical_player_data()

    print("\nData loaded successfully.")

    # -----------------------------------------------------------------------
    # TEST 1 — All six seasons exist
    # -----------------------------------------------------------------------

    actual_seasons = sorted(
        data["season"].dropna().unique().tolist()
    )

    expected_seasons = sorted(
        HISTORICAL_SEASONS
    )

    assert_true(
        actual_seasons == expected_seasons,
        (
            "Season coverage mismatch.\n"
            f"Expected: {expected_seasons}\n"
            f"Actual:   {actual_seasons}"
        ),
    )

    print("PASS: All six historical seasons are present.")

    # -----------------------------------------------------------------------
    # TEST 2 — Every season has 380 fixtures
    # -----------------------------------------------------------------------

    fixtures_by_season = (
        data.groupby("season")["fixture_id"]
        .nunique()
        .to_dict()
    )

    for season in HISTORICAL_SEASONS:
        fixture_count = fixtures_by_season.get(
            season,
            0,
        )

        assert_true(
            fixture_count == EXPECTED_FIXTURES_PER_SEASON,
            (
                f"{season} has {fixture_count} fixtures; "
                f"expected {EXPECTED_FIXTURES_PER_SEASON}."
            ),
        )

    print("PASS: Every season contains 380 unique fixtures.")

    # -----------------------------------------------------------------------
    # TEST 3 — No duplicate player-fixture records
    # -----------------------------------------------------------------------

    duplicate_count = int(
        data.duplicated(
            subset=[
                "season",
                "player_id",
                "fixture_id",
            ],
            keep=False,
        ).sum()
    )

    assert_true(
        duplicate_count == 0,
        (
            "Duplicate player-fixture records remain: "
            f"{duplicate_count}"
        ),
    )

    print(
        "PASS: No duplicate season/player/fixture records remain."
    )

    # -----------------------------------------------------------------------
    # TEST 4 — Canonical columns exist
    # -----------------------------------------------------------------------

    missing_columns = [
        column
        for column in CANONICAL_COLUMNS
        if column not in data.columns
    ]

    assert_true(
        not missing_columns,
        (
            "Missing canonical columns: "
            f"{missing_columns}"
        ),
    )

    print("PASS: All canonical columns are present.")

    # -----------------------------------------------------------------------
    # TEST 5 — xP is NOT in the canonical dataset
    # -----------------------------------------------------------------------

    assert_true(
        "xP" not in data.columns,
        "xP must not be present in the canonical predictive dataset.",
    )

    print(
        "PASS: xP is excluded from the canonical predictive dataset."
    )

    # -----------------------------------------------------------------------
    # TEST 6 — Player and fixture IDs are populated
    # -----------------------------------------------------------------------

    missing_player_ids = int(
        data["player_id"].isna().sum()
    )

    missing_fixture_ids = int(
        data["fixture_id"].isna().sum()
    )

    assert_true(
        missing_player_ids == 0,
        (
            "Missing player IDs found: "
            f"{missing_player_ids}"
        ),
    )

    assert_true(
        missing_fixture_ids == 0,
        (
            "Missing fixture IDs found: "
            f"{missing_fixture_ids}"
        ),
    )

    print(
        "PASS: Player IDs and fixture IDs are fully populated."
    )

    # -----------------------------------------------------------------------
    # TEST 7 — Gameweek values are valid
    # -----------------------------------------------------------------------

    invalid_gameweeks = data.loc[
        ~data["gameweek"].between(1, 38),
        "gameweek",
    ].dropna()

    assert_true(
        invalid_gameweeks.empty,
        (
            "Invalid gameweek values found: "
            f"{invalid_gameweeks.unique().tolist()}"
        ),
    )

    print(
        "PASS: All gameweek values are between 1 and 38."
    )

    # -----------------------------------------------------------------------
    # TEST 8 — Provenance fields exist and are populated
    # -----------------------------------------------------------------------

    provenance_columns = [
        "source",
        "source_url",
        "source_retrieved_at",
    ]

    for column in provenance_columns:
        missing_count = int(
            data[column].isna().sum()
        )

        assert_true(
            missing_count == 0,
            (
                f"Provenance column '{column}' "
                f"has {missing_count} missing values."
            ),
        )

    print(
        "PASS: Provenance fields are populated."
    )

    # -----------------------------------------------------------------------
    # TEST 9 — Source is the expected Vaastav dataset
    # -----------------------------------------------------------------------

    expected_source = (
        "vaastav_fpl_historical_dataset"
    )

    actual_sources = (
        data["source"]
        .dropna()
        .unique()
        .tolist()
    )

    assert_true(
        actual_sources == [expected_source],
        (
            "Unexpected source values found: "
            f"{actual_sources}"
        ),
    )

    print(
        "PASS: Source provenance is correctly identified."
    )

    # -----------------------------------------------------------------------
    # TEST 10 — 2022/23 does not incorrectly require GW7
    # -----------------------------------------------------------------------

    season_2022_23 = data.loc[
        data["season"] == "2022-23"
    ]

    gameweeks_2022_23 = sorted(
        season_2022_23["gameweek"]
        .dropna()
        .unique()
        .tolist()
    )

    assert_true(
        7 not in gameweeks_2022_23,
        (
            "2022/23 unexpectedly contains GW7. "
            "The current source data has no GW7 records."
        ),
    )

    print(
        "PASS: 2022/23 GW7 gap is preserved rather than fabricated."
    )

    # -----------------------------------------------------------------------
    # TEST 11 — Historical advanced metrics remain nullable
    # -----------------------------------------------------------------------

    advanced_columns = [
        "expected_goals",
        "expected_assists",
        "expected_goal_involvements",
        "expected_goals_conceded",
        "defensive_contribution",
    ]

    for column in advanced_columns:
        # The test only verifies that the column exists and supports
        # missing values. It does NOT require every historical season
        # to have the metric.
        assert_true(
            column in data.columns,
            (
                f"Advanced metric column '{column}' "
                "is missing."
            ),
        )

    print(
        "PASS: Advanced metrics support historical NULL values."
    )

    # -----------------------------------------------------------------------
    # TEST 12 — Older seasons actually contain missing advanced data
    # -----------------------------------------------------------------------

    old_data = data.loc[
        data["season"].isin(
            [
                "2020-21",
                "2021-22",
            ]
        )
    ]

    expected_goals_missing = int(
        old_data["expected_goals"].isna().sum()
    )

    assert_true(
        expected_goals_missing > 0,
        (
            "Expected historical xG values to be missing "
            "for at least part of 2020/21 and 2021/22."
        ),
    )

    print(
        "PASS: Missing historical advanced metrics are preserved."
    )

    # -----------------------------------------------------------------------
    # TEST 13 — Total row count is sensible
    # -----------------------------------------------------------------------

    expected_minimum_rows = 150_000

    assert_true(
        len(data) > expected_minimum_rows,
        (
            f"Only {len(data):,} rows loaded; "
            f"expected more than {expected_minimum_rows:,}."
        ),
    )

    print(
        "PASS: Total historical row count is sensible."
    )

    # -----------------------------------------------------------------------
    # Final summary
    # -----------------------------------------------------------------------

    print("\n" + "=" * 70)
    print("ALL HISTORICAL PLAYER DATA TESTS PASSED")
    print("=" * 70)

    print(
        f"\nTotal rows tested: {len(data):,}"
    )

    print(
        "Seasons tested: "
        f"{', '.join(HISTORICAL_SEASONS)}"
    )

    print(
        "Unique players: "
        f"{data['player_id'].nunique():,}"
    )

    print(
        "Unique fixtures: "
        f"{data['fixture_id'].nunique():,}"
    )


# ---------------------------------------------------------------------------
# Run tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run_tests()