"""
Historical Team Data Ingestion
==============================

Purpose:
    Download and normalize historical Premier League match data
    from Football-Data.co.uk.

This module is intentionally limited to INGESTION and NORMALIZATION.

It does NOT:
    - calculate team strength
    - calculate fixture difficulty
    - make predictions
    - calculate expected points
    - make FPL recommendations

Source:
    Football-Data.co.uk Premier League E0.csv

Historical seasons:
    2020/21 through 2025/26
"""

# -------------------------------------------------------------------
# IMPORTS
# -------------------------------------------------------------------

# pandas is used to download, read and transform the CSV files.
import pandas as pd


# -------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------

# Football-Data.co.uk uses a season code in its URL.
#
# Example:
#   2020/21 -> 2021
#   2021/22 -> 2122
#   ...
#   2025/26 -> 2526
SEASONS = {
    "2020/21": "2021",
    "2021/22": "2122",
    "2022/23": "2223",
    "2023/24": "2324",
    "2024/25": "2425",
    "2025/26": "2526",
}


# Columns from the raw Football-Data file that we need.
#
# We deliberately select only the fields required by our
# canonical historical match schema.
RAW_COLUMNS = [
    "Date",
    "Time",
    "HomeTeam",
    "AwayTeam",
    "FTHG",
    "FTAG",
    "FTR",
    "HTHG",
    "HTAG",
    "HTR",
    "HS",
    "AS",
    "HST",
    "AST",
    "HF",
    "AF",
    "HC",
    "AC",
    "HY",
    "AY",
    "HR",
    "AR",
]


# -------------------------------------------------------------------
# SOURCE LOADING
# -------------------------------------------------------------------

def build_source_url(season_code):
    """
    Build the Football-Data.co.uk URL for a season.

    Example:
        2526 -> https://www.football-data.co.uk/mmz4281/2526/E0.csv
    """

    return (
        "https://www.football-data.co.uk/"
        f"mmz4281/{season_code}/E0.csv"
    )


def load_season(season, season_code):
    """
    Download one historical Premier League season.

    Args:
        season:
            Human-readable season such as "2025/26".

        season_code:
            Football-Data URL code such as "2526".

    Returns:
        Raw pandas DataFrame containing the required columns.
    """

    # Build the source URL.
    url = build_source_url(season_code)

    print(
        f"Loading Football-Data.co.uk "
        f"{season}..."
    )

    print(f"URL: {url}")

    # Read the CSV.
    #
    # Football-Data files use an encoding that is compatible with
    # cp1252. This was validated against all six seasons.
    df = pd.read_csv(
        url,
        encoding="cp1252",
    )

    # Remove whitespace around column names.
    df.columns = df.columns.str.strip()

    # Some Football-Data files can contain a UTF-8 BOM that is
    # interpreted as literal characters in the first column name.
    #
    # Removing it makes the schema stable.
    df.columns = df.columns.str.replace(
        "ï»¿",
        "",
        regex=False,
    )

    # Verify that every required raw column exists.
    missing_columns = [
        column
        for column in RAW_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"{season}: Missing required source columns: "
            f"{missing_columns}"
        )

    # Keep only the columns required by our canonical model.
    df = df[RAW_COLUMNS].copy()

    return df


# -------------------------------------------------------------------
# NORMALIZATION
# -------------------------------------------------------------------

