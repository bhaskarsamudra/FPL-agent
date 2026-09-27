"""
Historical Prior Layer
======================

Purpose
-------
Build a transparent, season-scoped historical Premier League prior for
team strength. The prior is deliberately separate from the current-season
point-in-time team state.

V1 methodology
---------------
* Use up to the three most recent completed Premier League seasons before
  the target season.
* Apply a transparent recency baseline of 60% / 30% / 10% from newest to
  oldest season used.
* Keep observed attack/defence signals separate from underlying metrics.
* Retain sample-size and availability metadata.
* Do not fabricate a Premier League prior for promoted teams with no usable
  Premier League history.
* Do not introduce a separately tuned historical shrinkage parameter in V1.
* Never use matches from the target season or later to construct the prior.

This module is diagnostic-first. It does not modify the current-season
state layer and does not feed the expected-goals model directly.
"""

from __future__ import annotations

# -------------------------------------------------------------------
# IMPORTS
# -------------------------------------------------------------------

from dataclasses import dataclass, asdict
from typing import Any, Iterable, Optional

import pandas as pd


# -------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------

# Maximum number of completed seasons that can contribute to the prior.
MAX_HISTORICAL_SEASONS = 3

# Transparent V1 recency baseline, newest season first.
RECENCY_WEIGHTS = (0.60, 0.30, 0.10)

# Canonical season order used by the project.
SEASON_ORDER = (
    "2020/21",
    "2021/22",
    "2022/23",
    "2023/24",
    "2024/25",
    "2025/26",
    "2026/27",
)

REQUIRED_COLUMNS = {
    "season",
    "home_team",
    "away_team",
    "home_goals",
    "away_goals",
}


# -------------------------------------------------------------------
# DATA CONTRACT
# -------------------------------------------------------------------

