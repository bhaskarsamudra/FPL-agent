"""
strategy_scenario_evaluator.py

Batch 18D-C - scenario-aware cross-horizon reconciliation.

This module connects the first-class StrategyScenario objects introduced in
18D-A/B to the existing Batch 18C cross-horizon scoring engine. It does not
recalculate projected points. Instead, it maps each generated scenario to the
already-evaluated strategic option and exposes the same target/3/5/8-GW
results using scenario IDs, flexibility and explicit trade-offs.

Future transfer sequences remain conditional reassessment points. A scenario
is therefore evaluated on the current action plus the information currently
available; it is not treated as a known future transfer path.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

from strategy_scenario import StrategyScenario
from strategy_scenario_engine import (
    CrossHorizonStrategyPlan,
    CrossHorizonStrategyOption,
    HorizonStrategyScore,
    SELECTION_BASIS,
)


MODEL_VERSION = "strategy_scenario_reconciliation_v1"


@dataclass(frozen=True)
class StrategyScenarioHorizonTradeoff:
    """Scenario-level view of one horizon's existing strategic score."""

    horizon_name: str
    gameweeks: tuple[int, ...]
    strategic_score: float
    projected_points: float
    captaincy_points: float
    transfer_hit_cost: float
    data_complete: bool
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StrategyScenarioEvaluation:
    """One generated strategy scenario reconciled to all horizon scores."""

    scenario_id: str
    source_option_id: str
    initial_action_type: str
    remaining_transfer_flexibility: int
    hit_cost: float
    horizon_scores: tuple[StrategyScenarioHorizonTradeoff, ...]
    target_to_long_delta: float | None
    data_complete: bool
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def score_for(self, horizon_name: str) -> StrategyScenarioHorizonTradeoff | None:
        return next(
            (score for score in self.horizon_scores if score.horizon_name == horizon_name),
            None,
        )


@dataclass(frozen=True)
class StrategyScenarioEvaluationPlan:
    """Scenario-aware reconciliation across target/3/5/8-GW lenses."""

    decision_gameweek: int
    target_gameweek: int
    horizons: tuple[tuple[str, tuple[int, ...]], ...]
    horizon_winners: tuple[tuple[str, str | None], ...]
    selected_scenario_id: str | None
    reconciliation: str
    rationale: tuple[str, ...]
    evaluations: tuple[StrategyScenarioEvaluation, ...]
    data_complete: bool
    warnings: tuple[str, ...] = ()
    model_version: str = MODEL_VERSION
    selection_basis: str = SELECTION_BASIS

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def winner_for(self, horizon_name: str) -> str | None:
        return dict(self.horizon_winners).get(horizon_name)

    def evaluation_for(self, scenario_id: str) -> StrategyScenarioEvaluation | None:
        return next(
            (item for item in self.evaluations if item.scenario_id == scenario_id),
            None,
        )


def _tradeoff_from_score(score: HorizonStrategyScore) -> StrategyScenarioHorizonTradeoff:
    return StrategyScenarioHorizonTradeoff(
        horizon_name=score.horizon_name,
        gameweeks=score.gameweeks,
        strategic_score=score.strategic_score,
        projected_points=score.projected_points,
        captaincy_points=score.captaincy_points,
        transfer_hit_cost=score.transfer_hit_cost,
        data_complete=score.data_complete,
        warnings=score.warnings,
    )


def _find_source_option(
    scenario: StrategyScenario,
    cross_horizon_plan: CrossHorizonStrategyPlan,
) -> CrossHorizonStrategyOption | None:
    source_option_id = scenario.source_option_id
    if source_option_id is not None:
        return next(
            (
                option
                for option in cross_horizon_plan.options
                if option.option_id == source_option_id
            ),
            None,
        )

    # Backward-compatible fallback for scenarios created by the 18D-A/B model
    # before source_option_id became explicit.
    prefix = f"SCENARIO_GW{scenario.target_gameweek}_"
    if scenario.scenario_id.startswith(prefix):
        candidate = scenario.scenario_id[len(prefix):]
        return next(
            (option for option in cross_horizon_plan.options if option.option_id == candidate),
            None,
        )
    return None


def _winner_for(
    evaluations: Sequence[StrategyScenarioEvaluation],
    horizon_name: str,
) -> str | None:
    complete = [
        item
        for item in evaluations
        if (score := item.score_for(horizon_name)) is not None and score.data_complete
    ]
    if not complete:
        return None
    return max(
        complete,
        key=lambda item: (
            item.score_for(horizon_name).strategic_score,  # type: ignore[union-attr]
            item.scenario_id,
        ),
    ).scenario_id


