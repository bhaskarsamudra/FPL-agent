"""
multi_gw_strategy.py

Bounded multi-Gameweek strategic decision framework.

Captaincy is part of the common horizon evaluation. The captain engine remains
the single source of captaincy intelligence; this module only incorporates its
point-in-time output into option scoring.

Dream Team data is deliberately absent. The Strategist must make an
independent decision before the Gameweek; Dream Team data belongs to
post-Gameweek evaluation and learning.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

from captain_engine import CaptaincyHorizonContext


ENGINE_VERSION = "multi_gw_strategy_v1_1"


@dataclass(frozen=True)
class MultiGWOptionEvaluation:
    """Evaluation of one strategic option over the complete horizon."""

    option_id: str
    option_type: str
    horizon_start_gameweek: int
    horizon_end_gameweek: int
    projected_horizon_points: float
    projected_first_gameweek_points: float
    captaincy_projected_points: float
    projected_total_points: float
    transfer_hit_cost: float
    retained_free_transfer_value: float
    strategic_score: float
    opportunity_cost: float
    data_complete: bool
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MultiGWStrategicPlan:
    """Bounded multi-Gameweek comparison of the available strategy options."""

    decision_gameweek: int
    horizon_gameweeks: tuple[int, ...]
    selected_option_id: str | None
    options: tuple[MultiGWOptionEvaluation, ...]
    captaincy_context: CaptaincyHorizonContext | None = None
    engine_version: str = ENGINE_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _first_gameweek_points(
    *,
    option: Any,
    projections: dict[int, dict[str, Any]],
    horizon_start: int,
) -> float:
    """Return the option's first-GW projection without fabricating data."""

    if getattr(option, "option_type", None) == "transfer":
        transfer = getattr(option, "transfer", None)
        if transfer is not None:
            buy_id = int(transfer.buy_player_id)
            sell_id = int(transfer.sell_player_id)
            buy_row = projections.get(buy_id, {})
            sell_row = projections.get(sell_id, {})
            return _player_gw_points(buy_row, horizon_start) - _player_gw_points(
                sell_row, horizon_start
            )

    return _number(getattr(option, "projected_first_gameweek_points", 0.0))


def _player_gw_points(row: dict[str, Any], gameweek: int) -> float:
    fixtures = row.get("fixtures") or ()
    total = 0.0
    found = False
    for fixture in fixtures:
        if int(fixture.get("gameweek", -1)) != int(gameweek):
            continue
        found = True
        total += _number(fixture.get("expected_points"))
    return total if found else 0.0


def _captaincy_points(
    *,
    option: Any,
    captaincy_context: CaptaincyHorizonContext | None,
    horizon_gameweeks: Sequence[int],
) -> tuple[float, tuple[str, ...]]:
    """Return normal captain bonus supplied by the captain engine.

    Chip counterfactuals are already scenario-evaluated and therefore include
    their own captain mechanics. Triple Captain must never receive a second
    captain bonus here.
    """
    if captaincy_context is None or getattr(option, "option_type", None) == "chip":
        return 0.0, ()

    total = 0.0
    warnings: list[str] = []
    for gameweek in horizon_gameweeks:
        opportunity = captaincy_context.for_gameweek(gameweek)
        if opportunity is None or opportunity.best_player_id is None:
            warnings.append(f"No captaincy context is available for GW{gameweek}.")
            continue
        total += opportunity.best_expected_points * (
            captaincy_context.captain_multiplier - 1.0
        )
        if not opportunity.data_complete:
            warnings.extend(opportunity.warnings)

    return total, tuple(dict.fromkeys(warnings))


