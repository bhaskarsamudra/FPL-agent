"""
team_data.py

Builds team-level performance data from:

1. FPL fixture data
   - Results
   - Goals scored/conceded
   - Points
   - Recent form

2. FPL player data
   - xG
   - xA
   - xGI
   - Actual goals
   - Actual assists
   - Minutes

The final team-strength model will be built later.

This module is deliberately a data/measurement layer.
It does NOT decide how strong a team is.
"""


# =========================================================
# MAIN FUNCTION
# =========================================================

def build_team_performance(fixture_data, player_universe=None):
    """
    Build structured team-level performance data.

    Parameters
    ----------
    fixture_data : list
        Structured fixtures created by fixture_data.py.

    player_universe : list, optional
        Structured player data created by player_data.py.

    Returns
    -------
    dict
        Dictionary keyed by team ID.
    """

    # Make sure fixture_data is a list.
    if not isinstance(fixture_data, list):
        raise ValueError("fixture_data must be a list.")

    # Player data is optional so that the existing
    # results-based functionality can still work.
    if player_universe is None:
        player_universe = []

    if not isinstance(player_universe, list):
        raise ValueError("player_universe must be a list.")

    # -----------------------------------------------------
    # TEAM CONTAINERS
    # -----------------------------------------------------

    teams = {}

    # Stores completed fixtures for each team.
    # This is later used for recent-form calculations.
    team_matches = {}

    # -----------------------------------------------------
    # PROCESS FIXTURES
    # -----------------------------------------------------

    for fixture in fixture_data:

        # We only use completed matches for actual results.
        if not fixture.get("finished", False):
            continue

        home_team_id = fixture.get("home_team_id")
        away_team_id = fixture.get("away_team_id")

        home_score = fixture.get("home_score")
        away_score = fixture.get("away_score")

        # Skip incomplete fixtures.
        if (
            home_team_id is None
            or away_team_id is None
            or home_score is None
            or away_score is None
        ):
            continue

        # -------------------------------------------------
        # CREATE HOME TEAM
        # -------------------------------------------------

        if home_team_id not in teams:

            teams[home_team_id] = {
                "team_id": home_team_id,
                "team_name": fixture.get("home_team"),
                "team_short_name": fixture.get(
                    "home_team_short_name"
                ),

                # Overall results
                "played": 0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "points": 0,

                # Overall goals
                "goals_for": 0,
                "goals_against": 0,

                # Home results
                "home_played": 0,
                "home_wins": 0,
                "home_draws": 0,
                "home_losses": 0,
                "home_goals_for": 0,
                "home_goals_against": 0,

                # Away results
                "away_played": 0,
                "away_wins": 0,
                "away_draws": 0,
                "away_losses": 0,
                "away_goals_for": 0,
                "away_goals_against": 0,

                # Underlying player performance
                "underlying_players_count": 0,
                "underlying_minutes": 0,
                "underlying_goals": 0,
                "underlying_assists": 0,
                "underlying_xg": 0.0,
                "underlying_xa": 0.0,
                "underlying_xgi": 0.0,
                "underlying_xgc": 0.0,
            }

            team_matches[home_team_id] = []

        # -------------------------------------------------
        # CREATE AWAY TEAM
        # -------------------------------------------------

        if away_team_id not in teams:

            teams[away_team_id] = {
                "team_id": away_team_id,
                "team_name": fixture.get("away_team"),
                "team_short_name": fixture.get(
                    "away_team_short_name"
                ),

                # Overall results
                "played": 0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "points": 0,

                # Overall goals
                "goals_for": 0,
                "goals_against": 0,

                # Home results
                "home_played": 0,
                "home_wins": 0,
                "home_draws": 0,
                "home_losses": 0,
                "home_goals_for": 0,
                "home_goals_against": 0,

                # Away results
                "away_played": 0,
                "away_wins": 0,
                "away_draws": 0,
                "away_losses": 0,
                "away_goals_for": 0,
                "away_goals_against": 0,

                # Underlying player performance
                "underlying_players_count": 0,
                "underlying_minutes": 0,
                "underlying_goals": 0,
                "underlying_assists": 0,
                "underlying_xg": 0.0,
                "underlying_xa": 0.0,
                "underlying_xgi": 0.0,
                "underlying_xgc": 0.0,
            }

            team_matches[away_team_id] = []

        # -------------------------------------------------
        # STORE FIXTURE FOR RECENT FORM
        # -------------------------------------------------

        team_matches[home_team_id].append(fixture)
        team_matches[away_team_id].append(fixture)

        # -------------------------------------------------
        # MATCHES PLAYED
        # -------------------------------------------------

        teams[home_team_id]["played"] += 1
        teams[away_team_id]["played"] += 1

        # -------------------------------------------------
        # GOALS
        # -------------------------------------------------

        teams[home_team_id]["goals_for"] += home_score
        teams[home_team_id]["goals_against"] += away_score

        teams[away_team_id]["goals_for"] += away_score
        teams[away_team_id]["goals_against"] += home_score

        # -------------------------------------------------
        # HOME STATISTICS
        # -------------------------------------------------

        teams[home_team_id]["home_played"] += 1
        teams[home_team_id]["home_goals_for"] += home_score
        teams[home_team_id]["home_goals_against"] += away_score

        # -------------------------------------------------
        # AWAY STATISTICS
        # -------------------------------------------------

        teams[away_team_id]["away_played"] += 1
        teams[away_team_id]["away_goals_for"] += away_score
        teams[away_team_id]["away_goals_against"] += home_score

        # -------------------------------------------------
        # RESULT
        # -------------------------------------------------

        if home_score > away_score:

            # Home team wins.
            teams[home_team_id]["wins"] += 1
            teams[home_team_id]["points"] += 3
            teams[home_team_id]["home_wins"] += 1

            # Away team loses.
            teams[away_team_id]["losses"] += 1
            teams[away_team_id]["away_losses"] += 1

        elif home_score < away_score:

            # Away team wins.
            teams[away_team_id]["wins"] += 1
            teams[away_team_id]["points"] += 3
            teams[away_team_id]["away_wins"] += 1

            # Home team loses.
            teams[home_team_id]["losses"] += 1
            teams[home_team_id]["home_losses"] += 1

        else:

            # Draw.
            teams[home_team_id]["draws"] += 1
            teams[home_team_id]["points"] += 1
            teams[home_team_id]["home_draws"] += 1

            teams[away_team_id]["draws"] += 1
            teams[away_team_id]["points"] += 1
            teams[away_team_id]["away_draws"] += 1

    # =====================================================
    # AGGREGATE PLAYER UNDERLYING PERFORMANCE
    # =====================================================

    for player in player_universe:

        # IMPORTANT:
        # player_data.py uses "team_id", not "team".
        team_id = player.get("team_id")

        # Ignore players whose team cannot be matched.
        if team_id not in teams:
            continue

        teams[team_id]["underlying_players_count"] += 1

        # Convert numeric values safely.
        minutes = _safe_float(
            player.get("minutes")
        )

        goals = _safe_float(
            player.get("goals_scored")
        )

        assists = _safe_float(
            player.get("assists")
        )

        xg = _safe_float(
            player.get("expected_goals")
        )

        xa = _safe_float(
            player.get("expected_assists")
        )

        xgi = _safe_float(
            player.get("expected_goal_involvements")
        )

        xgc = _safe_float(
            player.get("expected_goals_conceded")
        )

        # Add player data to the team totals.
        teams[team_id]["underlying_minutes"] += minutes
        teams[team_id]["underlying_goals"] += goals
        teams[team_id]["underlying_assists"] += assists
        teams[team_id]["underlying_xg"] += xg
        teams[team_id]["underlying_xa"] += xa
        teams[team_id]["underlying_xgi"] += xgi
        teams[team_id]["underlying_xgc"] += xgc

    # =====================================================
    # DERIVED TEAM METRICS
    # =====================================================

    for team in teams.values():

        # -------------------------------------------------
        # RESULTS
        # -------------------------------------------------

        team["goal_difference"] = (
            team["goals_for"]
            - team["goals_against"]
        )

        team["points_per_match"] = _safe_divide(
            team["points"],
            team["played"]
        )

        team["goals_per_match"] = _safe_divide(
            team["goals_for"],
            team["played"]
        )

        team["goals_conceded_per_match"] = _safe_divide(
            team["goals_against"],
            team["played"]
        )

        # -------------------------------------------------
        # HOME
        # -------------------------------------------------

        team["home_goals_per_match"] = _safe_divide(
            team["home_goals_for"],
            team["home_played"]
        )

        team["home_goals_conceded_per_match"] = _safe_divide(
            team["home_goals_against"],
            team["home_played"]
        )

        # -------------------------------------------------
        # AWAY
        # -------------------------------------------------

        team["away_goals_per_match"] = _safe_divide(
            team["away_goals_for"],
            team["away_played"]
        )

        team["away_goals_conceded_per_match"] = _safe_divide(
            team["away_goals_against"],
            team["away_played"]
        )

        # -------------------------------------------------
        # UNDERLYING ATTACKING METRICS
        # -------------------------------------------------

        team["underlying_xg_per_90"] = _safe_divide(
            team["underlying_xg"] * 90,
            team["underlying_minutes"]
        )

        team["underlying_xa_per_90"] = _safe_divide(
            team["underlying_xa"] * 90,
            team["underlying_minutes"]
        )

        team["underlying_xgi_per_90"] = _safe_divide(
            team["underlying_xgi"] * 90,
            team["underlying_minutes"]
        )

        # -------------------------------------------------
        # ACTUAL ATTACKING OUTPUT
        # -------------------------------------------------

        team["underlying_goals_per_90"] = _safe_divide(
            team["underlying_goals"] * 90,
            team["underlying_minutes"]
        )

        team["underlying_assists_per_90"] = _safe_divide(
            team["underlying_assists"] * 90,
            team["underlying_minutes"]
        )

    # =====================================================
    # RECENT FORM
    # =====================================================

    for team_id, matches in team_matches.items():

        # Newest fixture first.
        matches_sorted = sorted(
            matches,
            key=lambda fixture: fixture.get(
                "kickoff_time"
            ) or "",
            reverse=True
        )

        # Most recent five completed matches.
        recent_matches = matches_sorted[:5]

        recent_played = 0
        recent_wins = 0
        recent_draws = 0
        recent_losses = 0
        recent_points = 0
        recent_goals_for = 0
        recent_goals_against = 0

        for fixture in recent_matches:

            home_team_id = fixture.get(
                "home_team_id"
            )

            away_team_id = fixture.get(
                "away_team_id"
            )

            home_score = fixture.get(
                "home_score"
            )

            away_score = fixture.get(
                "away_score"
            )

            recent_played += 1

            # Determine whether this team was home or away.
            if team_id == home_team_id:

                goals_for = home_score
                goals_against = away_score

            else:

                goals_for = away_score
                goals_against = home_score

            recent_goals_for += goals_for
            recent_goals_against += goals_against

            # Determine result.
            if goals_for > goals_against:

                recent_wins += 1
                recent_points += 3

            elif goals_for == goals_against:

                recent_draws += 1
                recent_points += 1

            else:

                recent_losses += 1

        team = teams[team_id]

        team["recent_5_played"] = recent_played
        team["recent_5_wins"] = recent_wins
        team["recent_5_draws"] = recent_draws
        team["recent_5_losses"] = recent_losses
        team["recent_5_points"] = recent_points

        team["recent_5_goals_for"] = recent_goals_for
        team["recent_5_goals_against"] = recent_goals_against

        team["recent_5_goal_difference"] = (
            recent_goals_for
            - recent_goals_against
        )

        team["recent_5_points_per_match"] = _safe_divide(
            recent_points,
            recent_played
        )

        team["recent_5_goals_per_match"] = _safe_divide(
            recent_goals_for,
            recent_played
        )

        team["recent_5_goals_conceded_per_match"] = _safe_divide(
            recent_goals_against,
            recent_played
        )

    # =====================================================
    # SORT LIKE A LEAGUE TABLE
    # =====================================================

    sorted_teams = sorted(
        teams.values(),
        key=lambda team: (
            team["points"],
            team["goal_difference"],
            team["goals_for"],
        ),
        reverse=True
    )

    # Assign league rank.
    for rank, team in enumerate(
        sorted_teams,
        start=1
    ):
        team["rank"] = rank

    # Return dictionary keyed by team ID.
    return {
        team["team_id"]: team
        for team in sorted_teams
    }


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def _safe_float(value):
    """
    Convert a value into a float safely.

    FPL often returns numerical values as strings,
    so this helper handles both strings and numbers.
    """

    try:
        return float(value or 0)

    except (TypeError, ValueError):

        return 0.0


def _safe_divide(numerator, denominator):
    """
    Divide two numbers safely.

    Returns 0 when the denominator is zero.
    """

    if denominator == 0:
        return 0.0

    return numerator / denominator