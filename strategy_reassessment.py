"""
strategy_reassessment.py

Batch 18D-E2 - conditional multi-GW strategy reassessment/execution contract.

This module resolves what the strategist should do at a decision point using a
previously selected ConditionalStrategyPlan and the information available at
that point in time. It deliberately does not invent future transfers.

At the target Gameweek the plan exposes the known initial action. At a future
reassessment Gameweek, the engine either keeps the current strategy when no
material trigger is present, or requests a fresh strategic-option generation
when a trigger is present. If required inputs are incomplete, it refuses to
produce a new strategic action.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

from strategy_future_plan import ConditionalStrategyPlan


MODEL_VERSION = "strategy_reassessment_v1"

EXECUTE_INITIAL_ACTION = "EXECUTE_INITIAL_ACTION"
HOLD_CURRENT_STRATEGY = "HOLD_CURRENT_STRATEGY"
REASSESS_AND_REGENERATE = "REASSESS_AND_REGENERATE"
NO_ACTION_DATA_INCOMPLETE = "NO_ACTION_DATA_INCOMPLETE"
NO_ACTION_NO_REASSESSMENT_POINT = "NO_ACTION_NO_REASSESSMENT_POINT"

REQUIRED_REASSESSMENT_INPUTS = (
    "manager_state",
    "player_availability",
    "fixture_state",
    "refreshed_projections",
)


@dataclass(frozen=True)
class StrategyReassessmentContext:
    """Point-in-time inputs available when a strategy is reassessed."""

    gameweek: int
    observed_triggers: tuple[str, ...] = ()
    available_inputs: tuple[str, ...] = REQUIRED_REASSESSMENT_INPUTS
    data_complete: bool = True
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StrategyReassessmentDecision:
    """Auditable action resolved from the selected conditional plan."""

    gameweek: int
    decision_type: str
    selected_scenario_id: str
    action_description: str
    triggered_rules: tuple[str, ...]
    required_inputs: tuple[str, ...]
    data_complete: bool
    future_action_committed: bool = False
    model_version: str = MODEL_VERSION
    rationale: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values))


def _reassessment_rule_for_gameweek(
    plan: ConditionalStrategyPlan,
    gameweek: int,
):
    return next(
        (
            rule
            for rule in plan.conditional_rules
            if rule.gameweek == int(gameweek)
        ),
        None,
    )


def resolve_strategy_step(
    *,
    plan: ConditionalStrategyPlan,
    context: StrategyReassessmentContext,
) -> StrategyReassessmentDecision:
    """Resolve the current strategy step without predicting future actions.

    Rules:
    * At the target Gameweek, expose the already-selected initial action.
    * At a future reassessment point, incomplete required inputs block action.
    * Material triggers request fresh strategic-option generation.
    * No material trigger means hold the current strategy.
    * A future transfer/chip is never committed by this function.
    """

    gameweek = int(context.gameweek)
    warnings = list(plan.warnings)
    warnings.extend(context.warnings)

    if not context.data_complete:
        return StrategyReassessmentDecision(
            gameweek=gameweek,
            decision_type=NO_ACTION_DATA_INCOMPLETE,
            selected_scenario_id=plan.selected_scenario_id,
            action_description="Do not issue a new strategic action until required data is complete.",
            triggered_rules=(),
            required_inputs=REQUIRED_REASSESSMENT_INPUTS,
            data_complete=False,
            rationale=(
                "Required point-in-time inputs are incomplete; the NO DATA = NO ANSWER rule blocks a new action.",
            ),
            warnings=_unique(warnings),
        )

    if gameweek == plan.target_gameweek:
        action = plan.initial_action
        action_warnings = list(action.warnings)
        return StrategyReassessmentDecision(
            gameweek=gameweek,
            decision_type=EXECUTE_INITIAL_ACTION,
            selected_scenario_id=plan.selected_scenario_id,
            action_description=action.description,
            triggered_rules=(),
            required_inputs=(),
            data_complete=bool(plan.data_complete and action.data_complete),
            future_action_committed=False,
            rationale=(
                "This is the target Gameweek action selected from the current point-in-time strategy evaluation.",
            ),
            warnings=_unique((*warnings, *action_warnings)),
        )

    if gameweek < plan.target_gameweek:
        return StrategyReassessmentDecision(
            gameweek=gameweek,
            decision_type=NO_ACTION_NO_REASSESSMENT_POINT,
            selected_scenario_id=plan.selected_scenario_id,
            action_description="The target Gameweek has not been reached; no future action is resolved here.",
            triggered_rules=(),
            required_inputs=(),
            data_complete=plan.data_complete,
            rationale=("The selected strategy remains pending its target Gameweek decision point.",),
            warnings=_unique(warnings),
        )

    rule = _reassessment_rule_for_gameweek(plan, gameweek)
    if rule is None:
        return StrategyReassessmentDecision(
            gameweek=gameweek,
            decision_type=NO_ACTION_NO_REASSESSMENT_POINT,
            selected_scenario_id=plan.selected_scenario_id,
            action_description="No reassessment point is defined for this Gameweek.",
            triggered_rules=(),
            required_inputs=(),
            data_complete=plan.data_complete,
            rationale=(
                "No future decision point exists for this Gameweek, so no future action is invented.",
            ),
            warnings=_unique(warnings),
        )

    required = tuple(rule.required_inputs)
    available = set(context.available_inputs)
    missing = tuple(item for item in required if item not in available)
    if missing:
        return StrategyReassessmentDecision(
            gameweek=gameweek,
            decision_type=NO_ACTION_DATA_INCOMPLETE,
            selected_scenario_id=plan.selected_scenario_id,
            action_description="Do not generate a future strategic action until reassessment inputs are complete.",
            triggered_rules=(),
            required_inputs=missing,
            data_complete=False,
            rationale=(
                "The reassessment point was reached, but one or more required inputs are unavailable.",
            ),
            warnings=_unique((*warnings, f"Missing reassessment inputs: {', '.join(missing)}.")),
        )

    observed = set(context.observed_triggers)
    matched = tuple(trigger for trigger in rule.triggers if trigger in observed)
    if matched:
        return StrategyReassessmentDecision(
            gameweek=gameweek,
            decision_type=REASSESS_AND_REGENERATE,
            selected_scenario_id=plan.selected_scenario_id,
            action_description=(
                "Regenerate strategic options from the refreshed point-in-time state; no future player move is committed in advance."
            ),
            triggered_rules=matched,
            required_inputs=required,
            data_complete=True,
            future_action_committed=False,
            rationale=(
                f"Material reassessment trigger(s) detected: {', '.join(matched)}.",
                "A fresh strategy evaluation is required because the current scenario may no longer represent the best decision.",
            ),
            warnings=_unique(warnings),
        )

    return StrategyReassessmentDecision(
        gameweek=gameweek,
        decision_type=HOLD_CURRENT_STRATEGY,
        selected_scenario_id=plan.selected_scenario_id,
        action_description="Hold the selected strategy and reassess again at the next defined decision point.",
        triggered_rules=(),
        required_inputs=required,
        data_complete=True,
        future_action_committed=False,
        rationale=(
            "No configured material reassessment trigger is present at this Gameweek.",
            "The current strategy is retained without inventing a future transfer or chip action.",
        ),
        warnings=_unique(warnings),
    )
