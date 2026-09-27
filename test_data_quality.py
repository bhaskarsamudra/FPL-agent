from types import SimpleNamespace
from data_quality import validate_strategy_inputs


def test_incomplete_projection_is_warning():
    state = SimpleNamespace(
        gameweek=6,
        squad=tuple({"id": i} for i in range(1, 16)),
    )
    result = validate_strategy_inputs(
        manager_state=state,
        projections={i: {"projection_complete": i != 1} for i in range(1, 16)},
        target_gameweek=6,
    )
    assert result.ok
    assert result.status == "DEGRADED"


def test_missing_manager_state_blocks():
    result = validate_strategy_inputs(
        manager_state=None,
        projections={},
        target_gameweek=6,
    )
    assert not result.ok
    assert result.status == "BLOCKED"
