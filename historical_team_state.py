"""
historical_team_state.py

Builds a point-in-time team state from historical Premier League
match data.

Purpose
-------
This module answers:

    "What did we know about each team BEFORE a particular
     historical cutoff?"

This is critical for walk-forward validation.

We must NOT use matches that happened after the prediction
cutoff because doing so would create look-ahead bias.

This module is intentionally a measurement layer.

It does NOT:
    - make fixture predictions
    - calculate expected goals
    - calculate expected FPL points
    - recommend transfers
    - tune model parameters
"""

from __future__ import annotations

from typing import Any

import pandas as pd


# ============================================================
# CONSTANTS
# ============================================================

# Number of recent matches used for recent-form calculations.
RECENT_MATCH_COUNT = 5


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _safe_divide(
    numerator: float,
    denominator: float,
) -> float:
    """
    Divide two numbers safely.

    If there are no matches yet, return 0.0 rather than
    creating a division-by-zero error.
    """

    if denominator == 0:
        return 0.0

    return numerator / denominator


def _create_empty_team_state(
    team_name: str,
    season: str,
    cutoff_datetime: pd.Timestamp,
) -> dict[str, Any]:
    """
    Create the initial state container for one team.

    All performance values start at zero because no historical
    matches have been processed yet.

    The season and cutoff are stored with the state so that
    downstream validation can identify exactly what point in
    time this state represents.
    """

    return {
        # ----------------------------------------------------
        # Point-in-time metadata
        # ----------------------------------------------------

        "team_name": team_name,
        "season": season,
        "as_of_datetime": cutoff_datetime,

        # ----------------------------------------------------
        # Overall results
        # ----------------------------------------------------

        "played": 0,
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "points": 0,

        # ----------------------------------------------------
        # Overall goals
        # ----------------------------------------------------

        "goals_for": 0,
        "goals_against": 0,

        # ----------------------------------------------------
        # Home performance
        # ----------------------------------------------------

        "home_played": 0,
        "home_wins": 0,
        "home_draws": 0,
        "home_losses": 0,
        "home_points": 0,
        "home_goals_for": 0,
        "home_goals_against": 0,

        # ----------------------------------------------------
        # Away performance
        # ----------------------------------------------------

        "away_played": 0,
        "away_wins": 0,
        "away_draws": 0,
        "away_losses": 0,
        "away_points": 0,
        "away_goals_for": 0,
        "away_goals_against": 0,

        # ----------------------------------------------------
        # Recent five-match form
        # ----------------------------------------------------

        "recent_5_played": 0,
        "recent_5_wins": 0,
        "recent_5_draws": 0,
        "recent_5_losses": 0,
        "recent_5_points": 0,
        "recent_5_goals_for": 0,
        "recent_5_goals_against": 0,

        # ----------------------------------------------------
        # Derived metrics
        # ----------------------------------------------------

        "goal_difference": 0,

        "points_per_match": 0.0,
        "goals_per_match": 0.0,
        "goals_conceded_per_match": 0.0,

        "home_points_per_match": 0.0,
        "home_goals_per_match": 0.0,
        "home_goals_conceded_per_match": 0.0,

        "away_points_per_match": 0.0,
        "away_goals_per_match": 0.0,
        "away_goals_conceded_per_match": 0.0,

        "recent_5_points_per_match": 0.0,
        "recent_5_goals_per_match": 0.0,
        "recent_5_goals_conceded_per_match": 0.0,

        # ----------------------------------------------------
        # League position
        #
        # Assigned after all teams have been processed.
        # ----------------------------------------------------

        "rank": None,
    }


def _update_team_from_match(
    team: dict[str, Any],
    goals_for: int,
    goals_against: int,
    venue: str,
) -> None:
    """
    Update one team's cumulative state from one completed match.

    Parameters
    ----------
    team:
        Team state dictionary.

    goals_for:
        Goals scored by this team.

    goals_against:
        Goals conceded by this team.

    venue:
        Either "home" or "away".
    """

    # --------------------------------------------------------
    # Overall statistics
    # --------------------------------------------------------

    team["played"] += 1

    team["goals_for"] += goals_for
    team["goals_against"] += goals_against

    # Determine result and points.

    if goals_for > goals_against:

        team["wins"] += 1
        team["points"] += 3

        result = "win"

    elif goals_for == goals_against:

        team["draws"] += 1
        team["points"] += 1

        result = "draw"

    else:

        team["losses"] += 1

        result = "loss"

    # --------------------------------------------------------
    # Venue-specific statistics
    # --------------------------------------------------------

    if venue == "home":

        team["home_played"] += 1

        team["home_goals_for"] += goals_for
        team["home_goals_against"] += goals_against

        if result == "win":

            team["home_wins"] += 1
            team["home_points"] += 3

        elif result == "draw":

            team["home_draws"] += 1
            team["home_points"] += 1

        else:

            team["home_losses"] += 1

    elif venue == "away":

        team["away_played"] += 1

        team["away_goals_for"] += goals_for
        team["away_goals_against"] += goals_against

        if result == "win":

            team["away_wins"] += 1
            team["away_points"] += 3

        elif result == "draw":

            team["away_draws"] += 1
            team["away_points"] += 1

        else:

            team["away_losses"] += 1

    else:

        raise ValueError(
            "venue must be either 'home' or 'away'."
        )


