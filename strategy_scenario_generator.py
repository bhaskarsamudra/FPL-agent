"""
strategy_scenario_generator.py

Batch 18D - feasible strategy-path generation.

The generator creates auditable candidate strategy paths from *known current*
options. It does not invent future transfers. Future Gameweeks are represented
as conditional reassessment points, because prices, availability, team news
and future manager state are not known at the decision timestamp.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from strategy_scenario import (
    MODEL_VERSION,
    StrategyAction,
    StrategyDecisionPoint,
    StrategyScenario,
)


REASSESSMENT_TRIGGERS = (
    "availability_change",
    "starting_probability_change",
    "fixture_change",
    "new_projection_information",
)


@dataclass(frozen=True)
class StrategyScenarioGenerationResult:
    """Output contract for strategy-path generation."""

    scenarios: tuple[StrategyScenario, ...]
    data_complete: bool
    warnings: tuple[str, ...] = ()
    model_version: str = MODEL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenarios": tuple(item.to_dict() for item in self.scenarios),
            "data_complete": self.data_complete,
            "warnings": self.warnings,
            "model_version": self.model_version,
        }


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _initial_action(option: Any) -> StrategyAction:
    option_type = str(getattr(option, "option_type", "unknown"))
    transfer = getattr(option, "transfer", None)
    chip = getattr(option, "chip", None)
    warnings = tuple(str(item) for item in (getattr(option, "warnings", ()) or ()))
    complete = bool(getattr(option, "data_complete", False))

    if transfer is not None:
        return StrategyAction(
            action_type="transfer",
            description=str(getattr(option, "description", "Execute transfer.")),
            sell_player_id=int(transfer.sell_player_id),
            buy_player_id=int(transfer.buy_player_id),
            transfer_cost=max(0.0, _number(transfer.net_cost)),
            data_complete=complete,
            warnings=warnings,
        )

    if chip is not None:
        chip_name = str(getattr(chip, "chip_instance_id", getattr(chip, "chip", "unknown")))
        return StrategyAction(
            action_type="chip",
            description=str(getattr(option, "description", f"Use {chip_name}.")),
            chip=chip_name,
            data_complete=complete,
            warnings=warnings,
        )

    return StrategyAction(
        action_type=option_type,
        description=str(getattr(option, "description", option_type.title())),
        data_complete=complete,
        warnings=warnings,
    )


def _reassessment_point(gameweek: int) -> StrategyDecisionPoint:
    return StrategyDecisionPoint(
        gameweek=int(gameweek),
        action=StrategyAction(
            action_type="reassess",
            description=(
                "Reassess the strategy using the manager state, availability, "
                "fixtures and refreshed projections available at this Gameweek."
            ),
            data_complete=True,
        ),
        is_reassessment=True,
        triggers=REASSESSMENT_TRIGGERS,
    )



def generate_strategy_scenarios_from_options(
    *,
    decision_gameweek: int,
    target_gameweek: int,
    horizon_gameweeks: Sequence[int],
    options: Sequence[Any],
    free_transfers_before: int,
    max_scenarios: int = 10,
    allowed_option_types: Sequence[str] = ("roll", "transfer"),
) -> StrategyScenarioGenerationResult:
    """Generate strategy paths from already-validated orchestrator options.

    The orchestrator remains the owner of transfer/chip feasibility. This
    adapter only converts the existing bounded options into strategy paths and
    deliberately excludes option types that do not yet have a safe future
    state-transition model.
    """
    allowed = {str(item) for item in allowed_option_types}
    selected = [
        option
        for option in options
        if str(getattr(option, "option_type", "")) in allowed
    ]
    return generate_strategy_scenarios(
        decision_gameweek=decision_gameweek,
        target_gameweek=target_gameweek,
        horizon_gameweeks=horizon_gameweeks,
        options=selected,
        free_transfers_before=free_transfers_before,
        max_scenarios=max_scenarios,
    )

def generate_strategy_scenarios(
    *,
    decision_gameweek: int,
    target_gameweek: int,
    horizon_gameweeks: Sequence[int],
    options: Sequence[Any],
    free_transfers_before: int,
    max_scenarios: int = 10,
) -> StrategyScenarioGenerationResult:
    """Generate feasible strategy paths from current strategic alternatives.

    Each option becomes one candidate path. The target Gameweek action is
    known now; later Gameweeks become explicit reassessment points. This is a
    deliberate point-in-time boundary and is not a prediction of future
    transfers.
    """

    decision_gw = int(decision_gameweek)
    target_gw = int(target_gameweek)
    horizon = tuple(int(gw) for gw in horizon_gameweeks)

    if decision_gw < 1:
        raise ValueError("decision_gameweek must be positive.")
    if target_gw < 1:
        raise ValueError("target_gameweek must be positive.")
    if not horizon:
        raise ValueError("horizon_gameweeks must not be empty.")
    if horizon[0] != target_gw:
        raise ValueError("horizon_gameweeks must start at target_gameweek.")
    if tuple(sorted(horizon)) != horizon:
        raise ValueError("horizon_gameweeks must be in ascending order.")
    if int(max_scenarios) < 1:
        raise ValueError("max_scenarios must be positive.")

    scenarios: list[StrategyScenario] = []
    warnings: list[str] = []

    for option in options:
        if len(scenarios) >= int(max_scenarios):
            break

        action = _initial_action(option)
        transfer_used = 1 if action.action_type == "transfer" else 0
        hit_taken = 0
        hit_cost = 0.0
        if transfer_used > int(free_transfers_before):
            hit_taken = 1
            hit_cost = 4.0

        points = [
            StrategyDecisionPoint(
                gameweek=target_gw,
                action=action,
                is_reassessment=False,
            )
        ]
        points.extend(_reassessment_point(gw) for gw in horizon if gw > target_gw)

        remaining_flexibility = max(
            0,
            int(free_transfers_before) - transfer_used,
        )

        scenario_warnings = list(action.warnings)
        if hit_taken:
            scenario_warnings.append(
                "The initial transfer exceeds available free transfers and implies a 4-point hit."
            )

        scenario_complete = bool(action.data_complete)
        scenario_id = f"SCENARIO_GW{target_gw}_{getattr(option, 'option_id', action.action_type)}"
        scenarios.append(
            StrategyScenario(
                scenario_id=str(scenario_id),
                description=(
                    f"{action.description} with future reassessment points across "
                    f"the supplied planning horizon."
                ),
                source_option_id=str(getattr(option, "option_id", action.action_type)),
                decision_gameweek=decision_gw,
                target_gameweek=target_gw,
                horizon_gameweeks=horizon,
                decision_points=tuple(points),
                free_transfers_consumed=transfer_used,
                hits_taken=hit_taken,
                hit_cost=hit_cost,
                remaining_transfer_flexibility=remaining_flexibility,
                data_complete=scenario_complete,
                warnings=tuple(dict.fromkeys(scenario_warnings)),
            )
        )

    if not scenarios:
        warnings.append("No current strategic options were supplied for scenario generation.")

    return StrategyScenarioGenerationResult(
        scenarios=tuple(scenarios),
        data_complete=bool(scenarios) and all(item.data_complete for item in scenarios),
        warnings=tuple(dict.fromkeys(warnings)),
    )
