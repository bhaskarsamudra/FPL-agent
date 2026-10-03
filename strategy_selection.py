"""
strategy_selection.py

Batch 18D-D1 - strategy selection contract.

This module defines the first-class decision artifact used after scenario
generation and cross-horizon evaluation. D1 deliberately does not select a
winning strategy. It records comparable scenario attributes and explicit
trade-offs so a later, documented selection policy can make that choice
without hiding arbitrary weights inside the data model.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

from strategy_scenario_evaluator import StrategyScenarioEvaluationPlan


MODEL_VERSION = "strategy_selection_v1"
SELECTION_BASIS = "DEFERRED_SELECTION_POLICY"
TRADEOFF_POLICY_VERSION = "strategy_tradeoff_v1"


@dataclass(frozen=True)
class StrategyHorizonComparison:
    """Comparable metrics for one scenario across one planning horizon."""

    scenario_id: str
    horizon_name: str
    strategic_score: float
    projected_points: float
    transfer_hit_cost: float
    data_complete: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StrategyScenarioComparison:
    """Auditable comparison profile for one complete scenario."""

    scenario_id: str
    initial_action_type: str
    horizon_comparisons: tuple[StrategyHorizonComparison, ...]
    target_score: float | None
    short_score: float | None
    medium_score: float | None
    long_score: float | None
    target_to_long_delta: float | None
    hit_cost: float
    remaining_transfer_flexibility: int
    horizon_wins: tuple[str, ...]
    data_complete: bool
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def score_for(self, horizon_name: str) -> float | None:
        mapping = {
            "target": self.target_score,
            "short": self.short_score,
            "medium": self.medium_score,
            "long": self.long_score,
        }
        return mapping.get(horizon_name)


@dataclass(frozen=True)
class StrategyTradeoff:
    """Explicit difference or conflict between scenario alternatives."""

    tradeoff_type: str
    description: str
    scenario_ids: tuple[str, ...]
    data_complete: bool = True
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StrategySelection:
    """Decision-layer contract prepared for a future selection policy."""

    decision_gameweek: int
    target_gameweek: int
    candidates: tuple[StrategyScenarioComparison, ...]
    horizon_leaders: tuple[tuple[str, str | None], ...]
    tradeoffs: tuple[StrategyTradeoff, ...]
    selected_scenario_id: str | None
    selection_basis: str = SELECTION_BASIS
    model_version: str = MODEL_VERSION
    tradeoff_policy_version: str = TRADEOFF_POLICY_VERSION
    data_complete: bool = True
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def leader_for(self, horizon_name: str) -> str | None:
        return dict(self.horizon_leaders).get(horizon_name)

    def candidate_for(self, scenario_id: str) -> StrategyScenarioComparison | None:
        return next(
            (item for item in self.candidates if item.scenario_id == scenario_id),
            None,
        )


def _comparison_from_evaluation(
    evaluation: Any,
    horizon_leaders: dict[str, str | None],
) -> StrategyScenarioComparison:
    horizon_comparisons = tuple(
        StrategyHorizonComparison(
            scenario_id=evaluation.scenario_id,
            horizon_name=score.horizon_name,
            strategic_score=score.strategic_score,
            projected_points=score.projected_points,
            transfer_hit_cost=score.transfer_hit_cost,
            data_complete=score.data_complete,
        )
        for score in evaluation.horizon_scores
    )
    horizon_wins = tuple(
        name
        for name, leader in horizon_leaders.items()
        if leader == evaluation.scenario_id
    )
    return StrategyScenarioComparison(
        scenario_id=evaluation.scenario_id,
        initial_action_type=evaluation.initial_action_type,
        horizon_comparisons=horizon_comparisons,
        target_score=evaluation.score_for("target").strategic_score
        if evaluation.score_for("target")
        else None,
        short_score=evaluation.score_for("short").strategic_score
        if evaluation.score_for("short")
        else None,
        medium_score=evaluation.score_for("medium").strategic_score
        if evaluation.score_for("medium")
        else None,
        long_score=evaluation.score_for("long").strategic_score
        if evaluation.score_for("long")
        else None,
        target_to_long_delta=evaluation.target_to_long_delta,
        hit_cost=evaluation.hit_cost,
        remaining_transfer_flexibility=evaluation.remaining_transfer_flexibility,
        horizon_wins=horizon_wins,
        data_complete=evaluation.data_complete,
        warnings=evaluation.warnings,
    )


def _build_tradeoffs(
    candidates: Sequence[StrategyScenarioComparison],
    horizon_leaders: dict[str, str | None],
) -> tuple[StrategyTradeoff, ...]:
    complete = [item for item in candidates if item.data_complete]
    if not complete:
        return ()

    tradeoffs: list[StrategyTradeoff] = []

    unique_leaders = {leader for leader in horizon_leaders.values() if leader is not None}
    if len(unique_leaders) > 1:
        for horizon_name, leader in horizon_leaders.items():
            if leader is None:
                continue
            other_leaders = sorted(
                item for item in unique_leaders if item != leader
            )
            if other_leaders:
                tradeoffs.append(
                    StrategyTradeoff(
                        tradeoff_type="HORIZON_LEADER_CONFLICT",
                        description=(
                            f"{leader} leads the {horizon_name} horizon while "
                            f"{', '.join(other_leaders)} lead other horizon views."
                        ),
                        scenario_ids=tuple([leader, *other_leaders]),
                    )
                )

    max_flex = max(item.remaining_transfer_flexibility for item in complete)
    min_flex = min(item.remaining_transfer_flexibility for item in complete)
    if max_flex != min_flex:
        high = sorted(
            item.scenario_id
            for item in complete
            if item.remaining_transfer_flexibility == max_flex
        )
        low = sorted(
            item.scenario_id
            for item in complete
            if item.remaining_transfer_flexibility == min_flex
        )
        tradeoffs.append(
            StrategyTradeoff(
                tradeoff_type="TRANSFER_FLEXIBILITY",
                description=(
                    f"{', '.join(high)} retain {max_flex} transfer-flexibility unit(s), "
                    f"while {', '.join(low)} retain {min_flex}."
                ),
                scenario_ids=tuple(sorted(set(high + low))),
            )
        )

    max_hit = max(item.hit_cost for item in complete)
    min_hit = min(item.hit_cost for item in complete)
    if max_hit != min_hit:
        high = sorted(item.scenario_id for item in complete if item.hit_cost == max_hit)
        low = sorted(item.scenario_id for item in complete if item.hit_cost == min_hit)
        tradeoffs.append(
            StrategyTradeoff(
                tradeoff_type="TRANSFER_HIT_COST",
                description=(
                    f"{', '.join(high)} incur {max_hit:.2f} hit-cost unit(s), "
                    f"while {', '.join(low)} incur {min_hit:.2f}."
                ),
                scenario_ids=tuple(sorted(set(high + low))),
            )
        )

    return tuple(tradeoffs)


def build_strategy_selection(
    *,
    evaluation_plan: StrategyScenarioEvaluationPlan,
) -> StrategySelection:
    """Build the D1 selection contract without choosing a scenario.

    The authoritative horizon scores remain owned by the 18C/18D-C evaluator.
    D1 only reshapes those results into a decision-layer contract and exposes
    explicit, auditable trade-offs. A future D2 policy is responsible for any
    actual selection.
    """
    horizon_leaders = dict(evaluation_plan.horizon_winners)
    candidates = tuple(
        _comparison_from_evaluation(item, horizon_leaders)
        for item in evaluation_plan.evaluations
    )
    tradeoffs = _build_tradeoffs(candidates, horizon_leaders)

    warnings = tuple(dict.fromkeys(evaluation_plan.warnings))
    data_complete = bool(
        evaluation_plan.data_complete
        and candidates
        and all(item.data_complete for item in candidates)
    )

    return StrategySelection(
        decision_gameweek=evaluation_plan.decision_gameweek,
        target_gameweek=evaluation_plan.target_gameweek,
        candidates=candidates,
        horizon_leaders=tuple(evaluation_plan.horizon_winners),
        tradeoffs=tradeoffs,
        selected_scenario_id=None,
        selection_basis=SELECTION_BASIS,
        data_complete=data_complete,
        warnings=warnings,
    )
