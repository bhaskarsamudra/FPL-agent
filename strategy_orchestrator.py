"""
strategy_orchestrator.py

Batch 16 strategic decision orchestration.

This module connects the existing deterministic engines into one decision
framework. It deliberately keeps four concepts separate:

- absolute expected points for our own decision;
- rival context, which describes relative pressure but does not replace the
  underlying forecast;
- Gameweek Dream Team, which is an observed post-GW ceiling and therefore
  cannot be used as a future input;
- season-to-date Dream Team, which is an evolving long-horizon reference and
  may only be used at the version available by the decision timestamp.

The orchestrator is intentionally bounded. It compares a small set of
high-value alternatives instead of brute-forcing every possible squad/chip
combination. Exhaustive multi-chip optimisation remains a later capability.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

from production_projection import ProductionProjectionResult

from captain_engine import (
    CaptainCandidate,
    CaptaincyHorizonContext,
    build_captaincy_horizon,
    rank_captain_candidates,
)
from chip_engine import ChipScenarioEvaluation
from dream_team_engine import DreamTeamGap, DreamTeamSnapshot
from rival_engine import RivalSnapshot, identify_nearest_rivals
from multi_gw_strategy import MultiGWStrategicPlan, evaluate_multi_gw_options
from transfer_engine import TransferCandidate, generate_transfer_candidates


ENGINE_VERSION = "strategy_orchestrator_v1_2"
PRODUCTION_PROJECTION_ENGINE_VERSION = "strategy_orchestrator_v1_3"

# Architectural invariant: Dream Team data is benchmark/learning context only.
# It must never become a player-selection input for the Strategist.
DREAM_TEAM_SELECTION_POLICY = "benchmark_only"


@dataclass(frozen=True)
class RivalDecisionContext:
    """Relative league context kept separate from absolute strategy value."""

    user_team_id: int
    user_rank: int | None
    user_total_points: int | None
    nearest_rivals: tuple[RivalSnapshot, ...]
    nearest_ahead: tuple[RivalSnapshot, ...]
    nearest_behind: tuple[RivalSnapshot, ...]
    leader_gap: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DreamTeamDecisionContext:
    """Dream Team benchmark context allowed at a decision timestamp.

    Dream Team data is deliberately excluded from strategic option scoring.
    The Strategist must independently generate its decision; Dream Team data
    is retained for benchmark, gap-analysis and later learning purposes.
    """

    season_to_date: DreamTeamSnapshot | None
    season_gap: DreamTeamGap | None
    gameweek_outcome: DreamTeamGap | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StrategicDecisionOption:
    """One bounded strategic alternative on a common scoring basis."""

    option_id: str
    option_type: str
    description: str
    projected_horizon_points: float
    incremental_horizon_points: float
    captain_player_id: int | None
    transfer: TransferCandidate | None = None
    chip: ChipScenarioEvaluation | None = None
    data_complete: bool = True
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StrategicDecision:
    """Complete Batch 16 strategic decision package."""

    decision_gameweek: int
    target_gameweek: int
    selected_option: StrategicDecisionOption | None
    options: tuple[StrategicDecisionOption, ...]
    transfer_candidates: tuple[TransferCandidate, ...]
    captain_candidates: tuple[CaptainCandidate, ...]
    captaincy_horizon: CaptaincyHorizonContext | None
    chip_opportunities: tuple[ChipScenarioEvaluation, ...]
    multi_gw_plan: MultiGWStrategicPlan | None
    rival_context: RivalDecisionContext | None
    dream_context: DreamTeamDecisionContext | None
    data_complete: bool
    warnings: tuple[str, ...]
    dream_team_selection_policy: str = DREAM_TEAM_SELECTION_POLICY
    engine_version: str = ENGINE_VERSION
    projection_model_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_rival_decision_context(
    *,
    standings: Sequence[dict[str, Any]],
    user_team_id: int,
    nearest_limit: int = 5,
) -> RivalDecisionContext:
    """Build bounded rival context from official league standings."""

    rows = list(standings)
    user = next(
        (row for row in rows if int(row.get("entry", -1)) == int(user_team_id)),
        None,
    )
    if user is None:
        raise ValueError("User team was not found in league standings.")

    user_rank = int(user.get("rank", 0)) if user.get("rank") is not None else None
    user_total = int(user.get("total", 0)) if user.get("total") is not None else None
    rivals = build_rivals = []
    # Reuse the existing rival engine rather than creating a second standings
    # transformation implementation.
    rivals = build_rival_snapshots_for_context(rows, user_team_id)
    nearest = identify_nearest_rivals(rivals, limit=nearest_limit)
    ahead = tuple(item for item in rivals if item.gap_to_user < 0)
    behind = tuple(item for item in rivals if item.gap_to_user > 0)
    leader_gap = min((item.gap_to_user for item in rivals), default=0)
    if leader_gap > 0:
        leader_gap = 0

    return RivalDecisionContext(
        user_team_id=int(user_team_id),
        user_rank=user_rank,
        user_total_points=user_total,
        nearest_rivals=tuple(nearest),
        nearest_ahead=tuple(ahead[:nearest_limit]),
        nearest_behind=tuple(behind[:nearest_limit]),
        leader_gap=leader_gap,
    )


def build_rival_snapshots_for_context(
    standings: Sequence[dict[str, Any]],
    user_team_id: int,
) -> list[RivalSnapshot]:
    """Local import wrapper keeps the public context builder compact."""
    from rival_engine import build_rival_snapshots

    return build_rival_snapshots(
        standings=list(standings),
        user_team_id=int(user_team_id),
    )


def build_dream_team_decision_context(
    *,
    season_to_date: DreamTeamSnapshot | None = None,
    season_gap: DreamTeamGap | None = None,
    gameweek_outcome: DreamTeamGap | None = None,
) -> DreamTeamDecisionContext:
    """Package Dream Team context without allowing future GW leakage."""

    if gameweek_outcome is not None and gameweek_outcome.gameweek is None:
        raise ValueError("Gameweek Dream Team outcome must contain a gameweek")
    if season_to_date is not None and season_to_date.scope != "season_to_date":
        raise ValueError("season_to_date must be a season-to-date Dream Team snapshot")
    if gameweek_outcome is not None and gameweek_outcome.scope != "gameweek":
        raise ValueError("gameweek_outcome must be a Gameweek Dream Team gap")

    return DreamTeamDecisionContext(
        season_to_date=season_to_date,
        season_gap=season_gap,
        gameweek_outcome=gameweek_outcome,
    )


def _top_captain(
    squad: Sequence[dict[str, Any]],
    projections: dict[int, dict[str, Any]],
    target_gameweek: int,
) -> tuple[CaptainCandidate, ...]:
    return tuple(
        rank_captain_candidates(
            squad=list(squad),
            projections=projections,
            max_candidates=len(squad),
            gameweek=int(target_gameweek),
        )
    )


def build_strategic_decision(
    *,
    manager_state: Any,
    market_players: list[dict[str, Any]],
    projections: dict[int, dict[str, Any]],
    horizon_gameweeks: Sequence[int],
    available_chips: Sequence[str] = (),
    chip_evaluations: Sequence[ChipScenarioEvaluation] = (),
    rival_context: RivalDecisionContext | None = None,
    dream_context: DreamTeamDecisionContext | None = None,
    fixture_count_by_gameweek: dict[int, int] | None = None,
) -> StrategicDecision:
    """Connect transfer, captain, chip, rival and Dream Team intelligence.

    The common comparison unit is projected points over the supplied horizon.
    Dream Team context is retained strictly as benchmark/learning context and
    is never used to select players, score options, or alter projected points.
    Transfer gains come from ``transfer_engine`` and chip gains from explicit
    counterfactual ``ChipScenarioEvaluation`` records. Captain selection is a
    target-GW decision attached to every option rather than double-counted as
    a second horizon projection.
    """

    del available_chips, fixture_count_by_gameweek  # reserved for next orchestration increment

    target_gameweek = int(horizon_gameweeks[0]) if horizon_gameweeks else int(manager_state.gameweek) + 1
    decision_gameweek = int(manager_state.gameweek)
    squad = list(manager_state.squad)

    transfers = tuple(
        generate_transfer_candidates(
            squad=squad,
            market=market_players,
            projections=projections,
            bank=float(manager_state.bank),
            free_transfers=int(manager_state.free_transfers),
        )
    )
    captains = _top_captain(squad, projections, target_gameweek)
    captaincy_horizon = build_captaincy_horizon(
        squad=squad,
        projections=projections,
        horizon_gameweeks=horizon_gameweeks or (target_gameweek,),
    )
    chips = tuple(chip_evaluations)

    baseline = sum(
        float(projections.get(int(player["id"]), {}).get("horizon_expected_points", 0.0))
        for player in squad
        if int(player.get("squad_position", 99)) <= 11
    )
    captain_id = captains[0].player_id if captains else None
    warnings: list[str] = []

    options: list[StrategicDecisionOption] = [
        StrategicDecisionOption(
            option_id="ROLL",
            option_type="roll",
            description="Keep the current squad and use the top captain candidate.",
            projected_horizon_points=baseline,
            incremental_horizon_points=0.0,
            captain_player_id=captain_id,
            data_complete=bool(squad) and bool(projections),
        )
    ]

    for candidate in transfers[:5]:
        options.append(
            StrategicDecisionOption(
                option_id=(
                    f"TRANSFER_{candidate.sell_player_id}_{candidate.buy_player_id}"
                ),
                option_type="transfer",
                description=(
                    f"Transfer {candidate.sell_name} to {candidate.buy_name}."
                ),
                projected_horizon_points=baseline + candidate.expected_gain,
                incremental_horizon_points=candidate.expected_gain,
                captain_player_id=captain_id,
                transfer=candidate,
                data_complete=candidate.data_complete,
                warnings=candidate.rationale if not candidate.data_complete else (),
            )
        )

    requested_start = int(horizon_gameweeks[0]) if horizon_gameweeks else None
    requested_end = int(horizon_gameweeks[-1]) if horizon_gameweeks else None

    for chip in chips:
        chip_warnings = list(chip.warnings)
        chip_complete = bool(chip.data_complete)
        if requested_start is not None and (
            chip.horizon_start_gameweek != requested_start
            or chip.horizon_end_gameweek != requested_end
        ):
            chip_complete = False
            chip_warnings.append(
                "Chip counterfactual horizon does not match the strategy horizon."
            )

        options.append(
            StrategicDecisionOption(
                option_id=(
                    f"CHIP_{chip.chip_instance_id}_GW{chip.target_gameweek}"
                ),
                option_type="chip",
                description=(
                    f"Use {chip.chip_instance_id} in GW{chip.target_gameweek}."
                ),
                projected_horizon_points=chip.chip_projected_points,
                incremental_horizon_points=chip.incremental_value,
                captain_player_id=captain_id,
                chip=chip,
                data_complete=chip_complete,
                warnings=tuple(dict.fromkeys(chip_warnings)),
            )
        )

    multi_gw_plan = evaluate_multi_gw_options(
        decision_gameweek=decision_gameweek,
        horizon_gameweeks=horizon_gameweeks or (target_gameweek,),
        options=options,
        projections=projections,
        free_transfers_before=int(manager_state.free_transfers),
        captaincy_context=captaincy_horizon,
    )
    selected_option_id = multi_gw_plan.selected_option_id
    selected = next(
        (item for item in options if item.option_id == selected_option_id),
        None,
    )

    if selected is None:
        warnings.append("No complete strategic option was available for selection.")
    if not captains:
        warnings.append("No target-Gameweek captain candidate was available.")
    if captaincy_horizon.warnings:
        warnings.extend(captaincy_horizon.warnings)
    if not projections:
        warnings.append("No projections were supplied.")

    data_complete = bool(selected is not None and not warnings)

    return StrategicDecision(
        decision_gameweek=decision_gameweek,
        target_gameweek=target_gameweek,
        selected_option=selected,
        options=tuple(options),
        transfer_candidates=transfers,
        captain_candidates=captains,
        captaincy_horizon=captaincy_horizon,
        chip_opportunities=chips,
        multi_gw_plan=multi_gw_plan,
        rival_context=rival_context,
        dream_context=dream_context,
        data_complete=data_complete,
        warnings=tuple(dict.fromkeys(warnings)),
        dream_team_selection_policy=DREAM_TEAM_SELECTION_POLICY,
    )

def build_strategic_decision_from_production_projection(
    *,
    manager_state: Any,
    market_players: list[dict[str, Any]],
    projection_result: ProductionProjectionResult,
    available_chips: Sequence[str] = (),
    chip_evaluations: Sequence[ChipScenarioEvaluation] = (),
    rival_context: RivalDecisionContext | None = None,
    dream_context: DreamTeamDecisionContext | None = None,
    fixture_count_by_gameweek: dict[int, int] | None = None,
) -> StrategicDecision:
    """Build a strategic decision from the authoritative 18A projection result.

    This is the production-facing adapter for Batch 18A -> 18B. It keeps
    ``build_strategic_decision`` backward-compatible while making the
    production projection contract explicit at the orchestrator boundary.
    The adapter validates that the projection horizon is exactly the horizon
    being evaluated and propagates projection completeness/warnings into the
    final decision.
    """

    if not isinstance(projection_result, ProductionProjectionResult):
        raise TypeError(
            "projection_result must be a ProductionProjectionResult."
        )

    horizon = tuple(int(gameweek) for gameweek in projection_result.horizon_gameweeks)
    if not horizon:
        raise ValueError("projection_result must contain at least one Gameweek.")

    target_gameweek = int(projection_result.target_gameweek)
    if horizon[0] != target_gameweek:
        raise ValueError(
            "Projection result horizon must start at its target Gameweek."
        )

    decision = build_strategic_decision(
        manager_state=manager_state,
        market_players=market_players,
        projections=projection_result.projections,
        horizon_gameweeks=horizon,
        available_chips=available_chips,
        chip_evaluations=chip_evaluations,
        rival_context=rival_context,
        dream_context=dream_context,
        fixture_count_by_gameweek=fixture_count_by_gameweek,
    )

    projection_warnings = tuple(projection_result.warnings)
    warnings = tuple(dict.fromkeys(decision.warnings + projection_warnings))

    return StrategicDecision(
        decision_gameweek=decision.decision_gameweek,
        target_gameweek=decision.target_gameweek,
        selected_option=decision.selected_option,
        options=decision.options,
        transfer_candidates=decision.transfer_candidates,
        captain_candidates=decision.captain_candidates,
        captaincy_horizon=decision.captaincy_horizon,
        chip_opportunities=decision.chip_opportunities,
        multi_gw_plan=decision.multi_gw_plan,
        rival_context=decision.rival_context,
        dream_context=decision.dream_context,
        data_complete=bool(decision.data_complete and projection_result.data_complete),
        warnings=warnings,
        dream_team_selection_policy=decision.dream_team_selection_policy,
        engine_version=PRODUCTION_PROJECTION_ENGINE_VERSION,
        projection_model_version=projection_result.model_version,
    )