def _calculate_recent_form(
    team: dict[str, Any],
    team_matches: list[dict[str, Any]],
) -> None:
    """
    Calculate the team's recent-form statistics.

    Only the most recent five matches BEFORE the cutoff
    are considered.
    """

    # Sort newest first.

    sorted_matches = sorted(
        team_matches,
        key=lambda match: match["kickoff_datetime"],
        reverse=True,
    )

    recent_matches = sorted_matches[
        :RECENT_MATCH_COUNT
    ]

    recent_played = 0
    recent_wins = 0
    recent_draws = 0
    recent_losses = 0
    recent_points = 0
    recent_goals_for = 0
    recent_goals_against = 0

    for match in recent_matches:

        # Determine whether this team was home or away.

        if match["home_team"] == team["team_name"]:

            goals_for = int(
                match["home_goals"]
            )

            goals_against = int(
                match["away_goals"]
            )

        else:

            goals_for = int(
                match["away_goals"]
            )

            goals_against = int(
                match["home_goals"]
            )

        recent_played += 1

        recent_goals_for += goals_for
        recent_goals_against += goals_against

        if goals_for > goals_against:

            recent_wins += 1
            recent_points += 3

        elif goals_for == goals_against:

            recent_draws += 1
            recent_points += 1

        else:

            recent_losses += 1

    # Store recent-form results.

    team["recent_5_played"] = recent_played
    team["recent_5_wins"] = recent_wins
    team["recent_5_draws"] = recent_draws
    team["recent_5_losses"] = recent_losses
    team["recent_5_points"] = recent_points

    team["recent_5_goals_for"] = recent_goals_for
    team["recent_5_goals_against"] = recent_goals_against


def _calculate_derived_metrics(
    team: dict[str, Any],
) -> None:
    """
    Calculate derived metrics after all eligible matches
    have been processed.
    """

    # --------------------------------------------------------
    # Overall metrics
    # --------------------------------------------------------

    team["goal_difference"] = (
        team["goals_for"]
        - team["goals_against"]
    )

    team["points_per_match"] = _safe_divide(
        team["points"],
        team["played"],
    )

    team["goals_per_match"] = _safe_divide(
        team["goals_for"],
        team["played"],
    )

    team["goals_conceded_per_match"] = _safe_divide(
        team["goals_against"],
        team["played"],
    )

    # --------------------------------------------------------
    # Home metrics
    # --------------------------------------------------------

    team["home_points_per_match"] = _safe_divide(
        team["home_points"],
        team["home_played"],
    )

    team["home_goals_per_match"] = _safe_divide(
        team["home_goals_for"],
        team["home_played"],
    )

    team["home_goals_conceded_per_match"] = _safe_divide(
        team["home_goals_against"],
        team["home_played"],
    )

    # --------------------------------------------------------
    # Away metrics
    # --------------------------------------------------------

    team["away_points_per_match"] = _safe_divide(
        team["away_points"],
        team["away_played"],
    )

    team["away_goals_per_match"] = _safe_divide(
        team["away_goals_for"],
        team["away_played"],
    )

    team["away_goals_conceded_per_match"] = _safe_divide(
        team["away_goals_against"],
        team["away_played"],
    )

    # --------------------------------------------------------
    # Recent-form metrics
    # --------------------------------------------------------

    team["recent_5_points_per_match"] = _safe_divide(
        team["recent_5_points"],
        team["recent_5_played"],
    )

    team["recent_5_goals_per_match"] = _safe_divide(
        team["recent_5_goals_for"],
        team["recent_5_played"],
    )

    team["recent_5_goals_conceded_per_match"] = (
        _safe_divide(
            team["recent_5_goals_against"],
            team["recent_5_played"],
        )
    )


def _assign_league_ranks(
    teams: dict[str, dict[str, Any]],
) -> None:
    """
    Assign league positions using only information available
    at the cutoff.

    Ranking order:

        1. Points
        2. Goal difference
        3. Goals scored

    This is a simplified deterministic ranking for the
    validation layer. It is not intended to reproduce every
    historical Premier League tie-break rule.
    """

    sorted_teams = sorted(
        teams.values(),
        key=lambda team: (
            team["points"],
            team["goal_difference"],
            team["goals_for"],
        ),
        reverse=True,
    )

    for rank, team in enumerate(
        sorted_teams,
        start=1,
    ):

        team["rank"] = rank


# ============================================================
# PUBLIC FUNCTION
# ============================================================

