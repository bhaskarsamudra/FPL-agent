"""
strategy_scenario.py

Batch 18D - strategic scenario model.

This module represents a *strategy path* rather than a forecast or a single
transfer candidate. A strategy path records the action known at the decision
timestamp, future reassessment points, transfer/hit usage and remaining
flexibility. Future decisions are intentionally represented as reassessment
points rather than asserted future transfers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


MODEL_VERSION = "strategy_scenario_v1"


@dataclass(frozen=True)
class StrategyAction:
    """One strategic action attached to a decision point."""

    action_type: str
    description: str
    sell_player_id: int | None = None
    buy_player_id: int | None = None
    chip: str | None = None
    transfer_cost: float = 0.0
    hit_cost: float = 0.0
    data_complete: bool = True
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StrategyDecisionPoint:
    """A point at which the strategy can make or reassess a decision."""

    gameweek: int
    action: StrategyAction
    is_reassessment: bool = False
    triggers: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StrategyScenario:
    """Auditable strategy path across a planning horizon."""

    scenario_id: str
    description: str
    decision_gameweek: int
    target_gameweek: int
    horizon_gameweeks: tuple[int, ...]
    decision_points: tuple[StrategyDecisionPoint, ...]
    free_transfers_consumed: int
    hits_taken: int
    hit_cost: float
    remaining_transfer_flexibility: int
    data_complete: bool
    warnings: tuple[str, ...] = ()
    model_version: str = MODEL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def initial_action(self) -> StrategyAction:
        """Return the action at the target Gameweek."""
        for point in self.decision_points:
            if point.gameweek == self.target_gameweek:
                return point.action
        raise ValueError("Strategy scenario has no target-Gameweek action.")

    @property
    def future_decision_points(self) -> tuple[StrategyDecisionPoint, ...]:
        """Return future points that remain conditional reassessments."""
        return tuple(
            point
            for point in self.decision_points
            if point.gameweek > self.target_gameweek
        )

    @property
    def reassessment_gameweeks(self) -> tuple[int, ...]:
        return tuple(
            point.gameweek
            for point in self.decision_points
            if point.is_reassessment
        )
