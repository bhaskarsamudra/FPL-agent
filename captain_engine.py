"""
captain_engine.py

Authoritative captain and vice-captain intelligence.

The engine supports two related uses:

1. Immediate Gameweek captain/vice-captain selection.
2. Multi-Gameweek captaincy context used by the strategic planner.

The same captain projections are therefore reused by normal captaincy and
Triple Captain planning. Dream Team data is intentionally absent: captain
selection is based only on information available to the decision engine.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

MODEL_VERSION = "captain_v3"
DEFAULT_CAPTAIN_MULTIPLIER = 2.0
DEFAULT_TRIPLE_CAPTAIN_MULTIPLIER = 3.0


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if number != number or number in (float("inf"), float("-inf")):
            return default
        return number
    except (TypeError, ValueError):
        return default


def _fixture_rows_for_gameweek(
    projection: dict[str, Any],
    gameweek: int,
) -> list[dict[str, Any]]:
    return [
        row
        for row in projection.get("fixtures", []) or []
        if int(row.get("gameweek", -1)) == int(gameweek)
    ]


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
        selected = _fixture_rows_for_gameweek(projection, gameweek)

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


@dataclass(frozen=True)
class CaptaincyGameweekOpportunity:
    """Captaincy intelligence for one future Gameweek."""

    gameweek: int
    best_player_id: int | None
    best_player_name: str | None
    best_expected_points: float
    vice_player_id: int | None
    vice_player_name: str | None
    vice_expected_points: float
    captain_opportunity_cost: float
    best_fixture_count: int
    data_complete: bool
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CaptaincyHorizonContext:
    """Point-in-time captaincy context across a future planning horizon.

    This is a planning reference, not a list of final recommendations. Each
    Gameweek is evaluated independently so the strategic layer can account for
    captaincy opportunity cost and future captaincy availability.
    """

    horizon_gameweeks: tuple[int, ...]
    opportunities: tuple[CaptaincyGameweekOpportunity, ...]
    captain_multiplier: float = DEFAULT_CAPTAIN_MULTIPLIER
    triple_captain_multiplier: float = DEFAULT_TRIPLE_CAPTAIN_MULTIPLIER
    data_complete: bool = False
    warnings: tuple[str, ...] = ()
    model_version: str = MODEL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def for_gameweek(self, gameweek: int) -> CaptaincyGameweekOpportunity | None:
        return next(
            (item for item in self.opportunities if item.gameweek == int(gameweek)),
            None,
        )


@dataclass(frozen=True)
class TripleCaptainOpportunity:
    """Evidence record for using Triple Captain in one future Gameweek."""

    gameweek: int
    player_id: int
    player_name: str
    normal_captain_points: float
    triple_captain_points: float
    incremental_value: float
    captain_opportunity_cost: float
    future_opportunity_cost: float
    timing_value: float
    fixture_count: int
    data_complete: bool
    warnings: tuple[str, ...] = ()
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
    Rank captain candidates using expected points for the requested period.

    If ``gameweek`` is supplied, all fixtures in that Gameweek are summed,
    which correctly handles Double Gameweeks. If it is omitted, the legacy
    horizon projection is used for backward compatibility.

    Ownership is reported for context only and never changes the ranking.
    The ceiling proxy remains a transparent diagnostic rather than a calibrated
    probability distribution.
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
            complete = bool(projection.get("projection_complete", False))
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
            selected_rows = _fixture_rows_for_gameweek(projection, gameweek)

        if fixture_count == 0:
            # Backward-compatible fallback for callers that only provide the
            # legacy horizon projection.
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
        raise ValueError(
            "At least two projected squad players are required for captain and vice-captain."
        )

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


def build_captaincy_horizon(
    *,
    squad: Sequence[dict[str, Any]],
    projections: dict[int, dict[str, Any]],
    horizon_gameweeks: Sequence[int],
    captain_multiplier: float = DEFAULT_CAPTAIN_MULTIPLIER,
    triple_captain_multiplier: float = DEFAULT_TRIPLE_CAPTAIN_MULTIPLIER,
) -> CaptaincyHorizonContext:
    """Build reusable captaincy intelligence for every Gameweek in a horizon."""
    horizon = tuple(int(gw) for gw in horizon_gameweeks)
    if not horizon:
        raise ValueError("At least one future Gameweek is required.")
    if tuple(sorted(horizon)) != horizon or len(set(horizon)) != len(horizon):
        raise ValueError("Horizon Gameweeks must be strictly increasing.")
    if captain_multiplier < 1.0:
        raise ValueError("captain_multiplier must be at least 1.0")
    if triple_captain_multiplier < captain_multiplier:
        raise ValueError("triple_captain_multiplier cannot be below captain_multiplier")

    opportunities: list[CaptaincyGameweekOpportunity] = []
    warnings: list[str] = []

    for gameweek in horizon:
        candidates = rank_captain_candidates(
            squad=list(squad),
            projections=projections,
            max_candidates=len(squad),
            gameweek=gameweek,
        )

        if not candidates:
            message = f"No captain projection is available for GW{gameweek}."
            warnings.append(message)
            opportunities.append(
                CaptaincyGameweekOpportunity(
                    gameweek=gameweek,
                    best_player_id=None,
                    best_player_name=None,
                    best_expected_points=0.0,
                    vice_player_id=None,
                    vice_player_name=None,
                    vice_expected_points=0.0,
                    captain_opportunity_cost=0.0,
                    best_fixture_count=0,
                    data_complete=False,
                    warnings=(message,),
                )
            )
            continue

        best = candidates[0]
        vice = candidates[1] if len(candidates) > 1 else None
        opportunity_cost = (
            max(0.0, best.expected_points - vice.expected_points)
            if vice is not None
            else 0.0
        )
        opportunity_warnings = tuple(dict.fromkeys(
            (*best.warnings, *(vice.warnings if vice else ()))
        ))
        opportunities.append(
            CaptaincyGameweekOpportunity(
                gameweek=gameweek,
                best_player_id=best.player_id,
                best_player_name=best.player_name,
                best_expected_points=best.expected_points,
                vice_player_id=vice.player_id if vice else None,
                vice_player_name=vice.player_name if vice else None,
                vice_expected_points=vice.expected_points if vice else 0.0,
                captain_opportunity_cost=opportunity_cost,
                best_fixture_count=best.fixture_count,
                data_complete=best.data_complete and bool(vice and vice.data_complete),
                warnings=opportunity_warnings,
            )
        )
        warnings.extend(opportunity_warnings)

    return CaptaincyHorizonContext(
        horizon_gameweeks=horizon,
        opportunities=tuple(opportunities),
        captain_multiplier=float(captain_multiplier),
        triple_captain_multiplier=float(triple_captain_multiplier),
        data_complete=bool(opportunities) and all(item.data_complete for item in opportunities),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def evaluate_triple_captain_opportunities(
    context: CaptaincyHorizonContext,
) -> tuple[TripleCaptainOpportunity, ...]:
    """Evaluate Triple Captain timing using the same captaincy context.

    The normal-vs-triple incremental value is transparent: one additional
    captain multiplier applied to the projected captain points. Timing value
    also subtracts the strongest future normal-captain opportunity in the
    supplied horizon, making opportunity cost explicit without claiming a
    probabilistic chip recommendation.
    """
    complete_opportunities = [
        item for item in context.opportunities
        if item.data_complete and item.best_player_id is not None
    ]
    result: list[TripleCaptainOpportunity] = []

    for item in complete_opportunities:
        incremental = item.best_expected_points * (
            context.triple_captain_multiplier - context.captain_multiplier
        )
        future_best = max(
            (
                other.best_expected_points
                for other in complete_opportunities
                if other.gameweek > item.gameweek
            ),
            default=0.0,
        )
        future_opportunity_cost = max(0.0, future_best - item.best_expected_points)
        timing_value = incremental - future_opportunity_cost
        result.append(
            TripleCaptainOpportunity(
                gameweek=item.gameweek,
                player_id=int(item.best_player_id),
                player_name=str(item.best_player_name),
                normal_captain_points=item.best_expected_points * context.captain_multiplier,
                triple_captain_points=item.best_expected_points * context.triple_captain_multiplier,
                incremental_value=incremental,
                captain_opportunity_cost=item.captain_opportunity_cost,
                future_opportunity_cost=future_opportunity_cost,
                timing_value=timing_value,
                fixture_count=item.best_fixture_count,
                data_complete=item.data_complete,
                warnings=item.warnings,
            )
        )

    return tuple(
        sorted(
            result,
            key=lambda item: (
                item.timing_value,
                item.incremental_value,
                item.normal_captain_points,
                -item.gameweek,
            ),
            reverse=True,
        )
    )