@dataclass(frozen=True)
class HistoricalPrior:
    """Historical team-strength prior for one team before a target season."""

    team: str
    target_season: str
    historical_prior_available: bool

    # Historical seasons actually used in the prior.
    seasons_used: tuple[str, ...]
    season_count: int

    # Total completed historical matches represented by the prior.
    sample_size: int

    # Weighted observed strength indicators.
    attack_overall: Optional[float]
    attack_home: Optional[float]
    attack_away: Optional[float]

    # Defensive weakness is expressed as a multiplier:
    # 1.0 = league average, >1.0 = more goals conceded than average.
    defence_overall: Optional[float]
    defence_home: Optional[float]
    defence_away: Optional[float]

    # Underlying metrics are intentionally separate. They remain None in
    # this match-result-only implementation unless a future validated source
    # is explicitly supplied to this layer.
    underlying_xg_overall: Optional[float]
    underlying_xg_home: Optional[float]
    underlying_xg_away: Optional[float]
    underlying_xga_overall: Optional[float]
    underlying_xga_home: Optional[float]
    underlying_xga_away: Optional[float]

    # Diagnostic metadata makes the prior auditable.
    recency_weights: tuple[float, ...]
    source_seasons_available: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return the prior as a normal dictionary for downstream code."""

        return asdict(self)


# -------------------------------------------------------------------
# VALIDATION HELPERS
# -------------------------------------------------------------------


def _validate_target_season(target_season: str) -> None:
    """Reject unknown target seasons rather than silently guessing order."""

    if target_season not in SEASON_ORDER:
        raise ValueError(
            f"Unknown target season '{target_season}'. "
            f"Expected one of: {SEASON_ORDER}."
        )


def _validate_matches(historical_matches: pd.DataFrame) -> None:
    """Validate the minimum canonical match schema required by this layer."""

    if not isinstance(historical_matches, pd.DataFrame):
        raise ValueError("historical_matches must be a pandas DataFrame.")

    missing = sorted(REQUIRED_COLUMNS - set(historical_matches.columns))

    if missing:
        raise ValueError(
            "historical_matches is missing required columns: "
            f"{missing}"
        )

    if historical_matches.empty:
        raise ValueError("historical_matches cannot be empty.")


def _season_index(season: str) -> int:
    """Return the canonical index for a known season."""

    _validate_target_season(season)
    return SEASON_ORDER.index(season)


# -------------------------------------------------------------------
# SEASON SELECTION
# -------------------------------------------------------------------


def get_prior_seasons(
    target_season: str,
    available_seasons: Iterable[str],
) -> list[str]:
    """
    Select up to three completed seasons immediately before target_season.

    Seasons are returned newest-first because RECENCY_WEIGHTS are defined
    in newest-first order.
    """

    target_index = _season_index(target_season)

    available = set(available_seasons)

    # Only seasons strictly before the target are eligible. This is the
    # fundamental leakage boundary for the Historical Prior Layer.
    eligible = [
        season
        for season in SEASON_ORDER[:target_index]
        if season in available
    ]

    # The canonical list is oldest -> newest, so reverse it to make the
    # newest completed season receive the largest weight.
    eligible = list(reversed(eligible))

    return eligible[:MAX_HISTORICAL_SEASONS]


# -------------------------------------------------------------------
# SEASON-LEVEL METRICS
# -------------------------------------------------------------------


def _calculate_season_metrics(
    season_matches: pd.DataFrame,
    team: str,
) -> Optional[dict[str, float | int]]:
    """Calculate transparent observed metrics for one team in one season."""

    home = season_matches[season_matches["home_team"] == team]
    away = season_matches[season_matches["away_team"] == team]

    home_played = len(home)
    away_played = len(away)
    played = home_played + away_played

    if played == 0:
        return None

    home_goals_for = float(home["home_goals"].sum())
    home_goals_against = float(home["away_goals"].sum())
    away_goals_for = float(away["away_goals"].sum())
    away_goals_against = float(away["home_goals"].sum())

    goals_for = home_goals_for + away_goals_for
    goals_against = home_goals_against + away_goals_against

    return {
        "played": played,
        "home_played": home_played,
        "away_played": away_played,
        "goals_for_per_match": goals_for / played,
        "goals_against_per_match": goals_against / played,
        "home_goals_for_per_match": (
            home_goals_for / home_played if home_played else 0.0
        ),
        "home_goals_against_per_match": (
            home_goals_against / home_played if home_played else 0.0
        ),
        "away_goals_for_per_match": (
            away_goals_for / away_played if away_played else 0.0
        ),
        "away_goals_against_per_match": (
            away_goals_against / away_played if away_played else 0.0
        ),
    }


def _calculate_league_averages(
    season_matches: pd.DataFrame,
) -> dict[str, float]:
    """Calculate season-specific league scoring baselines."""

    match_count = len(season_matches)

    if match_count == 0:
        raise ValueError("Cannot calculate league averages from zero matches.")

    total_home_goals = float(season_matches["home_goals"].sum())
    total_away_goals = float(season_matches["away_goals"].sum())

    return {
        "home_goals_per_match": total_home_goals / match_count,
        "away_goals_per_match": total_away_goals / match_count,
        "overall_goals_per_team_match": (
            (total_home_goals + total_away_goals) / (2 * match_count)
        ),
    }


def _normalise_season_strength(
    metrics: dict[str, float | int],
    league: dict[str, float],
) -> dict[str, float | int]:
    """Convert raw goals-per-match into league-relative strength indicators."""

    overall_baseline = league["overall_goals_per_team_match"]
    home_baseline = league["home_goals_per_match"]
    away_baseline = league["away_goals_per_match"]

    return {
        "played": int(metrics["played"]),
        "attack_overall": metrics["goals_for_per_match"] / overall_baseline,
        "attack_home": metrics["home_goals_for_per_match"] / home_baseline,
        "attack_away": metrics["away_goals_for_per_match"] / away_baseline,
        "defence_overall": metrics["goals_against_per_match"] / overall_baseline,
        # Home goals conceded are compared with the away-team scoring
        # baseline, because this is the scoring opportunity allowed to an
        # opponent playing away.
        "defence_home": (
            metrics["home_goals_against_per_match"] / away_baseline
        ),
        # Away goals conceded are compared with the home-team scoring
        # baseline for the same reason.
        "defence_away": (
            metrics["away_goals_against_per_match"] / home_baseline
        ),
    }


# -------------------------------------------------------------------
# WEIGHTED PRIOR
# -------------------------------------------------------------------


def _weighted_average(
    values: list[float],
    weights: list[float],
) -> float:
    """Calculate a weighted average for already-aligned values/weights."""

    if not values or not weights or len(values) != len(weights):
        raise ValueError("values and weights must be non-empty and aligned.")

    weight_total = sum(weights)

    if weight_total <= 0:
        raise ValueError("Weight total must be positive.")

    return sum(value * weight for value, weight in zip(values, weights)) / weight_total


def _build_available_team_set(
    historical_matches: pd.DataFrame,
    seasons: Iterable[str],
) -> set[str]:
    """Return teams with at least one match in the selected seasons."""

    subset = historical_matches[historical_matches["season"].isin(seasons)]

    return set(subset["home_team"].dropna()) | set(
        subset["away_team"].dropna()
    )


# -------------------------------------------------------------------
# PUBLIC API
# -------------------------------------------------------------------


def build_historical_prior(
    historical_matches: pd.DataFrame,
    target_season: str,
    team: str,
) -> HistoricalPrior:
    """
    Build the V1 historical prior for one team before a target season.

    Parameters
    ----------
    historical_matches:
        Canonical historical team match DataFrame.

    target_season:
        Season being predicted, for example ``"2026/27"``.

    team:
        Team name as represented in the canonical historical dataset.

    Returns
    -------
    HistoricalPrior
        A transparent, auditable prior. If the team has no usable prior
        Premier League history, historical_prior_available is False and
        all strength metrics are None.
    """

    _validate_matches(historical_matches)
    _validate_target_season(target_season)

    if not isinstance(team, str) or not team.strip():
        raise ValueError("team must be a non-empty string.")

    team = team.strip()

    available_seasons = set(historical_matches["season"].dropna().astype(str))
    source_seasons_available = tuple(
        season
        for season in SEASON_ORDER
        if season in available_seasons and _season_index(season) < _season_index(target_season)
    )

    prior_seasons = get_prior_seasons(
        target_season=target_season,
        available_seasons=source_seasons_available,
    )

    if not prior_seasons:
        return HistoricalPrior(
            team=team,
            target_season=target_season,
            historical_prior_available=False,
            seasons_used=(),
            season_count=0,
            sample_size=0,
            attack_overall=None,
            attack_home=None,
            attack_away=None,
            defence_overall=None,
            defence_home=None,
            defence_away=None,
            underlying_xg_overall=None,
            underlying_xg_home=None,
            underlying_xg_away=None,
            underlying_xga_overall=None,
            underlying_xga_home=None,
            underlying_xga_away=None,
            recency_weights=(),
            source_seasons_available=source_seasons_available,
        )

    season_strengths: list[dict[str, float | int]] = []
    seasons_used: list[str] = []

    for season in prior_seasons:
        season_matches = historical_matches[
            historical_matches["season"] == season
        ].copy()

        metrics = _calculate_season_metrics(season_matches, team)

        # A team can be absent from a season. Do not fabricate a zero or
        # league-average value for that missing season.
        if metrics is None:
            continue

        league = _calculate_league_averages(season_matches)
        strength = _normalise_season_strength(metrics, league)

        season_strengths.append(strength)
        seasons_used.append(season)

    if not season_strengths:
        return HistoricalPrior(
            team=team,
            target_season=target_season,
            historical_prior_available=False,
            seasons_used=(),
            season_count=0,
            sample_size=0,
            attack_overall=None,
            attack_home=None,
            attack_away=None,
            defence_overall=None,
            defence_home=None,
            defence_away=None,
            underlying_xg_overall=None,
            underlying_xg_home=None,
            underlying_xg_away=None,
            underlying_xga_overall=None,
            underlying_xga_home=None,
            underlying_xga_away=None,
            recency_weights=(),
            source_seasons_available=source_seasons_available,
        )

    # Use the predefined newest-first weights, truncated to the number of
    # usable seasons. Renormalising prevents a missing historical season from
    # implicitly reducing the total weight assigned to available evidence.
    weights = list(RECENCY_WEIGHTS[: len(season_strengths)])
    weight_total = sum(weights)
    weights = [weight / weight_total for weight in weights]

    sample_size = int(sum(int(item["played"]) for item in season_strengths))

    return HistoricalPrior(
        team=team,
        target_season=target_season,
        historical_prior_available=True,
        seasons_used=tuple(seasons_used),
        season_count=len(seasons_used),
        sample_size=sample_size,
        attack_overall=_weighted_average(
            [float(item["attack_overall"]) for item in season_strengths], weights
        ),
        attack_home=_weighted_average(
            [float(item["attack_home"]) for item in season_strengths], weights
        ),
        attack_away=_weighted_average(
            [float(item["attack_away"]) for item in season_strengths], weights
        ),
        defence_overall=_weighted_average(
            [float(item["defence_overall"]) for item in season_strengths], weights
        ),
        defence_home=_weighted_average(
            [float(item["defence_home"]) for item in season_strengths], weights
        ),
        defence_away=_weighted_average(
            [float(item["defence_away"]) for item in season_strengths], weights
        ),
        underlying_xg_overall=None,
        underlying_xg_home=None,
        underlying_xg_away=None,
        underlying_xga_overall=None,
        underlying_xga_home=None,
        underlying_xga_away=None,
        recency_weights=tuple(weights),
        source_seasons_available=source_seasons_available,
    )


def build_historical_priors(
    historical_matches: pd.DataFrame,
    target_season: str,
    teams: Optional[Iterable[str]] = None,
) -> dict[str, HistoricalPrior]:
    """
    Build historical priors for multiple teams.

    If ``teams`` is omitted, the function uses all teams represented in the
    eligible historical seasons. Passing the current-season team universe is
    recommended for the eventual production walk-forward integration.
    """

    _validate_matches(historical_matches)
    _validate_target_season(target_season)

    available_seasons = set(historical_matches["season"].dropna().astype(str))
    prior_seasons = get_prior_seasons(target_season, available_seasons)

    if teams is None:
        team_set = _build_available_team_set(
            historical_matches,
            prior_seasons,
        )
    else:
        team_set = {
            team.strip()
            for team in teams
            if isinstance(team, str) and team.strip()
        }

    return {
        team: build_historical_prior(
            historical_matches=historical_matches,
            target_season=target_season,
            team=team,
        )
        for team in sorted(team_set)
    }


# -------------------------------------------------------------------
# SIMPLE SERIALISATION HELPER
# -------------------------------------------------------------------


def priors_to_dataframe(
    priors: dict[str, HistoricalPrior],
) -> pd.DataFrame:
    """Convert a prior dictionary into a tabular diagnostic DataFrame."""

    if not isinstance(priors, dict):
        raise ValueError("priors must be a dictionary of HistoricalPrior objects.")

    rows = []

    for prior in priors.values():
        row = prior.to_dict()
        row["seasons_used"] = ",".join(prior.seasons_used)
        row["recency_weights"] = ",".join(
            f"{weight:.4f}" for weight in prior.recency_weights
        )
        row["source_seasons_available"] = ",".join(
            prior.source_seasons_available
        )
        rows.append(row)

    return pd.DataFrame(rows)
