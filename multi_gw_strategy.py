"""
multi_gw_strategy.py

Batch 16 multi-Gameweek strategic decision framework.

This module evaluates a bounded set of already-generated strategic options
across a common future horizon. It does not generate every possible squad or
chip combination. Its purpose is to make the trade-offs explicit:

- projected points over the full horizon;
- immediate Gameweek contribution;
- transfer cost / hit cost;
- retained free-transfer flexibility;
- opportunity cost versus the strongest alternative.

Dream Team data is deliberately absent from this module. The Strategist must
make an independent decision before the Gameweek; Dream Team data belongs to
post-Gameweek evaluation and learning.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence


ENGINE_VERSION = "multi_gw_strategy_v1_0"


@dataclass(frozen=True)
class MultiGWOptionEvaluation:
    """Evaluation of one strategic option over the complete horizon."""

    option_id: str
    option_type: str
    horizon_start_gameweek: int
    horizon_end_gameweek: int
    projected_horizon_points: float
    projected_first_gameweek_points: float
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

    # Roll/chip options already carry a complete horizon projection. For the
    # first GW, use an explicit fixture-level projection when available.
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


def evaluate_multi_gw_options(
    *,
    decision_gameweek: int,
    horizon_gameweeks: Sequence[int],
    options: Sequence[Any],
    projections: dict[int, dict[str, Any]],
    free_transfers_before: int,
    transfer_hit_points: float = 4.0,
    retained_ft_value: float = 0.5,
) -> MultiGWStrategicPlan:
    """Evaluate bounded strategic options on one common multi-GW horizon.

    ``retained_ft_value`` is deliberately a small transparent heuristic, not a
    learned probability. It represents the value of preserving one future
    transfer opportunity when rolling instead of using a transfer now.
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

        transfer_hit = 0.0
        if option_type == "transfer" and free_transfers_before < 1:
            transfer_hit = transfer_hit_points
            warnings.append(
                f"No free transfer available; a {transfer_hit_points:.1f}-point hit applies."
            )

        # A normal transfer consumes this week's transfer opportunity. Rolling
        # preserves it. Chip usage does not automatically imply that a future
        # free transfer is lost, so only roll receives the explicit flexibility
        # credit here.
        flexibility = retained_ft_value if option_type == "roll" else 0.0

        strategic_score = projected - transfer_hit + flexibility

        evaluated.append(
            MultiGWOptionEvaluation(
                option_id=option_id,
                option_type=option_type,
                horizon_start_gameweek=first_gw,
                horizon_end_gameweek=last_gw,
                projected_horizon_points=projected,
                projected_first_gameweek_points=first_points,
                transfer_hit_cost=transfer_hit,
                retained_free_transfer_value=flexibility,
                strategic_score=strategic_score,
                opportunity_cost=0.0,
                data_complete=complete and not warnings,
                warnings=tuple(dict.fromkeys(warnings)),
            )
        )

    complete = [row for row in evaluated if row.data_complete]
    best_score = max((row.strategic_score for row in complete), default=None)
    selected_id = None

    if best_score is not None:
        selected = max(
            complete,
            key=lambda row: (row.strategic_score, row.projected_horizon_points, row.option_id),
        )
        selected_id = selected.option_id

    # Opportunity cost is measured only against other complete options on the
    # same horizon. This makes the trade-off auditable without inventing a
    # counterfactual outside the bounded candidate set.
    final: list[MultiGWOptionEvaluation] = []
    for row in evaluated:
        if row.data_complete and best_score is not None:
            opportunity = max(0.0, best_score - row.strategic_score)
        else:
            opportunity = 0.0
        final.append(
            MultiGWOptionEvaluation(
                option_id=row.option_id,
                option_type=row.option_type,
                horizon_start_gameweek=row.horizon_start_gameweek,
                horizon_end_gameweek=row.horizon_end_gameweek,
                projected_horizon_points=row.projected_horizon_points,
                projected_first_gameweek_points=row.projected_first_gameweek_points,
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
    )
