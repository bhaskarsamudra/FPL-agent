from types import SimpleNamespace

import pytest

from production_projection import ProductionProjectionResult
from strategy_orchestrator import build_strategic_decision_from_production_projection


def _state():
    squad = tuple(
        {
            "id": i,
            "name": f"P{i}",
            "position_id": 3,
            "price": 60,
            "squad_position": i,
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


def _projection_result(*, data_complete=True, warnings=()):
    projections = {
        i: {
            "horizon_expected_points": 10.0 + i,
            "projection_complete": True,
            "fixtures": [
                {
                    "gameweek": 6,
                    "expected_points": 10.0 + i,
                    "data_complete": True,
                    "warnings": (),
                }
            ],
        }
        for i in range(1, 16)
    }
    return ProductionProjectionResult(
        target_gameweek=6,
        horizon_gameweeks=(6, 7),
        projections=projections,
        fixture_projections=(),
        team_expected_goals={},
        data_complete=data_complete,
        warnings=tuple(warnings),
    )


def test_production_projection_is_the_orchestrator_projection_source():
    result = build_strategic_decision_from_production_projection(
        manager_state=_state(),
        market_players=[],
        projection_result=_projection_result(),
    )

    assert result.target_gameweek == 6
    assert result.multi_gw_plan is not None
    assert result.selected_option is not None
    assert result.data_complete
    assert result.warnings == ()


def test_incomplete_production_projection_marks_decision_incomplete():
    result = build_strategic_decision_from_production_projection(
        manager_state=_state(),
        market_players=[],
        projection_result=_projection_result(
            data_complete=False,
            warnings=("Missing team state before GW6.",),
        ),
    )

    assert result.selected_option is not None
    assert not result.data_complete
    assert "Missing team state before GW6." in result.warnings


def test_production_projection_rejects_wrong_target_horizon():
    projection = _projection_result()
    projection = ProductionProjectionResult(
        target_gameweek=7,
        horizon_gameweeks=projection.horizon_gameweeks,
        projections=projection.projections,
        fixture_projections=projection.fixture_projections,
        team_expected_goals=projection.team_expected_goals,
        data_complete=projection.data_complete,
        warnings=projection.warnings,
    )

    with pytest.raises(ValueError, match="must start at its target Gameweek"):
        build_strategic_decision_from_production_projection(
            manager_state=_state(),
            market_players=[],
            projection_result=projection,
        )


def test_production_projection_requires_authoritative_result_type():
    with pytest.raises(TypeError, match="ProductionProjectionResult"):
        build_strategic_decision_from_production_projection(
            manager_state=_state(),
            market_players=[],
            projection_result={6: {"horizon_expected_points": 20.0}},
        )
