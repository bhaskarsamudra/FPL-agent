"""
expected_points.py

Transparent expected-FPL-points engine.

Batch 11 upgrades the baseline into an explicit V2 scoring model while keeping
all probability inputs auditable. The model never silently invents missing
football probabilities. Optional components such as goalkeeper saves and
defensive-contribution points are used only when their validated inputs are
supplied.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import exp, factorial
from typing import Any


MODEL_VERSION = "xp_v2"


@dataclass(frozen=True)
class ExpectedPoints:
    """Auditable expected-points result for one player over one fixture."""

    player_id: int
    gameweek: int
    expected_points: float

    expected_minutes: float
    expected_goals: float
    expected_assists: float
    expected_clean_sheet: float
    expected_bonus: float
    expected_saves: float
    expected_goals_conceded_points: float
    expected_defensive_contribution_points: float
    expected_appearance_points: float

    data_complete: bool
    warnings: tuple[str, ...]
    model_version: str = MODEL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if number == number and abs(number) != float("inf") else default
    except (TypeError, ValueError):
        return default


def _probability(value: Any, default: float = 0.0) -> float:
    return min(1.0, max(0.0, _float(value, default)))


def _scoring_rules(
    bootstrap_data: dict[str, Any],
    position_id: int,
) -> dict[str, float]:
    """Read official scoring rules from bootstrap when available."""
    positions = bootstrap_data.get("element_types", [])
    position = next(
        (row for row in positions if int(row.get("id", -1)) == int(position_id)),
        None,
    )
    scoring = (position or {}).get("scoring", {})

    def value(name: str, fallback: float) -> float:
        raw = scoring.get(name, fallback)
        if isinstance(raw, dict):
            raw = raw.get(str(position_id), raw.get(position_id, fallback))
        return _float(raw, fallback)

    goal_fallback = {1: 6, 2: 6, 3: 5, 4: 4}.get(position_id, 4)
    clean_sheet_fallback = {1: 4, 2: 4, 3: 1, 4: 0}.get(position_id, 0)

    return {
        "goal": value("goals_scored", goal_fallback),
        "assist": value("assists", 3.0),
        "clean_sheet": value("clean_sheets", clean_sheet_fallback),
        "bonus": value("bonus", 1.0),
        "save_every": value("saves", 3.0),
        "save_points": 1.0,
        "goals_conceded_every": 2.0,
        "goals_conceded_points": -1.0,
        "defensive_contribution_points": 2.0,
    }


def _poisson_expected_floor(
    mean: float,
    divisor: int,
    *,
    max_goals: int = 12,
) -> float:
    """Return E[floor(goals / divisor)] for a Poisson variable."""
    mean = max(0.0, mean)
    if mean == 0.0:
        return 0.0

    probability = exp(-mean)
    result = 0.0
    for goals in range(max_goals + 1):
        if goals > 0:
            probability *= mean / goals
        result += (goals // divisor) * probability

    # The tail above max_goals is negligible for the football-scale means used
    # here. This cap keeps the calculation deterministic and bounded.
    return result


def estimate_start_probability(player: dict[str, Any]) -> float:
    """Estimate starting probability from official FPL fields."""
    chance = player.get("chance_of_playing_this_round")
    availability = 1.0 if chance is None else min(1.0, max(0.0, _float(chance) / 100.0))

    minutes = _float(player.get("minutes"))
    starts = _float(player.get("starts"))
    if minutes <= 0 and starts <= 0:
        recent_start_signal = 0.0
    else:
        recent_start_signal = min(1.0, max(0.0, starts / max(1.0, minutes / 90.0)))

    start_probability = min(availability, recent_start_signal)
    if str(player.get("status", "a")) in {"i", "s", "u"}:
        start_probability = 0.0
    return min(1.0, max(0.0, start_probability))


def expected_points_for_fixture(
    *,
    player: dict[str, Any],
    gameweek: int,
    expected_goals: float | None = None,
    expected_assists: float | None = None,
    clean_sheet_probability: float | None = None,
    expected_bonus: float | None = None,
    bootstrap_data: dict[str, Any] | None = None,
    start_probability: float | None = None,
    expected_minutes: float | None = None,
    expected_saves: float | None = None,
    expected_defensive_contribution: float | None = None,
    defensive_contribution_probability: float | None = None,
    expected_goals_conceded: float | None = None,
) -> ExpectedPoints:
    """Calculate transparent expected points for one player/fixture."""
    bootstrap_data = bootstrap_data or {}
    position_id = int(player.get("position_id", player.get("element_type", 0)))
    rules = _scoring_rules(bootstrap_data, position_id)

    warnings: list[str] = []
    complete = True

    if start_probability is None:
        start_probability = estimate_start_probability(player)
    else:
        start_probability = _probability(start_probability)

    if expected_minutes is None:
        expected_minutes = 90.0 * start_probability
    else:
        expected_minutes = max(0.0, min(90.0, _float(expected_minutes)))

    xg = _float(expected_goals, 0.0)
    xa = _float(expected_assists, 0.0)
    minute_fraction = expected_minutes / 90.0

    if expected_goals is None:
        complete = False
        warnings.append("Expected goals input unavailable.")
    if expected_assists is None:
        complete = False
        warnings.append("Expected assists input unavailable.")

    cs_probability = _probability(clean_sheet_probability) if clean_sheet_probability is not None else None
    if cs_probability is None:
        complete = False
        warnings.append("Clean-sheet probability unavailable.")

    bonus = max(0.0, _float(expected_bonus)) if expected_bonus is not None else 0.0
    if expected_bonus is None:
        complete = False
        warnings.append("Expected bonus input unavailable.")

    # Without a substitute-appearance model, start probability is the
    # probability of appearing. Expected minutes then estimates the chance of
    # crossing the 60-minute threshold conditional on starting.
    appearance_probability = min(1.0, max(0.0, start_probability))
    sixty_plus_probability = appearance_probability * min(1.0, minute_fraction)
    appearance_points = sixty_plus_probability * 2.0 + max(
        0.0, appearance_probability - sixty_plus_probability
    ) * 1.0

    expected_goal_points = xg * minute_fraction * rules["goal"]
    expected_assist_points = xa * minute_fraction * rules["assist"]
    expected_cs_points = (
        cs_probability * sixty_plus_probability * rules["clean_sheet"]
        if cs_probability is not None
        else 0.0
    )

    goals_conceded_points = 0.0
    if position_id in {1, 2}:
        if expected_goals_conceded is None:
            complete = False
            warnings.append("Expected goals-conceded input unavailable for GK/DEF.")
        else:
            expected_goals_conceded_value = max(0.0, _float(expected_goals_conceded)) * minute_fraction
            goals_conceded_points = (
                _poisson_expected_floor(expected_goals_conceded_value, 2)
                * rules["goals_conceded_points"]
                * sixty_plus_probability
            )
    else:
        expected_goals_conceded_value = 0.0

    save_points = 0.0
    if position_id == 1:
        if expected_saves is None:
            complete = False
            warnings.append("Expected goalkeeper saves input unavailable.")
        else:
            saves = max(0.0, _float(expected_saves)) * minute_fraction
            save_points = saves / max(1.0, rules["save_every"]) * rules["save_points"]

    defensive_contribution_points = 0.0
    if position_id in {2, 3, 4}:
        threshold = {2: 10.0, 3: 12.0, 4: 12.0}[position_id]
        if defensive_contribution_probability is not None:
            dc_probability = _probability(defensive_contribution_probability)
        elif expected_defensive_contribution is not None:
            # Explicitly labelled baseline: expected DC / threshold is used as
            # a bounded probability proxy until a calibrated distribution is
            # available.
            dc_probability = min(1.0, max(0.0, _float(expected_defensive_contribution) / threshold))
            warnings.append("Defensive-contribution probability derived from expected contribution.")
        else:
            complete = False
            warnings.append("Defensive-contribution input unavailable.")
            dc_probability = 0.0
        defensive_contribution_points = dc_probability * sixty_plus_probability * rules["defensive_contribution_points"]

    total = (
        appearance_points
        + expected_goal_points
        + expected_assist_points
        + expected_cs_points
        + bonus * sixty_plus_probability
        + goals_conceded_points
        + save_points * sixty_plus_probability
        + defensive_contribution_points
    )

    expected_saves_value = (
        max(0.0, _float(expected_saves)) * minute_fraction
        if expected_saves is not None
        else 0.0
    )

    return ExpectedPoints(
        player_id=int(player["id"]),
        gameweek=int(gameweek),
        expected_points=max(0.0, total),
        expected_minutes=expected_minutes,
        expected_goals=xg * minute_fraction,
        expected_assists=xa * minute_fraction,
        expected_clean_sheet=(cs_probability * sixty_plus_probability if cs_probability is not None else 0.0),
        expected_bonus=bonus * sixty_plus_probability,
        expected_saves=expected_saves_value,
        expected_goals_conceded_points=goals_conceded_points,
        expected_defensive_contribution_points=defensive_contribution_points,
        expected_appearance_points=appearance_points,
        data_complete=complete,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def build_baseline_player_projection(
    *,
    players: list[dict[str, Any]],
    fixtures: list[dict[str, Any]],
    target_gameweek: int,
    bootstrap_data: dict[str, Any],
    horizon: int = 3,
) -> dict[int, dict[str, Any]]:
    """Build a baseline projection for every player over a fixture horizon."""
    projections: dict[int, dict[str, Any]] = {}

    for player in players:
        player_id = int(player["id"])
        team_id = int(player["team_id"])
        relevant = [
            fixture for fixture in fixtures
            if target_gameweek <= int(fixture.get("gameweek", -1)) < target_gameweek + horizon
            and team_id in {
                int(fixture.get("home_team_id", -1)),
                int(fixture.get("away_team_id", -1)),
            }
        ]
        rows = []
        for fixture in sorted(relevant, key=lambda row: int(row["gameweek"])):
            result = expected_points_for_fixture(
                player=player,
                gameweek=int(fixture["gameweek"]),
                expected_goals=None,
                expected_assists=None,
                clean_sheet_probability=None,
                expected_bonus=None,
                bootstrap_data=bootstrap_data,
            )
            rows.append({
                "gameweek": int(fixture["gameweek"]),
                "fixture_id": fixture.get("fixture_id"),
                "fdr": fixture.get("fdr"),
                "home": fixture.get("home"),
                "expected_points": result.expected_points,
                "data_complete": result.data_complete,
                "warnings": result.warnings,
            })
        projections[player_id] = {
            "player_id": player_id,
            "player_name": player.get("name", player.get("web_name")),
            "team_id": team_id,
            "price": _float(player.get("price")) / 10.0 if _float(player.get("price")) >= 10 else _float(player.get("price")),
            "fixtures": rows,
            "horizon_expected_points": sum(row["expected_points"] for row in rows),
            "projection_complete": bool(rows) and all(row["data_complete"] for row in rows),
            "model_version": MODEL_VERSION,
        }

    return projections
