from types import SimpleNamespace

from chip_engine import ChipScenarioEvaluation
from dream_team_engine import parse_dream_team
from strategy_orchestrator import (
    build_dream_team_decision_context,
    build_rival_decision_context,
    build_strategic_decision,
)


def _state():
    squad = tuple(
        {
            "id": i,
            "name": f"P{i}",
            "position_id": 3,
            "price": 60,
            "squad_position": i,
            "selected_by_percent": "20.0",
        }
        for i in range(1, 16)
    )
    return SimpleNamespace(
        team_id=1,
        gameweek=5,
        bank=2.0,
        free_transfers=1,
        squad=squad,
    )


def _projections():
    return {
        i: {
            "horizon_expected_points": 10.0 + i,
            "projection_complete": True,
            "fixtures": [
                {"gameweek": 6, "expected_points": 5.0 + i, "data_complete": True, "warnings": ()}
            ],
        }
        for i in range(1, 16)
    }


def test_rival_context_keeps_absolute_and_relative_state_separate():
    context = build_rival_decision_context(
        standings=[
            {"entry": 1, "rank": 5, "entry_name": "Us", "player_name": "A", "total": 300},
            {"entry": 2, "rank": 4, "entry_name": "Ahead", "player_name": "B", "total": 305},
            {"entry": 3, "rank": 6, "entry_name": "Behind", "player_name": "C", "total": 295},
        ],
        user_team_id=1,
    )

    assert context.user_rank == 5
    assert context.nearest_ahead[0].entry_id == 2
    assert context.nearest_behind[0].entry_id == 3


def test_dream_context_does_not_promote_future_gameweek_dream_team():
    season = parse_dream_team(
        {"team": [{"element": 1, "points": 80}]},
        scope="season_to_date",
        gameweek=None,
        source_endpoint="dream-team/",
    )
    context = build_dream_team_decision_context(season_to_date=season)
    assert context.gameweek_outcome is None
    assert context.season_to_date.scope == "season_to_date"


def test_orchestrator_compares_roll_transfer_and_chip_on_common_horizon_basis():
    projections = _projections()
    projections[100] = {
        "horizon_expected_points": 50.0,
        "projection_complete": True,
        "fixtures": [{"gameweek": 6, "expected_points": 20.0, "data_complete": True, "warnings": ()}],
    }
    chip = ChipScenarioEvaluation(
        chip_instance_id="3xc_1",
        chip="3xc",
        target_gameweek=6,
        horizon_start_gameweek=6,
        horizon_end_gameweek=6,
        baseline_projected_points=100.0,
        chip_projected_points=125.0,
        incremental_value=25.0,
        data_complete=True,
        feature_context={},
    )

    result = build_strategic_decision(
        manager_state=_state(),
        market_players=[{"id": 100, "name": "Target", "position_id": 3, "price": 60}],
        projections=projections,
        horizon_gameweeks=[6],
        chip_evaluations=[chip],
    )

    assert result.engine_version == "strategy_orchestrator_v1_2"
    assert result.options
    assert any(option.option_type == "transfer" for option in result.options)
    assert any(option.option_type == "chip" for option in result.options)
    assert result.selected_option is not None


def test_dream_team_is_benchmark_only_and_cannot_change_independent_selection():
    projections = _projections()
    season_a = parse_dream_team(
        {"team": [{"element": 1, "points": 100}]},
        scope="season_to_date",
        gameweek=None,
        source_endpoint="dream-team/",
    )
    season_b = parse_dream_team(
        {"team": [{"element": 100, "points": 500}]},
        scope="season_to_date",
        gameweek=None,
        source_endpoint="dream-team/",
    )

    result_a = build_strategic_decision(
        manager_state=_state(),
        market_players=[],
        projections=projections,
        horizon_gameweeks=[6],
        dream_context=build_dream_team_decision_context(season_to_date=season_a),
    )
    result_b = build_strategic_decision(
        manager_state=_state(),
        market_players=[],
        projections=projections,
        horizon_gameweeks=[6],
        dream_context=build_dream_team_decision_context(season_to_date=season_b),
    )

    assert result_a.dream_team_selection_policy == "benchmark_only"
    assert result_b.dream_team_selection_policy == "benchmark_only"
    assert result_a.selected_option.option_id == result_b.selected_option.option_id
    assert result_a.selected_option.projected_horizon_points == result_b.selected_option.projected_horizon_points


def test_future_gameweek_dream_team_cannot_be_used_as_decision_context():
    future_gw = parse_dream_team(
        {"team": [{"element": 100, "points": 200}]},
        scope="gameweek",
        gameweek=7,
        source_endpoint="dream-team/7/",
    )
    try:
        build_dream_team_decision_context(season_to_date=future_gw)
    except ValueError as exc:
        assert "season-to-date" in str(exc)
    else:
        raise AssertionError("Future Gameweek Dream Team must not be accepted as season context")
