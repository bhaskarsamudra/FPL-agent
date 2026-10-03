from __future__ import annotations

import pytest

from evaluation_models import DecisionRecord, ForecastRecord, OutcomeRecord


def test_forecast_record_preserves_point_in_time_and_horizon():
    record = ForecastRecord(
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
        horizon_start_gameweek=11,
        horizon_end_gameweek=15,
    )

    assert record.target_gameweek == 11
    assert record.horizon_end_gameweek == 15
    assert record.to_dict()["model_version"] == "xp_v2"


def test_forecast_record_rejects_target_not_after_decision():
    with pytest.raises(ValueError, match="target_gameweek"):
        ForecastRecord(
            forecast_id="f1",
            forecast_type="player_points",
            decision_gameweek=10,
            target_gameweek=10,
            target_entity_type="player",
            target_entity_id=123,
            predicted_value=7.5,
            prediction_unit="fpl_points",
            model_version="xp_v2",
            predicted_at="now",
            data_snapshot_at="now",
        )


def test_decision_and_outcome_records_serialize():
    decision = DecisionRecord(
        decision_id="d1",
        decision_gameweek=10,
        decision_type="captain",
        recommendation="CAPTAIN 123",
        alternatives_considered=("CAPTAIN 456",),
        generated_at="2026-10-02T10:00:00Z",
        data_snapshot_at="2026-10-02T09:59:00Z",
        engine_version="strategy_v1",
    )
    outcome = OutcomeRecord(
        outcome_id="o1",
        target_gameweek=11,
        entity_type="manager",
        entity_id=99,
        actual_value=61.0,
        evaluated_at="2026-10-10T10:00:00Z",
        outcome_unit="fpl_points",
    )

    assert decision.to_dict()["decision_type"] == "captain"
    assert outcome.to_dict()["actual_value"] == 61.0
