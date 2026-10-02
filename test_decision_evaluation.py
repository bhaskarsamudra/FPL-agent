from __future__ import annotations

import pytest

from decision_evaluation import build_decision_record, evaluate_decision


def _decision():
    return build_decision_record(
        decision_id="d1",
        decision_gameweek=10,
        decision_type="captain",
        recommendation="CAPTAIN 123",
        alternatives_considered=["CAPTAIN 456"],
        generated_at="2026-10-02T10:00:00Z",
        data_snapshot_at="2026-10-02T09:59:00Z",
        engine_version="strategy_v1",
        model_versions=["xp_v2", "captain_v2"],
    )


def test_evaluate_decision_calculates_opportunity_cost():
    evaluation = evaluate_decision(
        decision=_decision(),
        target_gameweek=11,
        recommended_outcome=6.0,
        benchmark_outcome=10.0,
        evaluated_at="2026-10-10T10:00:00Z",
    )

    assert evaluation.opportunity_cost == pytest.approx(4.0)
    assert evaluation.diagnostics["decision_type"] == "captain"


def test_decision_without_benchmark_has_no_opportunity_cost():
    evaluation = evaluate_decision(
        decision=_decision(),
        target_gameweek=11,
        recommended_outcome=6.0,
        benchmark_outcome=None,
        evaluated_at="2026-10-10T10:00:00Z",
    )

    assert evaluation.opportunity_cost is None


def test_evaluate_decision_rejects_non_future_target():
    with pytest.raises(ValueError, match="after decision_gameweek"):
        evaluate_decision(
            decision=_decision(),
            target_gameweek=10,
            recommended_outcome=6.0,
            benchmark_outcome=10.0,
            evaluated_at="2026-10-10T10:00:00Z",
        )
