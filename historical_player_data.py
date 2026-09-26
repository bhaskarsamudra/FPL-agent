"""
Historical FPL player data ingestion.

Purpose
-------
This module downloads and standardizes historical Fantasy Premier League
player/gameweek data for the 2020/21 through 2025/26 seasons.

Important design principles
----------------------------
1. Vaastav's merged_gw.csv is used as the primary historical FPL source.
2. The canonical grain is ONE ROW PER PLAYER PER FIXTURE.
3. We do not invent missing historical values.
4. Missing fields remain NULL/NaN.
5. xP is deliberately excluded from the canonical predictive dataset
   because the source documentation warns about potential look-ahead bias.
6. Source provenance is retained.
7. Exact duplicate source rows are removed only after validation.
8. Conflicting duplicate player-fixture records cause validation to fail.
9. This module is an ingestion layer. It does NOT perform prediction.
"""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Any

import pandas as pd
import requests


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# These are the six completed seasons selected for model development.
HISTORICAL_SEASONS = [
    "2020-21",
    "2021-22",
    "2022-23",
    "2023-24",
    "2024-25",
    "2025-26",
]


# Base location of the Vaastav historical FPL repository.
BASE_URL = (
    "https://raw.githubusercontent.com/"
    "vaastav/Fantasy-Premier-League/master/data/"
)


# ---------------------------------------------------------------------------
# Canonical schema
# ---------------------------------------------------------------------------

# These are the fields that our application will use as the standard
# historical player/gameweek representation.
#
# Some fields did not exist in older seasons.
# Those fields remain NULL rather than being fabricated.
CANONICAL_COLUMNS = [
    # Identity
    "season",
    "gameweek",
    "player_id",
    "player_name",
    "position",
    "team",
    "opponent_team",
    "fixture_id",

    # Fixture context
    "kickoff_time",
    "was_home",

    # Playing time
    "minutes",
    "starts",

    # FPL scoring
    "total_points",
    "goals_scored",
    "assists",
    "clean_sheets",
    "goals_conceded",
    "own_goals",
    "penalties_saved",
    "penalties_missed",
    "saves",
    "bonus",
    "bps",
    "yellow_cards",
    "red_cards",

    # Underlying / performance metrics
    "expected_goals",
    "expected_assists",
    "expected_goal_involvements",
    "expected_goals_conceded",

    # Other performance indicators
    "creativity",
    "influence",
    "threat",
    "ict_index",

    # Defensive contribution metrics
    "clearances_blocks_interceptions",
    "recoveries",
    "tackles",
    "defensive_contribution",

    # Historical price / ownership information
    "value",
    "selected",
    "transfers_balance",
    "transfers_in",
    "transfers_out",

    # Provenance
    "source",
    "source_url",
    "source_retrieved_at",
]


# These columns define the actual football/FPL record.
#
# Provenance fields are deliberately excluded because two identical source
# records may have different retrieval timestamps.
RECORD_COLUMNS = [
    column
    for column in CANONICAL_COLUMNS
    if column not in {
        "source",
        "source_url",
        "source_retrieved_at",
    }
]


# ---------------------------------------------------------------------------
# Source helpers
# ---------------------------------------------------------------------------

def build_source_url(season: str) -> str:
    """
    Build the raw GitHub URL for a historical season.

    Example
    -------
    2023-24 becomes:

    https://raw.githubusercontent.com/vaastav/Fantasy-Premier-League/
    master/data/2023-24/gws/merged_gw.csv
    """

    return f"{BASE_URL}{season}/gws/merged_gw.csv"


def download_season_data(
    season: str,
    timeout_seconds: int = 60,
) -> tuple[pd.DataFrame, str]:
    """
    Download one historical season from Vaastav.

    Parameters
    ----------
    season:
        Season identifier such as "2023-24".

    timeout_seconds:
        Maximum time allowed for the HTTP request.

    Returns
    -------
    tuple[pd.DataFrame, str]
        Downloaded DataFrame and source URL.

    Raises
    ------
    RuntimeError
        If the source cannot be downloaded or contains no records.
    """

    # Build the exact source URL.
    source_url = build_source_url(season)

    # Download the CSV file.
    response = requests.get(
        source_url,
        timeout=timeout_seconds,
    )

    # Raise an exception if GitHub returned an HTTP error.
    response.raise_for_status()

    # Convert downloaded bytes into a pandas DataFrame.
    dataframe = pd.read_csv(BytesIO(response.content))

    # Make sure the source actually contains records.
    if dataframe.empty:
        raise RuntimeError(
            f"No records were returned for season {season}."
        )

    return dataframe, source_url


