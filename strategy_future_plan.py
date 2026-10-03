"""
strategy_future_plan.py

Batch 18D-E1 - conditional future strategy plan contract.

This module converts the selected strategy scenario into an explicit plan for
what is known now and what must be reassessed later. It does not predict or
commit future transfers. Future actions remain conditional on refreshed
manager state, availability, fixtures and projections.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

from strategy_scenario import StrategyAction, StrategyDecisionPoint, StrategyScenario
from strategy_selection import StrategySelection


MODEL_VERSION = "strategy_future_plan_v1"
PLAN_BASIS = "SELECTED_SCENARIO_WITH_CONDITIONAL_REASSESSMENT"


@dataclass(frozen=True)
class ConditionalDecisionRule:
    """A future reassessment rule without asserting a future action."""

    gameweek: int
    triggers: tuple[str, ...]
    action_type: str = "reassess"
    required_inputs: tuple[str, ...] = (
        "manager_state",
        "player_availability",
        "fixture_state",
        "refreshed_projections",
    )
    future_action_committed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConditionalStrategyPlan:
    """Production-facing plan for the selected strategy path."""

    selected_scenario_id: str
    decision_gameweek: int
    target_gameweek: int
    horizon_gameweeks: tuple[int, ...]
    initial_action: StrategyAction
    future_decision_points: tuple[StrategyDecisionPoint, ...]
    conditional_rules: tuple[ConditionalDecisionRule, ...]
    hit_cost: float
    remaining_transfer_flexibility: int
    future_actions_committed: bool
    data_complete: bool
    plan_basis: str = PLAN_BASIS
    model_version: str = MODEL_VERSION
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _rules_from_points(
    points: Sequence[StrategyDecisionPoint],
) -> tuple[ConditionalDecisionRule, ...]:
    return tuple(
        ConditionalDecisionRule(
            gameweek=point.gameweek,
            triggers=tuple(point.triggers),
            action_type=point.action.action_type,
        )
        for point in points
        if point.is_reassessment
    )


def build_conditional_strategy_plan(
    *,
    selection: StrategySelection,
    scenarios: Sequence[StrategyScenario],
) -> ConditionalStrategyPlan | None:
    """Build a conditional plan for the scenario selected by D2.

    Returns ``None`` when the selection has no selected scenario. This keeps
    incomplete/no-solution states explicit rather than inventing a fallback.
    """

    selected_id = selection.selected_scenario_id
    if selected_id is None:
        return None

    matches = [scenario for scenario in scenarios if scenario.scenario_id == selected_id]
    if not matches:
        raise ValueError(
            f"Selected scenario '{selected_id}' was not supplied to the future-plan builder."
        )
    if len(matches) > 1:
        raise ValueError(f"Scenario '{selected_id}' appears more than once.")

    scenario = matches[0]
    future_points = scenario.future_decision_points
    rules = _rules_from_points(future_points)
    warnings = list(selection.warnings)
    warnings.extend(scenario.warnings)

    if not future_points and len(scenario.horizon_gameweeks) > 1:
        warnings.append(
            "The scenario horizon extends beyond the target Gameweek but contains no future reassessment point."
        )

    data_complete = bool(selection.data_complete and scenario.data_complete)

    return ConditionalStrategyPlan(
        selected_scenario_id=scenario.scenario_id,
        decision_gameweek=scenario.decision_gameweek,
        target_gameweek=scenario.target_gameweek,
        horizon_gameweeks=scenario.horizon_gameweeks,
        initial_action=scenario.initial_action,
        future_decision_points=future_points,
        conditional_rules=rules,
        hit_cost=scenario.hit_cost,
        remaining_transfer_flexibility=scenario.remaining_transfer_flexibility,
        future_actions_committed=False,
        data_complete=data_complete,
        warnings=tuple(dict.fromkeys(warnings)),
    )