def build_historical_team_state(
    historical_matches: pd.DataFrame,
    season: str,
    cutoff_datetime: Any,
) -> dict[str, dict[str, Any]]:
    """
    Build team state using only matches from one season that
    occurred before a specified cutoff.

    Parameters
    ----------
    historical_matches:
        Canonical historical match DataFrame produced by
        historical_team_data.py.

    season:
        Historical season to analyse, for example "2023/24".

    cutoff_datetime:
        Point in time immediately before the historical
        fixture/prediction we want to evaluate.

    Returns
    -------
    dict
        Dictionary keyed by team name.

    Important
    ---------
    The cutoff is EXCLUSIVE.

    Therefore:

        match_datetime < cutoff_datetime

    is included.

    A match occurring exactly at the cutoff is excluded.

    This prevents the target match itself from leaking into
    the team's historical state.
    """

    # --------------------------------------------------------
    # Validate input type.
    # --------------------------------------------------------

    if not isinstance(
        historical_matches,
        pd.DataFrame,
    ):

        raise TypeError(
            "historical_matches must be a pandas DataFrame."
        )

    # --------------------------------------------------------
    # Validate season.
    # --------------------------------------------------------

    if not isinstance(season, str) or not season.strip():

        raise ValueError(
            "season must be a non-empty string."
        )

    # --------------------------------------------------------
    # Validate required columns.
    # --------------------------------------------------------

    required_columns = [
        "match_id",
        "season",
        "kickoff_datetime",
        "home_team",
        "away_team",
        "home_goals",
        "away_goals",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in historical_matches.columns
    ]

    if missing_columns:

        raise ValueError(
            "Historical match data is missing required "
            f"columns: {missing_columns}"
        )

    # --------------------------------------------------------
    # Convert cutoff into a pandas timestamp.
    # --------------------------------------------------------

    cutoff = pd.Timestamp(
        cutoff_datetime
    )

    # --------------------------------------------------------
    # Work on a copy.
    #
    # We do not modify the source DataFrame.
    # --------------------------------------------------------

    data = historical_matches.copy()

    data["kickoff_datetime"] = pd.to_datetime(
        data["kickoff_datetime"],
        errors="raise",
    )

    # --------------------------------------------------------
    # Filter to the requested season FIRST.
    #
    # This is important because a historical dataset may
    # contain several seasons.
    # --------------------------------------------------------

    data = data[
        data["season"].astype(str) == season
    ].copy()

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # Only matches strictly BEFORE the cutoff are allowed.
    #
    # This is the core anti-look-ahead rule.
    # --------------------------------------------------------

    eligible_matches = data[
        data["kickoff_datetime"] < cutoff
    ].copy()

    # Sort chronologically so that processing is deterministic.

    eligible_matches = eligible_matches.sort_values(
        "kickoff_datetime"
    )

    # --------------------------------------------------------
    # Create team containers.
    # --------------------------------------------------------

    teams: dict[str, dict[str, Any]] = {}

    # Keep individual historical matches for each team.
    #
    # This allows us to calculate recent-5 form after the
    # cumulative statistics have been built.

    team_matches: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    # --------------------------------------------------------
    # Process every eligible historical match.
    # --------------------------------------------------------

    for _, match in eligible_matches.iterrows():

        home_team = str(
            match["home_team"]
        )

        away_team = str(
            match["away_team"]
        )

        home_goals = int(
            match["home_goals"]
        )

        away_goals = int(
            match["away_goals"]
        )

        # ----------------------------------------------------
        # Create team containers if necessary.
        # ----------------------------------------------------

        if home_team not in teams:

            teams[home_team] = (
                _create_empty_team_state(
                    home_team,
                    season,
                    cutoff,
                )
            )

            team_matches[home_team] = []

        if away_team not in teams:

            teams[away_team] = (
                _create_empty_team_state(
                    away_team,
                    season,
                    cutoff,
                )
            )

            team_matches[away_team] = []

        # ----------------------------------------------------
        # Update home team.
        # ----------------------------------------------------

        _update_team_from_match(
            team=teams[home_team],
            goals_for=home_goals,
            goals_against=away_goals,
            venue="home",
        )

        # ----------------------------------------------------
        # Update away team.
        # ----------------------------------------------------

        _update_team_from_match(
            team=teams[away_team],
            goals_for=away_goals,
            goals_against=home_goals,
            venue="away",
        )

        # ----------------------------------------------------
        # Store the match for recent-form calculations.
        # ----------------------------------------------------

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

    # --------------------------------------------------------
    # Calculate derived statistics.
    # --------------------------------------------------------

    for team_name, team in teams.items():

        _calculate_recent_form(
            team=team,
            team_matches=team_matches[team_name],
        )

        _calculate_derived_metrics(
            team
        )

    # --------------------------------------------------------
    # Assign league positions.
    # --------------------------------------------------------

    if teams:

        _assign_league_ranks(
            teams
        )

    # --------------------------------------------------------
    # Return the point-in-time team state.
    # --------------------------------------------------------

    return teams