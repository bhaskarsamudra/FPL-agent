"""
decision_evaluation.py

Reusable strategic decision creation and outcome evaluation helpers.

This module does not decide which action is best.  It records a decision made
by an existing strategy engine and later compares it with a supplied benchmark.
"""

from __future__ import annotations

from typing import Any

from evaluation_models import DecisionEvaluation, DecisionRecord


EVALUATION_VERSION = "decision_eval_v1"


def build_decision_record(
    *,
    decision_id: str,
    decision_gameweek: int,
    decision_type: str,
    recommendation: str,
    alternatives_considered: list[str] | tuple[str, ...],
    generated_at: str,
    data_snapshot_at: str,
    engine_version: str,
    model_versions: list[str] | tuple[str, ...] = (),
    model_inputs_hash: str | None = None,
    data_complete: bool = True,
    warnings: list[str] | tuple[str, ...] = (),
) -> DecisionRecord:
    """Create one auditable strategic decision record."""

    return DecisionRecord(
        decision_id=str(decision_id),
        decision_gameweek=int(decision_gameweek),
        decision_type=str(decision_type),
        recommendation=str(recommendation),
        alternatives_considered=tuple(str(item) for item in alternatives_considered),
        generated_at=str(generated_at),
        data_snapshot_at=str(data_snapshot_at),
        engine_version=str(engine_version),
        model_versions=tuple(str(item) for item in model_versions),
        model_inputs_hash=model_inputs_hash,
        data_complete=bool(data_complete),
        warnings=tuple(str(item) for item in warnings),
    )


def evaluate_decision(
    *,
    decision: DecisionRecord,
    target_gameweek: int,
    recommended_outcome: float,
    benchmark_outcome: float | None,
    evaluated_at: str,
    evaluation_version: str = EVALUATION_VERSION,
    diagnostics: dict[str, Any] | None = None,
) -> DecisionEvaluation:
    """Evaluate a recommendation against an explicitly supplied benchmark.

    A benchmark may be the best alternative actually available, the user's
    chosen alternative, or another clearly defined counterfactual.  The
    evaluator never assumes what the benchmark should be.
    """

    if target_gameweek <= decision.decision_gameweek:
        raise ValueError("target_gameweek must be after decision_gameweek")

    opportunity_cost = None
    if benchmark_outcome is not None:
        opportunity_cost = float(benchmark_outcome) - float(recommended_outcome)

    details = dict(diagnostics or {})
    details.setdefault("decision_type", decision.decision_type)
    details.setdefault("engine_version", decision.engine_version)
    details.setdefault("data_complete", decision.data_complete)
    details.setdefault("warnings", list(decision.warnings))

    return DecisionEvaluation(
        decision_id=decision.decision_id,
        target_gameweek=int(target_gameweek),
        recommended_outcome=float(recommended_outcome),
        benchmark_outcome=(
            None if benchmark_outcome is None else float(benchmark_outcome)
        ),
        opportunity_cost=opportunity_cost,
        evaluation_version=str(evaluation_version),
        evaluated_at=str(evaluated_at),
        diagnostics=details,
    )