def normalize_season(df, season, season_code):
    """
    Convert one raw Football-Data season into our canonical
    historical match schema.
    """

    # Work on a copy so that the original DataFrame is not modified.
    data = df.copy()

    # ---------------------------------------------------------------
    # DATE
    # ---------------------------------------------------------------

    # Football-Data dates are stored in day/month/year format.
    data["match_date"] = pd.to_datetime(
        data["Date"],
        dayfirst=True,
        errors="coerce",
    )

    # Make sure every date was successfully parsed.
    if data["match_date"].isna().any():
        raise ValueError(
            f"{season}: Invalid match date detected."
        )

    # ---------------------------------------------------------------
    # KICKOFF TIME
    # ---------------------------------------------------------------

    # Combine the historical date and time into one timestamp.
    #
    # We deliberately preserve this as a naive timestamp for now.
    # Timezone interpretation will be handled explicitly later rather
    # than silently assuming a timezone.
    data["kickoff_datetime"] = pd.to_datetime(
        data["Date"].astype(str)
        + " "
        + data["Time"].astype(str),
        dayfirst=True,
        errors="coerce",
    )

    if data["kickoff_datetime"].isna().any():
        raise ValueError(
            f"{season}: Invalid kickoff datetime detected."
        )

    # ---------------------------------------------------------------
    # TEAM NAMES
    # ---------------------------------------------------------------

    # Remove accidental whitespace from team names.
    data["home_team"] = (
        data["HomeTeam"]
        .astype(str)
        .str.strip()
    )

    data["away_team"] = (
        data["AwayTeam"]
        .astype(str)
        .str.strip()
    )

    # ---------------------------------------------------------------
    # RESULT FIELDS
    # ---------------------------------------------------------------

    data["home_goals"] = pd.to_numeric(
        data["FTHG"],
        errors="raise",
    ).astype(int)

    data["away_goals"] = pd.to_numeric(
        data["FTAG"],
        errors="raise",
    ).astype(int)

    data["result"] = (
        data["FTR"]
        .astype(str)
        .str.strip()
    )

    data["home_ht_goals"] = pd.to_numeric(
        data["HTHG"],
        errors="raise",
    ).astype(int)

    data["away_ht_goals"] = pd.to_numeric(
        data["HTAG"],
        errors="raise",
    ).astype(int)

    data["ht_result"] = (
        data["HTR"]
        .astype(str)
        .str.strip()
    )

    # ---------------------------------------------------------------
    # MATCH STATISTICS
    # ---------------------------------------------------------------

    # Shots
    data["home_shots"] = pd.to_numeric(
        data["HS"],
        errors="raise",
    ).astype(int)

    data["away_shots"] = pd.to_numeric(
        data["AS"],
        errors="raise",
    ).astype(int)

    # Shots on target
    data["home_shots_on_target"] = pd.to_numeric(
        data["HST"],
        errors="raise",
    ).astype(int)

    data["away_shots_on_target"] = pd.to_numeric(
        data["AST"],
        errors="raise",
    ).astype(int)

    # Corners
    data["home_corners"] = pd.to_numeric(
        data["HC"],
        errors="raise",
    ).astype(int)

    data["away_corners"] = pd.to_numeric(
        data["AC"],
        errors="raise",
    ).astype(int)

    # Fouls
    data["home_fouls"] = pd.to_numeric(
        data["HF"],
        errors="raise",
    ).astype(int)

    data["away_fouls"] = pd.to_numeric(
        data["AF"],
        errors="raise",
    ).astype(int)

    # Yellow cards
    data["home_yellow_cards"] = pd.to_numeric(
        data["HY"],
        errors="raise",
    ).astype(int)

    data["away_yellow_cards"] = pd.to_numeric(
        data["AY"],
        errors="raise",
    ).astype(int)

    # Red cards
    data["home_red_cards"] = pd.to_numeric(
        data["HR"],
        errors="raise",
    ).astype(int)

    data["away_red_cards"] = pd.to_numeric(
        data["AR"],
        errors="raise",
    ).astype(int)

    # ---------------------------------------------------------------
    # MATCH ID
    # ---------------------------------------------------------------

    # Create a deterministic project-level match ID.
    #
    # We use:
    #   season + date + home team + away team
    #
    # The same historical match will therefore always produce
    # the same ID when the source is reloaded.
    data["match_id"] = (
        data["season"].astype(str)
        + "_"
        + data["match_date"].dt.strftime("%Y%m%d")
        + "_"
        + data["home_team"]
        + "_"
        + data["away_team"]
    )

    # ---------------------------------------------------------------
    # PROVENANCE
    # ---------------------------------------------------------------

    # Record where this record came from.
    data["source"] = "Football-Data.co.uk"

    data["source_url"] = build_source_url(
    season_code
    )

    data["source_season_code"] = season_code

    # Record when this source file was retrieved.
    # UTC is used internally so timestamps remain consistent across environments.
    data["source_retrieved_at"] = pd.Timestamp.now(tz="UTC")

    # ---------------------------------------------------------------
    # CANONICAL COLUMN ORDER
    # ---------------------------------------------------------------

    canonical_columns = [
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

    # Return only the canonical fields.
    return data[canonical_columns].copy()


# -------------------------------------------------------------------
# PUBLIC FUNCTION
# -------------------------------------------------------------------

def load_historical_team_matches():
    """
    Load and normalize all six historical Premier League seasons.

    Returns:
        One pandas DataFrame containing 2,280 canonical match records.
    """

    normalized_seasons = []

    # Process every historical season.
    for season, season_code in SEASONS.items():

        # Download the raw season.
        raw_data = load_season(
            season,
            season_code,
        )

        # Add the season before generating the match ID.
        raw_data["season"] = season

        # Normalize the season into our canonical schema.
        normalized_data = normalize_season(
            raw_data,
            season,
            season_code,
        )

        normalized_seasons.append(
            normalized_data
        )

    # Combine all six seasons.
    historical_matches = pd.concat(
        normalized_seasons,
        ignore_index=True,
    )

    return historical_matches


# -------------------------------------------------------------------
# VALIDATION
# -------------------------------------------------------------------

def validate_historical_team_matches(df):
    """
    Validate the final canonical historical dataset.

    Expected:
        6 seasons
        380 matches per season
        2,280 matches total
    """

    # Expected total number of matches.
    expected_matches = 6 * 380

    # Check total row count.
    if len(df) != expected_matches:
        raise ValueError(
            f"Expected {expected_matches} matches, "
            f"found {len(df)}."
        )

    # Check for duplicate match IDs.
    duplicate_count = int(
        df["match_id"].duplicated().sum()
    )

    if duplicate_count > 0:
        raise ValueError(
            f"Found {duplicate_count} duplicate match IDs."
        )

    # Check each season.
    season_counts = (
        df.groupby("season")
        .size()
        .sort_index()
    )

    if not (season_counts == 380).all():
        raise ValueError(
            "One or more seasons does not contain "
            "exactly 380 matches."
        )

    # Check the result values.
    valid_results = {"H", "D", "A"}

    if not set(df["result"]).issubset(
        valid_results
    ):
        raise ValueError(
            "Invalid full-time result detected."
        )

    if not set(df["ht_result"]).issubset(
        valid_results
    ):
        raise ValueError(
            "Invalid half-time result detected."
        )

    # Check core fields for missing values.
    required_fields = [
        "match_id",
        "season",
        "match_date",
        "kickoff_datetime",
        "home_team",
        "away_team",
        "home_goals",
        "away_goals",
        "result",
    ]

    missing = df[required_fields].isna().sum()

    if missing.sum() > 0:
        raise ValueError(
            "Missing values found in canonical fields:\n"
            f"{missing[missing > 0]}"
        )

    print("\n" + "=" * 70)
    print("CANONICAL HISTORICAL TEAM DATA VALIDATION")
    print("=" * 70)

    print(
        f"Total matches: {len(df)}"
    )

    print(
        f"Expected matches: {expected_matches}"
    )

    print(
        f"Duplicate match IDs: {duplicate_count}"
    )

    print("\nMatches by season:")
    print(season_counts.to_string())

    print("\nValidation: PASS")


# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------

if __name__ == "__main__":

    # Load and normalize all six seasons.
    historical_matches = (
        load_historical_team_matches()
    )

    # Validate the resulting canonical dataset.
    validate_historical_team_matches(
        historical_matches
    )

    # Display a small sample so we can visually inspect the result.
    print("\nFirst 5 canonical records:")
    print(
        historical_matches.head(5).to_string(
            index=False
        )
    )

    print("\nCanonical columns:")
    print(
        list(historical_matches.columns)
    )