# ---------------------------------------------------------------------------
# Data standardization
# ---------------------------------------------------------------------------

def _rename_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    """
    Rename Vaastav columns into our canonical naming convention.

    The source uses:
        element -> FPL player ID
        GW      -> gameweek
        fixture -> fixture ID
        name    -> player name
    """

    rename_map = {
        "GW": "gameweek",
        "element": "player_id",
        "name": "player_name",
        "fixture": "fixture_id",
    }

    return dataframe.rename(columns=rename_map)


def _add_missing_columns(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Add canonical columns that do not exist in a particular season.

    Older seasons do not contain every modern FPL metric.

    We therefore add those columns as NULL/NaN rather than assuming
    that a missing metric means zero.
    """

    for column in CANONICAL_COLUMNS:
        if column not in dataframe.columns:
            dataframe[column] = pd.NA

    return dataframe


def _standardize_data_types(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Convert important columns into consistent pandas data types.
    """

    # Columns that should behave like integers.
    integer_columns = [
        "gameweek",
        "player_id",
        "fixture_id",
        "minutes",
        "starts",
        "total_points",
        "goals_scored",
        "assists",
        "clean_sheets",
        "goals_conceded",
        "own_goals",
        "penalties_saved",
        "penalties_missed",
        "saves",
        "bonus",
        "bps",
        "yellow_cards",
        "red_cards",
        "clearances_blocks_interceptions",
        "recoveries",
        "tackles",
        "defensive_contribution",
        "value",
        "transfers_balance",
        "transfers_in",
        "transfers_out",
    ]

    # Columns that can contain decimal values.
    numeric_columns = [
        "expected_goals",
        "expected_assists",
        "expected_goal_involvements",
        "expected_goals_conceded",
        "creativity",
        "influence",
        "threat",
        "ict_index",
        "selected",
    ]

    # Convert integer-like fields to pandas nullable integers.
    for column in integer_columns:
        dataframe[column] = pd.to_numeric(
            dataframe[column],
            errors="coerce",
        ).astype("Int64")

    # Convert decimal/statistical fields to numeric.
    for column in numeric_columns:
        dataframe[column] = pd.to_numeric(
            dataframe[column],
            errors="coerce",
        )

    # Convert home/away information to nullable Boolean.
    if "was_home" in dataframe.columns:
        dataframe["was_home"] = dataframe["was_home"].astype("boolean")

    # Convert kickoff timestamp into UTC.
    dataframe["kickoff_time"] = pd.to_datetime(
        dataframe["kickoff_time"],
        errors="coerce",
        utc=True,
    )

    return dataframe


# ---------------------------------------------------------------------------
# Duplicate handling
# ---------------------------------------------------------------------------

def _handle_duplicate_records(
    dataframe: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """
    Validate and remove duplicate player-fixture records.

    There are two possible situations.

    Situation 1
    ----------
    Exact duplicate rows exist.

    Example:

        player 123 + fixture 456
        player 123 + fixture 456

    and every football/FPL field is identical.

    These are safe to collapse to one record.

    Situation 2
    ----------
    The same player + fixture appears multiple times but the actual
    football/FPL values differ.

    This is dangerous and must NOT be silently resolved.

    In that case the function raises ValueError.
    """

    # Count rows before duplicate processing.
    rows_before = len(dataframe)

    # Identify duplicate player-fixture keys.
    duplicate_mask = dataframe.duplicated(
        subset=[
            "player_id",
            "fixture_id",
        ],
        keep=False,
    )

    duplicate_rows = dataframe.loc[duplicate_mask].copy()

    # If there are no duplicate keys, nothing needs to be done.
    if duplicate_rows.empty:
        return dataframe, {
            "duplicate_rows_found": 0,
            "exact_duplicate_rows_removed": 0,
            "conflicting_duplicate_rows": 0,
        }

    # -----------------------------------------------------------------------
    # Check whether every duplicate key contains identical actual records.
    # -----------------------------------------------------------------------

    conflicting_keys: list[tuple[Any, Any]] = []

    grouped = duplicate_rows.groupby(
        [
            "player_id",
            "fixture_id",
        ],
        dropna=False,
    )

    for key, group in grouped:
        # Remove provenance columns before comparing.
        comparison = group[RECORD_COLUMNS].copy()

        # Reset index so equality is not affected by original row numbers.
        comparison = comparison.reset_index(drop=True)

        # A group is safe if every record is identical to the first record.
        first_record = comparison.iloc[0]

        all_identical = comparison.eq(first_record).all().all()

        if not all_identical:
            conflicting_keys.append(key)

    # -----------------------------------------------------------------------
    # Conflicting duplicate records are a hard validation failure.
    # -----------------------------------------------------------------------

    if conflicting_keys:
        example_keys = conflicting_keys[:10]

        raise ValueError(
            "Conflicting duplicate player-fixture records were found. "
            "The same player_id + fixture_id contains different FPL data. "
            f"Examples: {example_keys}"
        )

    # -----------------------------------------------------------------------
    # At this point all duplicates are exact duplicates.
    #
    # Keep the first copy and remove subsequent identical copies.
    # -----------------------------------------------------------------------

    cleaned = dataframe.drop_duplicates(
        subset=[
            "player_id",
            "fixture_id",
        ],
        keep="first",
    ).reset_index(drop=True)

    rows_after = len(cleaned)

    removed = rows_before - rows_after

    return cleaned, {
        "duplicate_rows_found": len(duplicate_rows),
        "exact_duplicate_rows_removed": removed,
        "conflicting_duplicate_rows": 0,
    }


# ---------------------------------------------------------------------------
# Data standardization
# ---------------------------------------------------------------------------

def standardize_season_data(
    dataframe: pd.DataFrame,
    season: str,
    source_url: str,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """
    Convert one raw season DataFrame into the canonical schema.

    Returns
    -------
    tuple[pd.DataFrame, dict]
        Standardized data and duplicate-processing statistics.
    """

    # Work on a copy so the original downloaded DataFrame is untouched.
    data = dataframe.copy()

    # Rename source-specific columns.
    data = _rename_columns(data)

    # Add the season identifier.
    data["season"] = season

    # Add canonical columns that may be missing in older seasons.
    data = _add_missing_columns(data)

    # Convert values into consistent data types.
    data = _standardize_data_types(data)

    # Record exactly when this source was retrieved.
    retrieval_time = datetime.now(timezone.utc)

    data["source"] = "vaastav_fpl_historical_dataset"
    data["source_url"] = source_url
    data["source_retrieved_at"] = retrieval_time

    # -----------------------------------------------------------------------
    # IMPORTANT:
    #
    # xP is intentionally NOT included in CANONICAL_COLUMNS.
    #
    # The Vaastav documentation warns that xP may contain look-ahead
    # information because the dataset is scraped after the gameweek.
    #
    # Therefore we do not allow xP to accidentally enter the predictive
    # dataset.
    # -----------------------------------------------------------------------

    # Keep only our canonical columns.
    data = data[CANONICAL_COLUMNS]

    # Handle duplicate player-fixture records safely.
    data, duplicate_stats = _handle_duplicate_records(data)

    # Sort records into a predictable order.
    data = data.sort_values(
        by=[
            "season",
            "gameweek",
            "player_id",
            "fixture_id",
        ],
        na_position="last",
    ).reset_index(drop=True)

    return data, duplicate_stats


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_season_data(
    dataframe: pd.DataFrame,
    season: str,
    duplicate_stats: dict[str, int],
) -> dict[str, Any]:
    """
    Validate the canonical data for one season.

    The function returns a validation report.
    """

    report: dict[str, Any] = {
        "season": season,
        "rows": len(dataframe),
        "unique_players": dataframe["player_id"].nunique(),
        "unique_fixtures": dataframe["fixture_id"].nunique(),
        "gameweeks": sorted(
            dataframe["gameweek"]
            .dropna()
            .astype(int)
            .unique()
            .tolist()
        ),
        "duplicate_player_fixture_rows": 0,
        "duplicate_rows_found": duplicate_stats[
            "duplicate_rows_found"
        ],
        "exact_duplicate_rows_removed": duplicate_stats[
            "exact_duplicate_rows_removed"
        ],
        "conflicting_duplicate_rows": duplicate_stats[
            "conflicting_duplicate_rows"
        ],
        "missing_player_ids": int(
            dataframe["player_id"].isna().sum()
        ),
        "missing_fixture_ids": int(
            dataframe["fixture_id"].isna().sum()
        ),
        "missing_gameweeks": int(
            dataframe["gameweek"].isna().sum()
        ),
        "valid": True,
    }

    # After exact duplicates have been removed, the canonical dataset
    # should contain one record per player + fixture.
    remaining_duplicates = int(
        dataframe.duplicated(
            subset=[
                "player_id",
                "fixture_id",
            ],
            keep=False,
        ).sum()
    )

    report["duplicate_player_fixture_rows"] = remaining_duplicates

    # These conditions make the canonical dataset invalid.
    if remaining_duplicates > 0:
        report["valid"] = False

    if report["missing_player_ids"] > 0:
        report["valid"] = False

    if report["missing_fixture_ids"] > 0:
        report["valid"] = False

    if report["missing_gameweeks"] > 0:
        report["valid"] = False

    if report["conflicting_duplicate_rows"] > 0:
        report["valid"] = False

    return report


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_historical_player_data(
    seasons: list[str] | None = None,
) -> pd.DataFrame:
    """
    Download and combine historical player/gameweek data.

    Parameters
    ----------
    seasons:
        Optional list of seasons.

        If omitted, all six selected historical seasons are loaded.

    Returns
    -------
    pandas.DataFrame
        Canonical historical player/gameweek dataset.
    """

    # Use our six-season historical window by default.
    seasons_to_load = (
        HISTORICAL_SEASONS
        if seasons is None
        else seasons
    )

    all_seasons: list[pd.DataFrame] = []

    # Process each season independently.
    for season in seasons_to_load:
        print(f"Downloading historical player data: {season}")

        raw_data, source_url = download_season_data(season)

        canonical_data, duplicate_stats = (
            standardize_season_data(
                raw_data,
                season,
                source_url,
            )
        )

        validation = validate_season_data(
            canonical_data,
            season,
            duplicate_stats,
        )

        # Print a compact validation summary.
        print(
            f"  Rows: {validation['rows']:,}"
        )

        print(
            f"  Players: {validation['unique_players']:,}"
        )

        print(
            f"  Fixtures: {validation['unique_fixtures']:,}"
        )

        print(
            f"  Gameweeks: {validation['gameweeks']}"
        )

        print(
            "  Duplicate player-fixture rows remaining: "
            f"{validation['duplicate_player_fixture_rows']}"
        )

        print(
            "  Exact duplicate rows removed: "
            f"{validation['exact_duplicate_rows_removed']}"
        )

        if not validation["valid"]:
            raise ValueError(
                "Historical player data validation failed "
                f"for season {season}: {validation}"
            )

        all_seasons.append(canonical_data)

    # Combine all seasons into one DataFrame.
    combined = pd.concat(
        all_seasons,
        ignore_index=True,
    )

    # Final deterministic sort.
    combined = combined.sort_values(
        by=[
            "season",
            "gameweek",
            "player_id",
            "fixture_id",
        ],
        na_position="last",
    ).reset_index(drop=True)

    return combined


# ---------------------------------------------------------------------------
# Simple manual test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    """
    Run this file directly to perform a basic six-season ingestion test.

    Example:
        python historical_player_data.py
    """

    historical_data = load_historical_player_data()

    print("\n" + "=" * 70)
    print("HISTORICAL PLAYER DATA SUMMARY")
    print("=" * 70)

    print(
        f"Total rows: {len(historical_data):,}"
    )

    print(
        "Unique player IDs: "
        f"{historical_data['player_id'].nunique():,}"
    )

    print(
        "Unique fixtures: "
        f"{historical_data['fixture_id'].nunique():,}"
    )

    print("\nRows by season:")

    print(
        historical_data
        .groupby("season")
        .size()
        .to_string()
    )

    print("\nCanonical columns:")

    print(
        historical_data.columns.tolist()
    )

    print("\nAdvanced metrics availability:")

    for column in [
        "expected_goals",
        "expected_assists",
        "expected_goal_involvements",
        "expected_goals_conceded",
        "defensive_contribution",
    ]:
        available = historical_data[column].notna().sum()
        total = len(historical_data)

        percentage = (
            available / total * 100
            if total > 0
            else 0
        )

        print(
            f"  {column}: "
            f"{available:,}/{total:,} "
            f"({percentage:.1f}%)"
        )

    print(
        "\nHistorical player data ingestion "
        "completed successfully."
    )