"""
forecast_evaluation.py

Reusable forecast creation and outcome evaluation helpers.

This module measures predictions; it does not create predictions.  Forecast
models such as expected_points.py remain responsible for producing forecasts.
"""

from __future__ import annotations

from typing import Any

from evaluation_models import ForecastEvaluation, ForecastRecord, OutcomeRecord


EVALUATION_VERSION = "forecast_eval_v1"


def build_forecast_record(
    *,
    forecast_id: str,
    forecast_type: str,
    decision_gameweek: int,
    target_gameweek: int,
    target_entity_type: str,
    target_entity_id: int | str,
    predicted_value: float,
    prediction_unit: str,
    model_version: str,
    predicted_at: str,
    data_snapshot_at: str,
    data_complete: bool = True,
    warnings: list[str] | tuple[str, ...] = (),
    model_inputs_hash: str | None = None,
    horizon_start_gameweek: int | None = None,
    horizon_end_gameweek: int | None = None,
) -> ForecastRecord:
    """Create a point-in-time forecast record."""

    return ForecastRecord(
        forecast_id=str(forecast_id),
        forecast_type=str(forecast_type),
        decision_gameweek=int(decision_gameweek),
        target_gameweek=int(target_gameweek),
        target_entity_type=str(target_entity_type),
        target_entity_id=target_entity_id,
        predicted_value=float(predicted_value),
        prediction_unit=str(prediction_unit),
        model_version=str(model_version),
        predicted_at=str(predicted_at),
        data_snapshot_at=str(data_snapshot_at),
        data_complete=bool(data_complete),
        warnings=tuple(str(item) for item in warnings),
        model_inputs_hash=model_inputs_hash,
        horizon_start_gameweek=horizon_start_gameweek,
        horizon_end_gameweek=horizon_end_gameweek,
    )


def evaluate_forecast(
    *,
    forecast: ForecastRecord,
    outcome: OutcomeRecord,
    evaluated_at: str,
    evaluation_version: str = EVALUATION_VERSION,
) -> ForecastEvaluation:
    """Evaluate one forecast against its actual outcome.

    The caller is responsible for supplying an outcome that belongs to the
    forecast's target entity/gameweek and uses the same unit.
    """

    if forecast.target_gameweek != outcome.target_gameweek:
        raise ValueError("Forecast and outcome target gameweeks do not match")
    if forecast.target_entity_type != outcome.entity_type:
        raise ValueError("Forecast and outcome entity types do not match")
    if str(forecast.target_entity_id) != str(outcome.entity_id):
        raise ValueError("Forecast and outcome entity IDs do not match")
    if forecast.prediction_unit != outcome.outcome_unit:
        raise ValueError("Forecast and outcome units do not match")

    error = float(outcome.actual_value) - float(forecast.predicted_value)

    return ForecastEvaluation(
        forecast_id=forecast.forecast_id,
        outcome_id=outcome.outcome_id,
        predicted_value=forecast.predicted_value,
        actual_value=outcome.actual_value,
        error=error,
        absolute_error=abs(error),
        evaluation_version=str(evaluation_version),
        evaluated_at=str(evaluated_at),
        diagnostics={
            "forecast_type": forecast.forecast_type,
            "model_version": forecast.model_version,
            "data_complete": forecast.data_complete,
            "warnings": list(forecast.warnings),
        },
    )


def summarize_forecast_evaluations(
    evaluations: list[ForecastEvaluation] | tuple[ForecastEvaluation, ...],
) -> dict[str, Any]:
    """Return simple aggregate error metrics for a set of evaluations."""

    if not evaluations:
        return {
            "count": 0,
            "mean_error": None,
            "mean_absolute_error": None,
        }

    errors = [item.error for item in evaluations]
    absolute_errors = [item.absolute_error for item in evaluations]

    return {
        "count": len(evaluations),
        "mean_error": sum(errors) / len(errors),
        "mean_absolute_error": sum(absolute_errors) / len(absolute_errors),
    }
