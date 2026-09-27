from strategy_memory import DecisionSnapshot, append_decision, record_outcome


def test_decision_memory_and_outcome():
    memory = append_decision(
        [],
        DecisionSnapshot(
            gameweek=6,
            timestamp="2026-09-27T10:00:00+05:30",
            action="ROLL",
            player_in=None,
            player_out=None,
            captain_id=10,
            chip=None,
            expected_gain=None,
            confidence="MEDIUM",
            rationale=("No clear transfer gain.",),
        ),
    )
    updated = record_outcome(memory, gameweek=6, outcome_points=62)
    assert updated[0]["outcome_points"] == 62
