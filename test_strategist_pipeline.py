from types import SimpleNamespace

from strategist_pipeline import run_strategy_pipeline


def test_pipeline_blocks_missing_critical_data():
    state = SimpleNamespace(
        gameweek=6,
        squad=(),
    )

    result = run_strategy_pipeline(
        manager_state=state,
        market_players=[],
        projections={},
        available_chips=[],
        horizon_gameweeks=[6, 7, 8],
    )

    assert result.recommendations[0].action == "NO_ANSWER"
    assert not result.data_complete
