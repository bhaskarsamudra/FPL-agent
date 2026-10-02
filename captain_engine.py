"""
captain_engine.py

Captain and vice-captain candidate evaluation.

Batch 12 upgrades this from horizon-only ranking to a Gameweek-specific,
transparent captain/vice-captain decision. Double Gameweeks are handled by
summing the player's fixture projections for the target Gameweek.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

MODEL_VERSION = "captain_v2"


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if number != number or number in (float("inf"), float("-inf")):
            return default
        return number
    except (TypeError, ValueError):
        return default


def _target_projection(
    projection: dict[str, Any],
    *,
    gameweek: int | None,
) -> tuple[float, int, bool, tuple[str, ...]]:
    """Return expected points, fixture count, completeness and warnings."""
    fixtures = projection.get("fixtures", []) or []
    if gameweek is None:
        selected = fixtures
    else:
        selected = [
            row for row in fixtures
            if int(row.get("gameweek", -1)) == int(gameweek)
        ]

    if not selected:
        return 0.0, 0, False, ("No fixture projection is available for the target Gameweek.",)

    points = sum(_number(row.get("expected_points")) for row in selected)
    complete = all(bool(row.get("data_complete")) for row in selected)
    warnings = tuple(
        warning
        for row in selected
        for warning in row.get("warnings", ())
    )
    return points, len(selected), complete, tuple(dict.fromkeys(warnings))


@dataclass(frozen=True)
class CaptainCandidate:
    player_id: int
    player_name: str
    expected_points: float
    ownership_percent: float
    ceiling_proxy: float
    captain_score: float
    reasons: tuple[str, ...]
    gameweek: int | None = None
    fixture_count: int = 0
    data_complete: bool = False
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CaptainDecision:
    """Captain and vice-captain pair for one target Gameweek."""

    gameweek: int
    captain: CaptainCandidate
    vice_captain: CaptainCandidate
    data_complete: bool
    warnings: tuple[str, ...]
    model_version: str = MODEL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def rank_captain_candidates(
    *,
    squad: list[dict[str, Any]],
    projections: dict[int, dict[str, Any]],
    max_candidates: int = 5,
    gameweek: int | None = None,
) -> list[CaptainCandidate]:
    """
    Rank captain candidates using the target Gameweek's expected points.

    If ``gameweek`` is supplied, all fixtures in that Gameweek are summed,
    which correctly handles Double Gameweeks. If it is omitted, the legacy
    horizon projection is used for backward compatibility.

    Ownership is reported for context only and never changes the ranking.
    The ceiling proxy is deliberately a transparent diagnostic: it is the
    highest fixture expected-points contribution in the selected period, not
    a calibrated probability distribution or rank prediction.
    """

    rows: list[CaptainCandidate] = []

    for player in squad:
        player_id = int(player["id"])
        projection = projections.get(player_id)
        if not projection:
            continue

        if gameweek is None:
            expected = _number(projection.get("horizon_expected_points"))
            fixture_rows = projection.get("fixtures", []) or []
            fixture_count = len(fixture_rows)
            complete = bool(projection.get("projection_complete"))
            warnings = tuple(
                warning
                for row in fixture_rows
                for warning in row.get("warnings", ())
            )
            selected_rows = fixture_rows
        else:
            expected, fixture_count, complete, warnings = _target_projection(
                projection, gameweek=gameweek
            )
            selected_rows = [
                row for row in projection.get("fixtures", []) or []
                if int(row.get("gameweek", -1)) == int(gameweek)
            ]

        if fixture_count == 0:
            # Backward-compatible fallback for callers that only provide the
            # legacy horizon projection. Real fixture-aware projections use
            # the target Gameweek path above.
            expected = _number(projection.get("horizon_expected_points"))
            fixture_rows = projection.get("fixtures", []) or []
            fixture_count = len(fixture_rows)
            if fixture_count == 0:
                fixture_count = 1
                selected_rows = [{"expected_points": expected}]
            else:
                selected_rows = fixture_rows
            complete = bool(projection.get("projection_complete", True))
            warnings = tuple(
                warning
                for row in fixture_rows
                for warning in row.get("warnings", ())
            )

        if fixture_count == 0:
            continue

        ceiling_proxy = max(
            (_number(row.get("expected_points")) for row in selected_rows),
            default=0.0,
        )
        ownership = _number(player.get("selected_by_percent"))

        reasons = [
            f"Target expected points: {expected:.2f}.",
            f"Projected fixture count: {fixture_count}.",
            f"Official FPL ownership: {ownership:.1f}%.",
            "Ceiling proxy is the highest fixture projection, not a calibrated ceiling probability.",
        ]
        if not complete:
            reasons.append("One or more target fixture projections are incomplete.")

        rows.append(
            CaptainCandidate(
                player_id=player_id,
                player_name=str(player.get("name", player_id)),
                expected_points=expected,
                ownership_percent=ownership,
                ceiling_proxy=ceiling_proxy,
                captain_score=expected,
                reasons=tuple(reasons),
                gameweek=gameweek,
                fixture_count=fixture_count,
                data_complete=complete,
                warnings=warnings,
            )
        )

    rows.sort(
        key=lambda row: (row.captain_score, row.expected_points, -row.player_id),
        reverse=True,
    )
    return rows[:max_candidates]


def select_captain_pair(
    *,
    squad: list[dict[str, Any]],
    projections: dict[int, dict[str, Any]],
    gameweek: int,
) -> CaptainDecision:
    """Select the top two distinct captain candidates for one Gameweek."""
    if gameweek < 1:
        raise ValueError("gameweek must be positive.")

    candidates = rank_captain_candidates(
        squad=squad,
        projections=projections,
        max_candidates=len(squad),
        gameweek=gameweek,
    )
    if len(candidates) < 2:
        raise ValueError("At least two projected squad players are required for captain and vice-captain.")

    warnings = tuple(dict.fromkeys(
        (*candidates[0].warnings, *candidates[1].warnings)
    ))
    return CaptainDecision(
        gameweek=gameweek,
        captain=candidates[0],
        vice_captain=candidates[1],
        data_complete=candidates[0].data_complete and candidates[1].data_complete,
        warnings=warnings,
    )
