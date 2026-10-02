"""
future_horizon.py

Common future-horizon representation for the FPL Strategist.

This module does not forecast player performance. It organizes already
available fixture/projection information into a point-in-time future horizon
that other strategy engines can consume.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


MODEL_VERSION = "future_horizon_v1"


@dataclass(frozen=True)
class GameweekOpportunity:
    """Fixture characteristics for one future Gameweek."""

    gameweek: int
    total_fixtures: int
    teams_with_fixtures: int
    blank_team_count: int
    double_team_count: int
    fixture_ids: tuple[int | str, ...]
    data_complete: bool
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FutureHorizon:
    """Point-in-time representation of future Gameweeks."""

    decision_gameweek: int
    start_gameweek: int
    end_gameweek: int
    gameweeks: tuple[int, ...]
    opportunities: tuple[GameweekOpportunity, ...]
    data_complete: bool
    warnings: tuple[str, ...] = ()
    model_version: str = MODEL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fixture_team_ids(fixture: dict[str, Any]) -> tuple[int, int]:
    home = int(fixture.get("home_team_id", fixture.get("team_h", -1)))
    away = int(fixture.get("away_team_id", fixture.get("team_a", -1)))
    return home, away


def build_future_horizon(
    *,
    decision_gameweek: int,
    gameweeks: list[int] | tuple[int, ...],
    fixtures: list[dict[str, Any]],
    known_team_ids: list[int] | tuple[int, ...] | None = None,
) -> FutureHorizon:
    """Build a future fixture horizon from information known at decision time.

    The caller supplies only information available at the decision point. This
    function deliberately does not fetch data or infer missing future fixtures.
    """

    decision_gameweek = int(decision_gameweek)
    requested = tuple(dict.fromkeys(int(gw) for gw in gameweeks))
    if decision_gameweek < 0:
        raise ValueError("decision_gameweek must be non-negative")
    if not requested:
        raise ValueError("gameweeks must not be empty")
    if any(gw <= decision_gameweek for gw in requested):
        raise ValueError("future gameweeks must be after decision_gameweek")
    if tuple(sorted(requested)) != requested:
        raise ValueError("gameweeks must be in ascending order")

    fixture_by_gw: dict[int, list[dict[str, Any]]] = {gw: [] for gw in requested}
    warnings: list[str] = []
    for fixture in fixtures:
        try:
            gw = int(fixture["gameweek"])
        except (KeyError, TypeError, ValueError):
            warnings.append("Fixture without a valid Gameweek was ignored.")
            continue
        if gw in fixture_by_gw:
            fixture_by_gw[gw].append(fixture)

    if known_team_ids is None:
        inferred_teams: set[int] = set()
        for rows in fixture_by_gw.values():
            for fixture in rows:
                home, away = _fixture_team_ids(fixture)
                if home >= 0:
                    inferred_teams.add(home)
                if away >= 0:
                    inferred_teams.add(away)
        known_teams = inferred_teams
    else:
        known_teams = {int(team_id) for team_id in known_team_ids}

    opportunities: list[GameweekOpportunity] = []
    for gw in requested:
        rows = fixture_by_gw[gw]
        team_counts: dict[int, int] = {}
        fixture_ids: list[int | str] = []
        gw_warnings: list[str] = []

        for fixture in rows:
            home, away = _fixture_team_ids(fixture)
            if home < 0 or away < 0:
                gw_warnings.append(f"GW{gw} contains a fixture with missing team IDs.")
                continue
            team_counts[home] = team_counts.get(home, 0) + 1
            team_counts[away] = team_counts.get(away, 0) + 1
            fixture_id = fixture.get("fixture_id", fixture.get("id"))
            if fixture_id is not None:
                fixture_ids.append(fixture_id)

        teams_with_fixtures = len(team_counts)
        double_team_count = sum(1 for count in team_counts.values() if count >= 2)
        blank_team_count = max(0, len(known_teams) - teams_with_fixtures) if known_teams else 0
        complete = bool(rows) and not gw_warnings

        if not rows:
            gw_warnings.append(f"No fixtures supplied for GW{gw}.")
            complete = False
        if not known_teams:
            gw_warnings.append("Known team set was not supplied or inferred.")
            complete = False

        opportunities.append(
            GameweekOpportunity(
                gameweek=gw,
                total_fixtures=len(rows),
                teams_with_fixtures=teams_with_fixtures,
                blank_team_count=blank_team_count,
                double_team_count=double_team_count,
                fixture_ids=tuple(fixture_ids),
                data_complete=complete,
                warnings=tuple(dict.fromkeys(gw_warnings)),
            )
        )

    all_complete = all(item.data_complete for item in opportunities)
    all_warnings = list(warnings)
    for item in opportunities:
        all_warnings.extend(item.warnings)

    return FutureHorizon(
        decision_gameweek=decision_gameweek,
        start_gameweek=requested[0],
        end_gameweek=requested[-1],
        gameweeks=requested,
        opportunities=tuple(opportunities),
        data_complete=all_complete,
        warnings=tuple(dict.fromkeys(all_warnings)),
    )