def evaluate_multi_gw_options(
    *,
    decision_gameweek: int,
    horizon_gameweeks: Sequence[int],
    options: Sequence[Any],
    projections: dict[int, dict[str, Any]],
    free_transfers_before: int,
    transfer_hit_points: float = 4.0,
    retained_ft_value: float = 0.5,
    captaincy_context: CaptaincyHorizonContext | None = None,
) -> MultiGWStrategicPlan:
    """Evaluate bounded strategic options on one common multi-GW horizon.

    ``captaincy_context`` comes directly from ``captain_engine``. It adds the
    normal captain multiplier bonus to non-chip options. Chip counterfactuals
    already contain their own captain mechanics and are therefore not adjusted
    again.
    """

    horizon = tuple(int(gw) for gw in horizon_gameweeks)
    if not horizon:
        raise ValueError("At least one future Gameweek is required.")
    if any(horizon[index] >= horizon[index + 1] for index in range(len(horizon) - 1)):
        raise ValueError("Horizon Gameweeks must be strictly increasing.")

    evaluated: list[MultiGWOptionEvaluation] = []
    first_gw = horizon[0]
    last_gw = horizon[-1]

    for option in options:
        option_id = str(option.option_id)
        option_type = str(option.option_type)
        warnings = list(getattr(option, "warnings", ()) or ())
        complete = bool(getattr(option, "data_complete", False))

        projected = _number(getattr(option, "projected_horizon_points", 0.0))
        first_points = _first_gameweek_points(
            option=option,
            projections=projections,
            horizon_start=first_gw,
        )

        captain_points, captain_warnings = _captaincy_points(
            option=option,
            captaincy_context=captaincy_context,
            horizon_gameweeks=horizon,
        )
        warnings.extend(captain_warnings)

        transfer_hit = 0.0
        if option_type == "transfer" and free_transfers_before < 1:
            transfer_hit = transfer_hit_points
            warnings.append(
                f"No free transfer available; a {transfer_hit_points:.1f}-point hit applies."
            )

        flexibility = retained_ft_value if option_type == "roll" else 0.0
        projected_total = projected + captain_points
        strategic_score = projected_total - transfer_hit + flexibility

        evaluated.append(
            MultiGWOptionEvaluation(
                option_id=option_id,
                option_type=option_type,
                horizon_start_gameweek=first_gw,
                horizon_end_gameweek=last_gw,
                projected_horizon_points=projected,
                projected_first_gameweek_points=first_points,
                captaincy_projected_points=captain_points,
                projected_total_points=projected_total,
                transfer_hit_cost=transfer_hit,
                retained_free_transfer_value=flexibility,
                strategic_score=strategic_score,
                opportunity_cost=0.0,
                data_complete=complete and not warnings,
                warnings=tuple(dict.fromkeys(warnings)),
            )
        )

    complete_options = [row for row in evaluated if row.data_complete]
    best_score = max((row.strategic_score for row in complete_options), default=None)
    selected_id = None

    if best_score is not None:
        selected = max(
            complete_options,
            key=lambda row: (
                row.strategic_score,
                row.projected_total_points,
                row.option_id,
            ),
        )
        selected_id = selected.option_id

    final: list[MultiGWOptionEvaluation] = []
    for row in evaluated:
        opportunity = (
            max(0.0, best_score - row.strategic_score)
            if row.data_complete and best_score is not None
            else 0.0
        )
        final.append(
            MultiGWOptionEvaluation(
                option_id=row.option_id,
                option_type=row.option_type,
                horizon_start_gameweek=row.horizon_start_gameweek,
                horizon_end_gameweek=row.horizon_end_gameweek,
                projected_horizon_points=row.projected_horizon_points,
                projected_first_gameweek_points=row.projected_first_gameweek_points,
                captaincy_projected_points=row.captaincy_projected_points,
                projected_total_points=row.projected_total_points,
                transfer_hit_cost=row.transfer_hit_cost,
                retained_free_transfer_value=row.retained_free_transfer_value,
                strategic_score=row.strategic_score,
                opportunity_cost=opportunity,
                data_complete=row.data_complete,
                warnings=row.warnings,
            )
        )

    return MultiGWStrategicPlan(
        decision_gameweek=int(decision_gameweek),
        horizon_gameweeks=horizon,
        selected_option_id=selected_id,
        options=tuple(final),
        captaincy_context=captaincy_context,
    )
