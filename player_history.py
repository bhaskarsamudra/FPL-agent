"""
Player history utilities for the FPL agent.

This module converts the official FPL player-summary data
into a normalized gameweek-by-gameweek player history.

The official FPL endpoint provides:

    element-summary/{player_id}/

Its "history" section contains the player's current-season
gameweek-by-gameweek performance.

This module is responsible for STRUCTURING that data.

API retrieval itself belongs in fpl_truth.py.
"""


# Fields that we want to preserve from the official FPL
# player-history response.
PLAYER_HISTORY_FIELDS = [
    "element",
    "fixture",
    "opponent_team",
    "total_points",
    "was_home",
    "kickoff_time",
    "team_h_score",
    "team_a_score",
    "round",
    "modified",
    "minutes",
    "goals_scored",
    "assists",
    "clean_sheets",
    "goals_conceded",
    "own_goals",
    "penalties_saved",
    "penalties_missed",
    "yellow_cards",
    "red_cards",
    "saves",
    "bonus",
    "bps",
    "influence",
    "creativity",
    "threat",
    "ict_index",
    "clearances_blocks_interceptions",
    "recoveries",
    "tackles",
    "defensive_contribution",
    "starts",
    "expected_goals",
    "expected_assists",
    "expected_goal_involvements",
    "expected_goals_conceded",
    "value",
    "transfers_balance",
    "selected",
    "transfers_in",
    "transfers_out",
]


def build_player_history(player_summary):
    """
    Build a normalized current-season player history.

    Parameters:
        player_summary:
            Official player summary returned by
            fpl_truth.get_player_summary(player_id).

    Returns:
        A list containing one record per player per gameweek.

    Raises:
        ValueError if the player summary or history section
        is missing or invalid.
    """

    # --------------------------------------------------------
    # CHECK 1:
    # Make sure the player summary is a dictionary.
    # --------------------------------------------------------

    if not isinstance(player_summary, dict):
        raise ValueError(
            "Player summary must be a dictionary."
        )

    # --------------------------------------------------------
    # CHECK 2:
    # Make sure the current-season history exists.
    # --------------------------------------------------------

    if "history" not in player_summary:
        raise ValueError(
            "Player summary is missing the 'history' section."
        )

    history = player_summary["history"]

    # --------------------------------------------------------
    # CHECK 3:
    # Make sure history is a list.
    # --------------------------------------------------------

    if not isinstance(history, list):
        raise ValueError(
            "Player history must be a list."
        )

    # --------------------------------------------------------
    # Build normalized records.
    # --------------------------------------------------------

    normalized_history = []

    for gameweek_record in history:

        # Make sure each gameweek record is a dictionary.
        if not isinstance(gameweek_record, dict):
            raise ValueError(
                "Each player history record must be a dictionary."
            )

        # ----------------------------------------------------
        # Create a clean record containing the fields we want.
        #
        # We deliberately use .get() so that if the FPL API
        # adds/removes an optional field in the future, the
        # entire process does not fail unnecessarily.
        # ----------------------------------------------------

        normalized_record = {
            field: gameweek_record.get(field)
            for field in PLAYER_HISTORY_FIELDS
        }

        # ----------------------------------------------------
        # Add a clearer name for the gameweek.
        #
        # "round" is the name used by the FPL API.
        # "gameweek" is easier for our strategy engine to use.
        # ----------------------------------------------------

        normalized_record["gameweek"] = gameweek_record.get(
            "round"
        )

        # ----------------------------------------------------
        # Add a clearer name for the player ID.
        #
        # The API calls this "element".
        # Our architecture consistently uses "player_id".
        # ----------------------------------------------------

        normalized_record["player_id"] = gameweek_record.get(
            "element"
        )

        # ----------------------------------------------------
        # Add a clearer name for the fixture ID.
        # ----------------------------------------------------

        normalized_record["fixture_id"] = gameweek_record.get(
            "fixture"
        )

        # Add the normalized record to our history list.
        normalized_history.append(normalized_record)

    # --------------------------------------------------------
    # Return the complete current-season history.
    # --------------------------------------------------------

    return normalized_history