"""
evaluation_models.py

Common domain contracts for forecast and strategy evaluation.

These records deliberately do not depend on SQLite, FPL API objects, or the
LLM.  They describe what was known, what was predicted/recommended, and what
later happened.  Persistence can be added behind these contracts later.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ForecastRecord:
    """One forecast made from a point-in-time information state."""

    forecast_id: str
    forecast_type: str
    decision_gameweek: int
    target_gameweek: int
    target_entity_type: str
    target_entity_id: int | str
    predicted_value: float
    prediction_unit: str
    model_version: str
    predicted_at: str
    data_snapshot_at: str
    data_complete: bool = True
    warnings: tuple[str, ...] = ()
    model_inputs_hash: str | None = None
    horizon_start_gameweek: int | None = None
    horizon_end_gameweek: int | None = None

    def __post_init__(self) -> None:
        if self.decision_gameweek < 0:
            raise ValueError("decision_gameweek must be non-negative")
        if self.target_gameweek < 1:
            raise ValueError("target_gameweek must be positive")
        if self.target_gameweek <= self.decision_gameweek:
            raise ValueError("target_gameweek must be after decision_gameweek")
        if self.horizon_start_gameweek is not None and self.horizon_start_gameweek < 1:
            raise ValueError("horizon_start_gameweek must be positive")
        if self.horizon_end_gameweek is not None and self.horizon_end_gameweek < 1:
            raise ValueError("horizon_end_gameweek must be positive")
        if (
            self.horizon_start_gameweek is not None
            and self.horizon_end_gameweek is not None
            and self.horizon_end_gameweek < self.horizon_start_gameweek
        ):
            raise ValueError("horizon_end_gameweek must be >= horizon_start_gameweek")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DecisionRecord:
    """One strategic recommendation made from a point-in-time state."""

    decision_id: str
    decision_gameweek: int
    decision_type: str
    recommendation: str
    alternatives_considered: tuple[str, ...]
    generated_at: str
    data_snapshot_at: str
    engine_version: str
    model_versions: tuple[str, ...] = ()
    model_inputs_hash: str | None = None
    data_complete: bool = True
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.decision_gameweek < 1:
            raise ValueError("decision_gameweek must be positive")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OutcomeRecord:
    """Observed outcome for a prior forecast or decision."""

    outcome_id: str
    target_gameweek: int
    entity_type: str
    entity_id: int | str
    actual_value: float
    evaluated_at: str
    outcome_unit: str

    def __post_init__(self) -> None:
        if self.target_gameweek < 1:
            raise ValueError("target_gameweek must be positive")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ForecastEvaluation:
    """Comparison between a forecast and its realized outcome."""

    forecast_id: str
    outcome_id: str
    predicted_value: float
    actual_value: float
    error: float
    absolute_error: float
    evaluation_version: str
    evaluated_at: str
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DecisionEvaluation:
    """Outcome of a recommendation, including a supplied alternative benchmark."""

    decision_id: str
    target_gameweek: int
    recommended_outcome: float
    benchmark_outcome: float | None
    opportunity_cost: float | None
    evaluation_version: str
    evaluated_at: str
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