def evaluate_strategy_scenarios(
    *,
    scenarios: Sequence[StrategyScenario],
    cross_horizon_plan: CrossHorizonStrategyPlan,
) -> StrategyScenarioEvaluationPlan:
    """Reconcile generated scenarios with the authoritative 18C scores.

    The function deliberately consumes ``CrossHorizonStrategyPlan`` rather
    than projections directly. This keeps the point-scoring implementation in
    one place and prevents the 18D scenario layer from silently creating a
    second scoring model.
    """

    evaluations: list[StrategyScenarioEvaluation] = []
    warnings: list[str] = []

    for scenario in scenarios:
        source = _find_source_option(scenario, cross_horizon_plan)
        if source is None:
            warning = (
                f"No cross-horizon strategic option matched scenario {scenario.scenario_id}."
            )
            evaluations.append(
                StrategyScenarioEvaluation(
                    scenario_id=scenario.scenario_id,
                    source_option_id=scenario.source_option_id or "",
                    initial_action_type=scenario.initial_action.action_type,
                    remaining_transfer_flexibility=scenario.remaining_transfer_flexibility,
                    hit_cost=scenario.hit_cost,
                    horizon_scores=(),
                    target_to_long_delta=None,
                    data_complete=False,
                    warnings=(warning,),
                )
            )
            warnings.append(warning)
            continue

        horizon_scores = tuple(
            _tradeoff_from_score(score)
            for score in source.horizon_scores
        )
        target = next(
            (score.strategic_score for score in horizon_scores if score.horizon_name == "target"),
            None,
        )
        long = next(
            (score.strategic_score for score in horizon_scores if score.horizon_name == "long"),
            None,
        )
        delta = None if target is None or long is None else long - target
        scenario_warnings = tuple(
            dict.fromkeys(
                list(scenario.warnings)
                + list(source.warnings)
            )
        )
        complete = bool(scenario.data_complete and source.data_complete)
        evaluations.append(
            StrategyScenarioEvaluation(
                scenario_id=scenario.scenario_id,
                source_option_id=source.option_id,
                initial_action_type=scenario.initial_action.action_type,
                remaining_transfer_flexibility=scenario.remaining_transfer_flexibility,
                hit_cost=scenario.hit_cost,
                horizon_scores=horizon_scores,
                target_to_long_delta=delta,
                data_complete=complete,
                warnings=scenario_warnings,
            )
        )
        warnings.extend(scenario_warnings)

    horizons = cross_horizon_plan.horizons
    winners = tuple(
        (name, _winner_for(evaluations, name))
        for name, _ in horizons
    )
    long_winner = dict(winners).get("long")
    complete_evaluations = [item for item in evaluations if item.data_complete]
    selected = next(
        (item for item in complete_evaluations if item.scenario_id == long_winner),
        None,
    )

    rationale: list[str] = []
    reconciliation = "NO_COMPLETE_STRATEGY"
    if selected is not None:
        unique_winners = {winner for _, winner in winners if winner is not None}
        if len(unique_winners) == 1:
            reconciliation = "CONSISTENT_ACROSS_HORIZONS"
            rationale.append(
                f"{selected.scenario_id} is the complete-data leader across target, 3-GW, 5-GW and 8-GW views."
            )
        else:
            reconciliation = "LONG_HORIZON_LEADER_WITH_EXPLICIT_TRADE_OFFS"
            rationale.append(
                f"{selected.scenario_id} leads the complete-data 8-GW evaluation under the provisional long-horizon selection anchor."
            )
            for horizon_name, winner in winners:
                if winner and winner != selected.scenario_id:
                    rationale.append(
                        f"{winner} leads the {horizon_name} horizon, creating an explicit horizon trade-off."
                    )
            if selected.target_to_long_delta is not None:
                rationale.append(
                    f"Its 8-GW strategic score differs from its target-GW score by {selected.target_to_long_delta:.2f} points."
                )
        rationale.append(
            "Future exact transfer sequences remain conditional reassessments; this evaluation does not assume future prices, availability or team news."
        )

    data_complete = selected is not None and not warnings
    return StrategyScenarioEvaluationPlan(
        decision_gameweek=cross_horizon_plan.decision_gameweek,
        target_gameweek=cross_horizon_plan.target_gameweek,
        horizons=horizons,
        horizon_winners=winners,
        selected_scenario_id=selected.scenario_id if selected else None,
        reconciliation=reconciliation,
        rationale=tuple(rationale),
        evaluations=tuple(evaluations),
        data_complete=data_complete,
        warnings=tuple(dict.fromkeys(warnings)),
    )
