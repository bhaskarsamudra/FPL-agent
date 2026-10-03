from scenario_engine import Scenario, evaluate_scenario


def _projection(points11, points12):
    return {
        "fixtures": [
            {"gameweek": 11, "expected_points": points11, "data_complete": True, "warnings": ()},
            {"gameweek": 12, "expected_points": points12, "data_complete": True, "warnings": ()},
        ]
    }


def test_scenario_aggregates_player_points_across_horizon():
    scenario = Scenario(
        scenario_id="baseline",
        scenario_type="baseline",
        description="Current squad",
        player_ids=(1, 2),
    )
    result = evaluate_scenario(
        scenario=scenario,
        projections={1: _projection(5, 6), 2: _projection(7, 8)},
        gameweeks=[11, 12],
    )
    assert result.projected_points == 26
    assert [row.projected_points for row in result.gameweek_results] == [12, 14]
    assert result.data_complete is True


def test_scenario_excludes_players():
    scenario = Scenario(
        scenario_id="without-player-2",
        scenario_type="counterfactual",
        description="Remove player 2",
        player_ids=(1, 2),
        excluded_player_ids=(2,),
    )
    result = evaluate_scenario(
        scenario=scenario,
        projections={1: _projection(5, 6), 2: _projection(7, 8)},
        gameweeks=[11, 12],
    )
    assert result.projected_points == 11


def test_scenario_exposes_missing_projection():
    scenario = Scenario(
        scenario_id="incomplete",
        scenario_type="baseline",
        description="Incomplete data",
        player_ids=(1, 99),
    )
    result = evaluate_scenario(
        scenario=scenario,
        projections={1: _projection(5, 6)},
        gameweeks=[11, 12],
    )
    assert result.data_complete is False
    assert any("player 99" in warning for warning in result.warnings)


def test_scenario_applies_captain_multiplier():
    scenario = Scenario(
        scenario_id="captain",
        scenario_type="baseline",
        description="Captain scenario",
        player_ids=(1, 2),
        captain_by_gameweek=((11, 1),),
        captain_multiplier_by_gameweek=((11, 2.0),),
    )
    result = evaluate_scenario(
        scenario=scenario,
        projections={1: _projection(5, 0), 2: _projection(5, 0)},
        gameweeks=[11],
    )
    assert result.projected_points == 15
