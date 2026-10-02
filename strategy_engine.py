"""
strategy_engine.py

Top-level deterministic FPL strategy coordinator.

The strategy engine consumes verified state and outputs structured actions.
An LLM may later explain this output, but it must not replace this layer.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from captain_engine import CaptainCandidate, rank_captain_candidates
from chip_engine import ChipAssessment, assess_chips
from transfer_engine import TransferCandidate, generate_transfer_candidates


@dataclass(frozen=True)
class StrategyRecommendation:
    action: str
    priority: str
    confidence: str
    summary: str
    evidence: tuple[str, ...]
    source_status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StrategyResult:
    gameweek: int
    recommendations: tuple[StrategyRecommendation, ...]
    transfers: tuple[TransferCandidate, ...]
    captains: tuple[CaptainCandidate, ...]
    chips: tuple[ChipAssessment, ...]
    data_complete: bool
    warnings: tuple[str, ...]
    engine_version: str = "strategy_v1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_strategy(
    *,
    manager_state: Any,
    market_players: list[dict[str, Any]],
    projections: dict[int, dict[str, Any]],
    available_chips: list[str],
    horizon_gameweeks: list[int],
    fixture_count_by_gameweek: dict[int, int] | None = None,
) -> StrategyResult:
    """
    Produce a single universal strategy for the manager's FPL team.

    Mini-league/rival information is deliberately not an input to this
    decision function yet; it belongs in a contextual analytics layer.
    """

    squad = list(manager_state.squad)

    transfer_candidates = generate_transfer_candidates(
        squad=squad,
        market=market_players,
        projections=projections,
        bank=float(manager_state.bank),
        free_transfers=int(manager_state.free_transfers),
    )

    captain_gameweek = int(horizon_gameweeks[0]) if horizon_gameweeks else int(manager_state.gameweek)
    captain_candidates = rank_captain_candidates(
        squad=squad,
        projections=projections,
        gameweek=captain_gameweek,
    )

    captain_xp = (
        captain_candidates[0].expected_points
        if captain_candidates
        else 0.0
    )

    starter_ids = {
        int(player["id"])
        for player in squad
        if int(player.get("squad_position", 99)) <= 11
    }

    bench_xp = sum(
        float(projections.get(int(player["id"]), {}).get(
            "horizon_expected_points", 0.0
        ))
        for player in squad
        if int(player["id"]) not in starter_ids
    )

    best_transfer_gain = (
        transfer_candidates[0].expected_gain
        if transfer_candidates
        else 0.0
    )

    chips = assess_chips(
        available_chips=available_chips,
        horizon_gameweeks=horizon_gameweeks,
        current_squad_expected_points=sum(
            float(projections.get(player_id, {}).get(
                "horizon_expected_points", 0.0
            ))
            for player_id in starter_ids
        ),
        best_transfer_expected_gain=best_transfer_gain,
        bench_expected_points=bench_xp,
        captain_expected_points=captain_xp,
        fixture_count_by_gameweek=fixture_count_by_gameweek,
    )

    recommendations = []
    warnings = []

    if transfer_candidates:
        top = transfer_candidates[0]
        if top.data_complete:
            action = (
                f"TRANSFER {top.sell_name} -> {top.buy_name}"
                if top.expected_gain > 0.25
                else "ROLL"
            )
            priority = "HIGH" if top.expected_gain >= 2.0 else "MEDIUM"
            confidence = "MEDIUM"
            evidence = top.rationale
        else:
            action = "WATCH"
            priority = "MEDIUM"
            confidence = "LOW"
            evidence = top.rationale
            warnings.append(
                "Top transfer candidate has incomplete expected-points inputs."
            )
    else:
        action = "ROLL"
        priority = "MEDIUM"
        confidence = "LOW"
        evidence = (
            "No legal positive-gain transfer candidate was generated "
            "from the supplied data.",
        )

    recommendations.append(
        StrategyRecommendation(
            action=action,
            priority=priority,
            confidence=confidence,
            summary="Primary transfer decision from the deterministic engine.",
            evidence=tuple(evidence),
            source_status="verified FPL state + model outputs",
        )
    )

    if captain_candidates:
        captain = captain_candidates[0]
        recommendations.append(
            StrategyRecommendation(
                action=f"CAPTAIN {captain.player_name}",
                priority="HIGH",
                confidence="MEDIUM",
                summary="Highest current captain expected-value candidate.",
                evidence=captain.reasons,
                source_status="verified FPL state + projection layer",
            )
        )
    else:
        warnings.append("No captain candidate could be generated.")

    for chip in chips:
        if chip.recommendation == "CONSIDER":
            recommendations.append(
                StrategyRecommendation(
                    action=f"{chip.chip.upper()} {chip.recommendation}",
                    priority="MEDIUM",
                    confidence=chip.confidence.upper(),
                    summary=f"Chip opportunity detected for {chip.chip}.",
                    evidence=chip.reasons,
                    source_status="deterministic chip framework",
                )
            )

    data_complete = not warnings and all(
        candidate.data_complete
        for candidate in transfer_candidates[:1]
    ) if transfer_candidates else False

    return StrategyResult(
        gameweek=int(manager_state.gameweek),
        recommendations=tuple(recommendations),
        transfers=tuple(transfer_candidates),
        captains=tuple(captain_candidates),
        chips=tuple(chips),
        data_complete=data_complete,
        warnings=tuple(warnings),
    )
