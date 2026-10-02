"""
scenario_engine.py

Reusable future scenario evaluation foundation for the FPL Strategist.

A scenario describes a proposed future state. This module evaluates the
supplied scenario against already-created player projections; it does not
make transfer, captain or chip decisions itself.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


MODEL_VERSION = "scenario_v1"


@dataclass(frozen=True)
class Scenario:
    """A named future scenario with optional player replacements."""

    scenario_id: str
    scenario_type: str
    description: str
    player_ids: tuple[int, ...]
    excluded_player_ids: tuple[int, ...] = ()
    data_complete: bool = True
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ScenarioGameweekResult:
    """Projected result for one Gameweek inside a scenario."""

    gameweek: int
    projected_points: float
    data_complete: bool
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ScenarioResult:
    """Comparable projected result for a future scenario."""

    scenario_id: str
    start_gameweek: int
    end_gameweek: int
    projected_points: float
    gameweek_results: tuple[ScenarioGameweekResult, ...]
    data_complete: bool
    warnings: tuple[str, ...] = ()
    model_version: str = MODEL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _projection_for_gameweek(
    projection: dict[str, Any],
    gameweek: int,
) -> tuple[float, bool, tuple[str, ...]]:
    rows = projection.get("fixtures", [])
    matching = [row for row in rows if int(row.get("gameweek", -1)) == int(gameweek)]
    if not matching:
        return 0.0, False, (f"No projection available for GW{gameweek}.",)

    points = sum(float(row.get("expected_points", 0.0)) for row in matching)
    complete = all(bool(row.get("data_complete", False)) for row in matching)
    warnings: list[str] = []
    for row in matching:
        warnings.extend(str(item) for item in row.get("warnings", ()))
    if not complete:
        warnings.append(f"Projection for GW{gameweek} is incomplete.")
    return points, complete, tuple(dict.fromkeys(warnings))


def evaluate_scenario(
    *,
    scenario: Scenario,
    projections: dict[int, dict[str, Any]],
    gameweeks: list[int] | tuple[int, ...],
) -> ScenarioResult:
    """Evaluate a scenario over the requested future Gameweeks.

    The evaluator treats each player's supplied fixture-level projection as
    authoritative for the calculation. It does not create new forecasts.
    """

    requested = tuple(int(gw) for gw in gameweeks)
    if not requested:
        raise ValueError("gameweeks must not be empty")
    if tuple(sorted(requested)) != requested:
        raise ValueError("gameweeks must be in ascending order")

    included = [pid for pid in scenario.player_ids if pid not in set(scenario.excluded_player_ids)]
    results: list[ScenarioGameweekResult] = []
    warnings = list(scenario.warnings)
    complete = scenario.data_complete

    for gw in requested:
        gw_points = 0.0
        gw_complete = True
        gw_warnings: list[str] = []
        for player_id in included:
            projection = projections.get(int(player_id))
            if projection is None:
                gw_complete = False
                gw_warnings.append(f"No projection available for player {player_id} in GW{gw}.")
                continue
            points, player_complete, player_warnings = _projection_for_gameweek(projection, gw)
            gw_points += points
            gw_complete = gw_complete and player_complete
            gw_warnings.extend(player_warnings)

        gw_warnings = list(dict.fromkeys(gw_warnings))
        results.append(
            ScenarioGameweekResult(
                gameweek=gw,
                projected_points=gw_points,
                data_complete=gw_complete,
                warnings=tuple(gw_warnings),
            )
        )
        complete = complete and gw_complete
        warnings.extend(gw_warnings)

    return ScenarioResult(
        scenario_id=scenario.scenario_id,
        start_gameweek=requested[0],
        end_gameweek=requested[-1],
        projected_points=sum(item.projected_points for item in results),
        gameweek_results=tuple(results),
        data_complete=complete,
        warnings=tuple(dict.fromkeys(warnings)),
    )
