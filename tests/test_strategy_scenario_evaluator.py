from strategy_scenario import StrategyAction, StrategyDecisionPoint, StrategyScenario
from strategy_scenario_engine import (
    CrossHorizonStrategyOption,
    CrossHorizonStrategyPlan,
    HorizonStrategyScore,
)
from strategy_scenario_evaluator import evaluate_strategy_scenarios


def _score(name, value, complete=True):
    length = {"target": 1, "short": 3, "medium": 5, "long": 8}[name]
    start = 6
    return HorizonStrategyScore(
        horizon_name=name,
        gameweeks=tuple(range(start, start + length)),
        projected_points=value,
        captaincy_points=0.0,
        transfer_hit_cost=0.0,
        strategic_score=value,
        data_complete=complete,
        warnings=(),
    )


def _scenario(scenario_id, option_id, flexibility=1):
    return StrategyScenario(
        scenario_id=scenario_id,
        description="Test scenario",
        source_option_id=option_id,
        decision_gameweek=5,
        target_gameweek=6,
        horizon_gameweeks=tuple(range(6, 14)),
        decision_points=(
            StrategyDecisionPoint(
                gameweek=6,
                action=StrategyAction(action_type="roll", description="Roll"),
            ),
            StrategyDecisionPoint(
                gameweek=7,
                action=StrategyAction(action_type="reassess", description="Reassess"),
                is_reassessment=True,
            ),
        ),
        free_transfers_consumed=0,
        hits_taken=0,
        hit_cost=0.0,
        remaining_transfer_flexibility=flexibility,
        data_complete=True,
    )


def _plan():
    horizons = (
        ("target", (6,)),
        ("short", (6, 7, 8)),
        ("medium", (6, 7, 8, 9, 10)),
        ("long", tuple(range(6, 14))),
    )
    option_a = CrossHorizonStrategyOption(
        option_id="A",
        option_type="roll",
        description="A",
        horizon_scores=tuple(
            _score(name, value)
            for name, value in (
                ("target", 60),
                ("short", 170),
                ("medium", 280),
                ("long", 430),
            )
        ),
        data_complete=True,
    )
    option_b = CrossHorizonStrategyOption(
        option_id="B",
        option_type="transfer",
        description="B",
        horizon_scores=tuple(
            _score(name, value)
            for name, value in (
                ("target", 65),
                ("short", 180),
                ("medium", 300),
                ("long", 450),
            )
        ),
        data_complete=True,
    )
    return CrossHorizonStrategyPlan(
        decision_gameweek=5,
        target_gameweek=6,
        horizons=horizons,
        horizon_winners=(("target", "B"), ("short", "B"), ("medium", "B"), ("long", "B")),
        selected_option_id="B",
        reconciliation="CONSISTENT_ACROSS_HORIZONS",
        rationale=("B leads all horizons.",),
        options=(option_a, option_b),
        data_complete=True,
    )


def test_evaluator_maps_scenarios_to_existing_cross_horizon_scores():
    result = evaluate_strategy_scenarios(
        scenarios=(_scenario("SCENARIO_B", "B"),),
        cross_horizon_plan=_plan(),
    )

    assert result.data_complete
    assert result.selected_scenario_id == "SCENARIO_B"
    assert result.winner_for("long") == "SCENARIO_B"
    assert result.evaluation_for("SCENARIO_B").score_for("short").strategic_score == 180


def test_evaluator_preserves_target_to_long_tradeoff():
    plan = _plan()
    result = evaluate_strategy_scenarios(
        scenarios=(_scenario("SCENARIO_A", "A"), _scenario("SCENARIO_B", "B")),
        cross_horizon_plan=plan,
    )

    evaluation = result.evaluation_for("SCENARIO_B")
    assert evaluation.target_to_long_delta == 385


def test_evaluator_reports_horizon_specific_winners_as_scenario_ids():
    plan = _plan()
    result = evaluate_strategy_scenarios(
        scenarios=(_scenario("SCENARIO_A", "A"), _scenario("SCENARIO_B", "B")),
        cross_horizon_plan=plan,
    )

    assert result.horizon_winners == (
        ("target", "SCENARIO_B"),
        ("short", "SCENARIO_B"),
        ("medium", "SCENARIO_B"),
        ("long", "SCENARIO_B"),
    )
    assert result.reconciliation == "CONSISTENT_ACROSS_HORIZONS"


def test_evaluator_rejects_unmatched_scenario_from_selection():
    result = evaluate_strategy_scenarios(
        scenarios=(_scenario("SCENARIO_UNKNOWN", "UNKNOWN"),),
        cross_horizon_plan=_plan(),
    )

    assert not result.data_complete
    assert result.selected_scenario_id is None
    assert result.evaluations[0].data_complete is False
    assert "No cross-horizon strategic option matched" in result.warnings[0]


def test_evaluator_does_not_create_future_transfer_actions():
    scenario = _scenario("SCENARIO_A", "A")
    result = evaluate_strategy_scenarios(
        scenarios=(scenario,),
        cross_horizon_plan=_plan(),
    )

    assert all(
        point.action.action_type == "reassess"
        for point in scenario.future_decision_points
    )
    assert result.evaluation_for("SCENARIO_A").source_option_id == "A"


def test_evaluator_surfaces_short_term_vs_long_term_tradeoff():
    plan = _plan()
    option_a = plan.options[0]
    option_b = plan.options[1]
    tradeoff_a = CrossHorizonStrategyOption(
        option_id="A",
        option_type=option_a.option_type,
        description=option_a.description,
        horizon_scores=tuple(
            _score(name, value)
            for name, value in (
                ("target", 70),
                ("short", 185),
                ("medium", 290),
                ("long", 440),
            )
        ),
        data_complete=True,
    )
    tradeoff_b = CrossHorizonStrategyOption(
        option_id="B",
        option_type=option_b.option_type,
        description=option_b.description,
        horizon_scores=tuple(
            _score(name, value)
            for name, value in (
                ("target", 65),
                ("short", 180),
                ("medium", 300),
                ("long", 450),
            )
        ),
        data_complete=True,
    )
    tradeoff_plan = CrossHorizonStrategyPlan(
        decision_gameweek=5,
        target_gameweek=6,
        horizons=plan.horizons,
        horizon_winners=(("target", "A"), ("short", "A"), ("medium", "B"), ("long", "B")),
        selected_option_id="B",
        reconciliation="LONG_HORIZON_LEADER_WITH_EXPLICIT_TRADE_OFFS",
        rationale=("A leads immediate views; B leads the longer horizon.",),
        options=(tradeoff_a, tradeoff_b),
        data_complete=True,
    )

    result = evaluate_strategy_scenarios(
        scenarios=(_scenario("SCENARIO_A", "A"), _scenario("SCENARIO_B", "B")),
        cross_horizon_plan=tradeoff_plan,
    )

    assert result.selected_scenario_id == "SCENARIO_B"
    assert result.winner_for("target") == "SCENARIO_A"
    assert result.winner_for("long") == "SCENARIO_B"
    assert result.reconciliation == "LONG_HORIZON_LEADER_WITH_EXPLICIT_TRADE_OFFS"
    assert any("SCENARIO_A leads the target horizon" in item for item in result.rationale)
    assert any("conditional reassessments" in item for item in result.rationale)
