"""
scenario_engine.py

Reusable future-scenario evaluation foundation for the FPL Strategist.

A scenario describes which players contribute in each future Gameweek and,
optionally, captain multipliers. This keeps scenario mechanics separate from
forecast generation and from strategic decision logic.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, replace
from typing import Any, Mapping


MODEL_VERSION = "scenario_v2"


@dataclass(frozen=True)
class Scenario:
    """A future scenario with optional Gameweek-specific state overrides."""

    scenario_id: str
    scenario_type: str
    description: str
    player_ids: tuple[int, ...]
    excluded_player_ids: tuple[int, ...] = ()
    gameweek_player_ids: tuple[tuple[int, tuple[int, ...]], ...] = ()
    captain_by_gameweek: tuple[tuple[int, int], ...] = ()
    captain_multiplier_by_gameweek: tuple[tuple[int, float], ...] = ()
    bench_boost_gameweeks: tuple[int, ...] = ()
    data_complete: bool = True
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def players_for_gameweek(self, gameweek: int) -> tuple[int, ...]:
        overrides = dict(self.gameweek_player_ids)
        return tuple(overrides.get(int(gameweek), self.player_ids))

    def captain_for_gameweek(self, gameweek: int) -> int | None:
        return dict(self.captain_by_gameweek).get(int(gameweek))

    def captain_multiplier_for_gameweek(self, gameweek: int) -> float:
        return float(dict(self.captain_multiplier_by_gameweek).get(int(gameweek), 1.0))

    def with_gameweek_players(
        self,
        gameweeks: list[int] | tuple[int, ...],
        player_ids: tuple[int, ...],
    ) -> "Scenario":
        overrides = dict(self.gameweek_player_ids)
        for gameweek in gameweeks:
            overrides[int(gameweek)] = tuple(player_ids)
        return replace(self, gameweek_player_ids=tuple(sorted(overrides.items())))

    def with_captain(
        self,
        gameweek: int,
        player_id: int,
        multiplier: float,
    ) -> "Scenario":
        captains = dict(self.captain_by_gameweek)
        multipliers = dict(self.captain_multiplier_by_gameweek)
        captains[int(gameweek)] = int(player_id)
        multipliers[int(gameweek)] = float(multiplier)
        return replace(
            self,
            captain_by_gameweek=tuple(sorted(captains.items())),
            captain_multiplier_by_gameweek=tuple(sorted(multipliers.items())),
        )

    def with_bench_boost(self, gameweek: int) -> "Scenario":
        weeks = set(self.bench_boost_gameweeks)
        weeks.add(int(gameweek))
        return replace(self, bench_boost_gameweeks=tuple(sorted(weeks)))


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


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if number != number or number in (float("inf"), float("-inf")):
            return default
        return number
    except (TypeError, ValueError):
        return default


def _projection_for_gameweek(
    projection: Mapping[str, Any],
    gameweek: int,
) -> tuple[float, bool, tuple[str, ...]]:
    rows = projection.get("fixtures", [])
    matching = [row for row in rows if int(row.get("gameweek", -1)) == int(gameweek)]
    if not matching:
        return 0.0, False, (f"No projection available for GW{gameweek}.",)

    points = sum(_number(row.get("expected_points")) for row in matching)
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

    The evaluator uses supplied fixture-level projections as authoritative. It
    does not create forecasts. DGWs are naturally aggregated because every
    matching fixture row contributes to the Gameweek total.
    """

    requested = tuple(int(gw) for gw in gameweeks)
    if not requested:
        raise ValueError("gameweeks must not be empty")
    if tuple(sorted(requested)) != requested:
        raise ValueError("gameweeks must be in ascending order")

    excluded = set(int(pid) for pid in scenario.excluded_player_ids)
    results: list[ScenarioGameweekResult] = []
    warnings = list(scenario.warnings)
    complete = scenario.data_complete

    for gw in requested:
        active_ids = [int(pid) for pid in scenario.players_for_gameweek(gw) if int(pid) not in excluded]
        gw_points = 0.0
        gw_complete = True
        gw_warnings: list[str] = []

        for player_id in active_ids:
            projection = projections.get(player_id)
            if projection is None:
                gw_complete = False
                gw_warnings.append(f"No projection available for player {player_id} in GW{gw}.")
                continue

            points, player_complete, player_warnings = _projection_for_gameweek(projection, gw)
            gw_points += points
            gw_complete = gw_complete and player_complete
            gw_warnings.extend(player_warnings)

        captain_id = scenario.captain_for_gameweek(gw)
        multiplier = scenario.captain_multiplier_for_gameweek(gw)
        if captain_id is not None:
            if captain_id not in active_ids:
                gw_complete = False
                gw_warnings.append(
                    f"Captain {captain_id} is not an active player in GW{gw}."
                )
            elif multiplier < 1.0:
                gw_complete = False
                gw_warnings.append(f"Captain multiplier for GW{gw} cannot be below 1.")
            else:
                captain_projection = projections.get(captain_id)
                if captain_projection is not None:
                    captain_points, captain_complete, captain_warnings = _projection_for_gameweek(
                        captain_projection, gw
                    )
                    # The raw player projection is already included once. Add
                    # only the extra multiplier above the normal contribution.
                    gw_points += captain_points * (multiplier - 1.0)
                    gw_complete = gw_complete and captain_complete
                    gw_warnings.extend(captain_warnings)

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
