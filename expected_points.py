"""
expected_points.py

Transparent baseline expected-FPL-points engine.

This is deliberately a framework rather than a claim that the current
formula is already optimal. Every contribution is exposed so it can be
validated and replaced independently.

Inputs should come from official FPL data and validated fixture/model
outputs. Missing probability inputs are not silently invented.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


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

    data_complete: bool
    warnings: tuple[str, ...]
    model_version: str = "xp_baseline_v1"

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
    """
    Read official scoring rules from bootstrap when available.

    A small fallback exists because older/test fixtures may not contain
    the scoring section. Production runs should report the fallback.
    """

    positions = bootstrap_data.get("element_types", [])
    position = next(
        (row for row in positions if int(row.get("id", -1)) == int(position_id)),
        None,
    )

    scoring = (position or {}).get("scoring", {})

    def value(name: str, fallback: float) -> float:
        raw = scoring.get(name, fallback)
        if isinstance(raw, dict):
            # Some FPL scoring fields are position-specific mappings.
            raw = raw.get(str(position_id), raw.get(position_id, fallback))
        return _float(raw, fallback)

    # These defaults match the conventional FPL scoring structure and are
    # only used when the API does not expose a corresponding rule.
    goal_fallback = {1: 6, 2: 6, 3: 5, 4: 4}.get(position_id, 4)
    clean_sheet_fallback = {1: 4, 2: 4, 3: 1, 4: 0}.get(position_id, 0)

    return {
        "appearance_1": value("minutes", 1.0),
        "goal": value("goals_scored", goal_fallback),
        "assist": value("assists", 3.0),
        "clean_sheet": value("clean_sheets", clean_sheet_fallback),
        "bonus": value("bonus", 1.0),
    }


def estimate_start_probability(player: dict[str, Any]) -> float:
    """
    Estimate starting probability from official FPL fields.

    This is intentionally conservative:
    chance_of_playing_this_round is treated as an availability ceiling,
    while starts/minutes provide the historical starting signal.
    """

    chance = player.get("chance_of_playing_this_round")
    availability = 1.0 if chance is None else min(1.0, max(0.0, _float(chance, 0.0) / 100.0))

    minutes = _float(player.get("minutes"))
    starts = _float(player.get("starts"))

    if minutes <= 0 and starts <= 0:
        recent_start_signal = 0.0
    else:
        recent_start_signal = min(1.0, max(
            starts / max(1.0, minutes / 90.0),
            0.0,
        ) / 1.0)

    # If minutes/starts are sparse, availability should not magically
    # produce a high starting probability.
    start_probability = min(availability, recent_start_signal)

    status = str(player.get("status", "a"))
    if status in {"i", "s", "u"}:
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
) -> ExpectedPoints:
    """
    Calculate transparent expected points for one player/fixture.

    expected_goals/assists/clean-sheet probability should come from the
    validated football-model layers. They are optional here so the engine
    can be tested independently.

    If a key probability is missing, its contribution is excluded and a
    warning is returned. We do not invent a hidden value.
    """

    bootstrap_data = bootstrap_data or {}
    position_id = int(player.get("position_id", player.get("element_type", 0)))

    rules = _scoring_rules(bootstrap_data, position_id)

    warnings = []
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

    if expected_goals is None:
        complete = False
        warnings.append("Expected goals input unavailable.")

    if expected_assists is None:
        complete = False
        warnings.append("Expected assists input unavailable.")

    cs_probability = (
        _probability(clean_sheet_probability)
        if clean_sheet_probability is not None
        else None
    )

    if cs_probability is None:
        complete = False
        warnings.append("Clean-sheet probability unavailable.")

    bonus = (
        max(0.0, _float(expected_bonus))
        if expected_bonus is not None
        else 0.0
    )

    if expected_bonus is None:
        complete = False
        warnings.append("Expected bonus input unavailable.")

    # FPL's expected goals/assists values are season-level rates, so scale
    # them by expected minutes as a first transparent baseline.
    minute_fraction = expected_minutes / 90.0

    appearance_points = (
        start_probability * 2.0
        + (1.0 - start_probability) * start_probability * rules["appearance_1"]
    )

    expected_goal_points = xg * minute_fraction * rules["goal"]
    expected_assist_points = xa * minute_fraction * rules["assist"]
    expected_cs_points = (
        cs_probability * start_probability * rules["clean_sheet"]
        if cs_probability is not None
        else 0.0
    )

    total = (
        appearance_points
        + expected_goal_points
        + expected_assist_points
        + expected_cs_points
        + bonus
    )

    return ExpectedPoints(
        player_id=int(player["id"]),
        gameweek=int(gameweek),
        expected_points=max(0.0, total),
        expected_minutes=expected_minutes,
        expected_goals=xg * minute_fraction,
        expected_assists=xa * minute_fraction,
        expected_clean_sheet=(
            cs_probability * start_probability
            if cs_probability is not None
            else 0.0
        ),
        expected_bonus=bonus,
        data_complete=complete,
        warnings=tuple(warnings),
    )


def build_baseline_player_projection(
    *,
    players: list[dict[str, Any]],
    fixtures: list[dict[str, Any]],
    target_gameweek: int,
    bootstrap_data: dict[str, Any],
    horizon: int = 3,
) -> dict[int, dict[str, Any]]:
    """
    Build a baseline projection for every player.

    This function deliberately does NOT fabricate football probabilities.
    It uses official FPL expected-goal/assist fields and FDR only as a
    scouting/context field. Fixture-specific xG and clean-sheet probabilities
    must be supplied by the validated football model before being treated as
    complete strategy inputs.
    """

    projections: dict[int, dict[str, Any]] = {}

    for player in players:
        player_id = int(player["id"])
        team_id = int(player["team_id"])

        relevant = [
            fixture for fixture in fixtures
            if int(fixture.get("gameweek", -1)) >= target_gameweek
            and int(fixture.get("gameweek", -1)) < target_gameweek + horizon
            and (
                int(fixture.get("home_team_id", -1)) == team_id
                or int(fixture.get("away_team_id", -1)) == team_id
            )
        ]

        rows = []

        for fixture in sorted(relevant, key=lambda row: int(row["gameweek"])):
            # We intentionally leave fixture xG/CS probability unset until
            # the validated expected-goals layer is connected.
            result = expected_points_for_fixture(
                player=player,
                gameweek=int(fixture["gameweek"]),
                expected_goals=None,
                expected_assists=None,
                clean_sheet_probability=None,
                expected_bonus=None,
                bootstrap_data=bootstrap_data,
            )

            rows.append(
                {
                    "gameweek": int(fixture["gameweek"]),
                    "fixture_id": fixture.get("fixture_id"),
                    "fdr": fixture.get("fdr"),
                    "home": fixture.get("home"),
                    "expected_points": result.expected_points,
                    "data_complete": result.data_complete,
                    "warnings": result.warnings,
                }
            )

        projections[player_id] = {
            "player_id": player_id,
            "player_name": player.get("name", player.get("web_name")),
            "team_id": team_id,
            "price": _float(player.get("price")) / 10.0
            if _float(player.get("price")) >= 10
            else _float(player.get("price")),
            "fixtures": rows,
            "horizon_expected_points": sum(
                row["expected_points"] for row in rows
            ),
            "projection_complete": bool(rows) and all(
                row["data_complete"] for row in rows
            ),
        }

    return projections
