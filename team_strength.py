"""
team_strength.py

This module converts the factual team-performance data from
team_data.py into transparent team-strength indicators.

Important:
- This is NOT the final team-strength model.
- We deliberately do NOT create one opaque "overall strength"
  score yet.
- Every component remains visible so we can inspect and validate it.
"""

from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    """
    Safely convert a value to float.

    FPL data can sometimes contain strings, None, or missing values.
    Returning a default value keeps calculations robust.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_ratio(
    numerator: float,
    denominator: float,
    default: float = 1.0,
) -> float:
    """
    Safely calculate numerator / denominator.

    A ratio of 1.0 means the team is at league-average level.
    """
    if denominator <= 0:
        return default

    return numerator / denominator


def _league_average(
    team_performance: dict[int, dict[str, Any]],
    field: str,
) -> float:
    """
    Calculate the league average for a numeric team metric.

    team_performance is a dictionary keyed by team ID.
    """

    values = []

    for team in team_performance.values():

        # Only include teams that have actually played matches.
        if _safe_float(team.get("played")) <= 0:
            continue

        values.append(_safe_float(team.get(field)))

    if not values:
        return 0.0

    return sum(values) / len(values)


def build_team_strength(
    team_performance: dict[int, dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    """
    Build transparent team-strength indicators.

    Input:
        Dictionary returned by build_team_performance().

    Output:
        Dictionary keyed by team ID.

    The function deliberately keeps the components separate.

    ATTACK
    - observed goals
    - underlying xG
    - underlying xGI
    - recent goals
    - home/away goals

    DEFENCE
    - observed goals conceded
    - recent goals conceded
    - home/away goals conceded

    We also record sample size because five gameweeks is a very
    small sample for judging true team strength.
    """

    # -------------------------------------------------------------
    # Validate the input structure.
    # -------------------------------------------------------------

    if not isinstance(team_performance, dict):
        raise TypeError(
            "team_performance must be a dictionary keyed by team ID."
        )

    # -------------------------------------------------------------
    # Calculate league-wide reference values.
    #
    # These allow us to compare each team against the current
    # league average.
    # -------------------------------------------------------------

    league_avg = {
        "goals_per_match": _league_average(
            team_performance,
            "goals_per_match",
        ),
        "underlying_xg_per_90": _league_average(
            team_performance,
            "underlying_xg_per_90",
        ),
        "underlying_xgi_per_90": _league_average(
            team_performance,
            "underlying_xgi_per_90",
        ),
        "recent_5_goals_per_match": _league_average(
            team_performance,
            "recent_5_goals_per_match",
        ),
        "goals_conceded_per_match": _league_average(
            team_performance,
            "goals_conceded_per_match",
        ),
        "recent_5_goals_conceded_per_match": _league_average(
            team_performance,
            "recent_5_goals_conceded_per_match",
        ),
        "home_goals_per_match": _league_average(
            team_performance,
            "home_goals_per_match",
        ),
        "away_goals_per_match": _league_average(
            team_performance,
            "away_goals_per_match",
        ),
        "home_goals_conceded_per_match": _league_average(
            team_performance,
            "home_goals_conceded_per_match",
        ),
        "away_goals_conceded_per_match": _league_average(
            team_performance,
            "away_goals_conceded_per_match",
        ),
    }

    # This dictionary will contain one strength record per team.
    strength_data = {}

    # -------------------------------------------------------------
    # Process each team.
    # -------------------------------------------------------------

    for team_id, team in team_performance.items():

        played = _safe_float(team.get("played"))

        # =========================================================
        # ATTACK
        # =========================================================

        # Actual goals scored per match.
        goals_per_match = _safe_float(
            team.get("goals_per_match")
        )

        observed_attack_ratio = _safe_ratio(
            goals_per_match,
            league_avg["goals_per_match"],
        )

        # Underlying xG per 90.
        xg_per_90 = _safe_float(
            team.get("underlying_xg_per_90")
        )

        underlying_attack_xg_ratio = _safe_ratio(
            xg_per_90,
            league_avg["underlying_xg_per_90"],
        )

        # Underlying xGI per 90.
        xgi_per_90 = _safe_float(
            team.get("underlying_xgi_per_90")
        )

        underlying_attack_xgi_ratio = _safe_ratio(
            xgi_per_90,
            league_avg["underlying_xgi_per_90"],
        )

        # Recent scoring rate.
        recent_goals_per_match = _safe_float(
            team.get("recent_5_goals_per_match")
        )

        recent_attack_ratio = _safe_ratio(
            recent_goals_per_match,
            league_avg["recent_5_goals_per_match"],
        )

        # =========================================================
        # HOME / AWAY ATTACK
        # =========================================================

        home_goals_per_match = _safe_float(
            team.get("home_goals_per_match")
        )

        away_goals_per_match = _safe_float(
            team.get("away_goals_per_match")
        )

        home_attack_ratio = _safe_ratio(
            home_goals_per_match,
            league_avg["home_goals_per_match"],
        )

        away_attack_ratio = _safe_ratio(
            away_goals_per_match,
            league_avg["away_goals_per_match"],
        )

        # =========================================================
        # DEFENCE
        # =========================================================
        #
        # For attack:
        #
        #     higher = better
        #
        # For defence:
        #
        #     lower goals conceded = better
        #
        # Therefore defensive ratios are reversed:
        #
        #     league average / team's value
        #
        # Example:
        #
        # League average conceded = 1.50
        # Team conceded = 1.00
        #
        # Defensive ratio = 1.50 / 1.00 = 1.50
        #
        # Therefore:
        #
        #     > 1.00 = better than average
        #     = 1.00 = league average
        #     < 1.00 = worse than average
        # =========================================================

        goals_conceded_per_match = _safe_float(
            team.get("goals_conceded_per_match")
        )

        observed_defence_ratio = _safe_ratio(
            league_avg["goals_conceded_per_match"],
            goals_conceded_per_match,
        )

        # Recent defensive performance.
        recent_goals_conceded = _safe_float(
            team.get("recent_5_goals_conceded_per_match")
        )

        recent_defence_ratio = _safe_ratio(
            league_avg["recent_5_goals_conceded_per_match"],
            recent_goals_conceded,
        )

        # =========================================================
        # HOME / AWAY DEFENCE
        # =========================================================

        home_goals_conceded = _safe_float(
            team.get("home_goals_conceded_per_match")
        )

        away_goals_conceded = _safe_float(
            team.get("away_goals_conceded_per_match")
        )

        home_defence_ratio = _safe_ratio(
            league_avg["home_goals_conceded_per_match"],
            home_goals_conceded,
        )

        away_defence_ratio = _safe_ratio(
            league_avg["away_goals_conceded_per_match"],
            away_goals_conceded,
        )

        # =========================================================
        # SAMPLE SIZE
        # =========================================================
        #
        # We are deliberately NOT applying a statistical shrinkage
        # formula yet.
        #
        # Five matches is a very small sample. We first want to
        # inspect the signals before deciding how reliability should
        # affect the final model.
        # =========================================================

        sample_size = int(played)

        strength_data[team_id] = {

            # -----------------------------------------------------
            # Team identity
            # -----------------------------------------------------

            "team_id": team.get("team_id"),
            "team_name": team.get("team_name"),
            "team_short_name": team.get("team_short_name"),

            # -----------------------------------------------------
            # Sample size
            # -----------------------------------------------------

            "played": sample_size,

            # -----------------------------------------------------
            # Attack - raw measurements
            # -----------------------------------------------------

            "goals_per_match": goals_per_match,
            "underlying_xg_per_90": xg_per_90,
            "underlying_xgi_per_90": xgi_per_90,
            "recent_5_goals_per_match": recent_goals_per_match,
            "home_goals_per_match": home_goals_per_match,
            "away_goals_per_match": away_goals_per_match,

            # -----------------------------------------------------
            # Attack - normalized measurements
            # -----------------------------------------------------

            "observed_attack_ratio": observed_attack_ratio,
            "underlying_attack_xg_ratio": (
                underlying_attack_xg_ratio
            ),
            "underlying_attack_xgi_ratio": (
                underlying_attack_xgi_ratio
            ),
            "recent_attack_ratio": recent_attack_ratio,
            "home_attack_ratio": home_attack_ratio,
            "away_attack_ratio": away_attack_ratio,

            # -----------------------------------------------------
            # Defence - raw measurements
            # -----------------------------------------------------

            "goals_conceded_per_match": (
                goals_conceded_per_match
            ),
            "recent_5_goals_conceded_per_match": (
                recent_goals_conceded
            ),
            "home_goals_conceded_per_match": (
                home_goals_conceded
            ),
            "away_goals_conceded_per_match": (
                away_goals_conceded
            ),

            # -----------------------------------------------------
            # Defence - normalized measurements
            # -----------------------------------------------------

            "observed_defence_ratio": (
                observed_defence_ratio
            ),
            "recent_defence_ratio": (
                recent_defence_ratio
            ),
            "home_defence_ratio": (
                home_defence_ratio
            ),
            "away_defence_ratio": (
                away_defence_ratio
            ),
        }

    return strength_data