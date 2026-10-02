from __future__ import annotations

import pytest

from evaluation_models import OutcomeRecord
from forecast_evaluation import (
    build_forecast_record,
    evaluate_forecast,
    summarize_forecast_evaluations,
)


def _forecast():
    return build_forecast_record(
        forecast_id="f1",
        forecast_type="player_points",
        decision_gameweek=10,
        target_gameweek=11,
        target_entity_type="player",
        target_entity_id=123,
        predicted_value=7.5,
        prediction_unit="fpl_points",
        model_version="xp_v2",
        predicted_at="2026-10-02T10:00:00Z",
        data_snapshot_at="2026-10-02T09:59:00Z",
        warnings=["example warning"],
    )


def test_evaluate_forecast_calculates_signed_and_absolute_error():
    evaluation = evaluate_forecast(
        forecast=_forecast(),
        outcome=OutcomeRecord(
            outcome_id="o1",
            target_gameweek=11,
            entity_type="player",
            entity_id=123,
            actual_value=10.0,
            evaluated_at="2026-10-10T10:00:00Z",
            outcome_unit="fpl_points",
        ),
        evaluated_at="2026-10-10T10:01:00Z",
    )

    assert evaluation.error == pytest.approx(2.5)
    assert evaluation.absolute_error == pytest.approx(2.5)
    assert evaluation.diagnostics["model_version"] == "xp_v2"


def test_evaluate_forecast_rejects_mismatched_entity():
    with pytest.raises(ValueError, match="entity IDs"):
        evaluate_forecast(
            forecast=_forecast(),
            outcome=OutcomeRecord(
                outcome_id="o1",
                target_gameweek=11,
                entity_type="player",
                entity_id=456,
                actual_value=10.0,
                evaluated_at="2026-10-10T10:00:00Z",
                outcome_unit="fpl_points",
            ),
            evaluated_at="2026-10-10T10:01:00Z",
        )


def test_summarize_forecast_evaluations():
    forecast = _forecast()
    outcomes = [
        OutcomeRecord("o1", 11, "player", 123, 10.0, "now", "fpl_points"),
        OutcomeRecord("o2", 11, "player", 123, 5.0, "now", "fpl_points"),
    ]
    evaluations = [
        evaluate_forecast(forecast=forecast, outcome=outcomes[0], evaluated_at="now"),
        evaluate_forecast(forecast=forecast, outcome=outcomes[1], evaluated_at="now"),
    ]

    summary = summarize_forecast_evaluations(evaluations)

    assert summary["count"] == 2
    assert summary["mean_error"] == pytest.approx(0.0)
    assert summary["mean_absolute_error"] == pytest.approx(2.5)
