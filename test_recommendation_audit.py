from recommendation_audit import build_audit_record


def test_audit_record_is_serializable():
    row = build_audit_record(
        gameweek=6,
        generated_at="2026-09-27T10:00:00+05:30",
        engine_version="strategy_v1",
        action="ROLL",
        source_status="verified",
        data_quality_status="OK",
        evidence=["test"],
        model_inputs={"free_transfers": 1},
    )
    assert row.to_dict()["action"] == "ROLL"
