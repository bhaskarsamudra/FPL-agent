from strategy_scenario import StrategyAction, StrategyDecisionPoint, StrategyScenario
from strategy_scenario_engine import (
    CrossHorizonStrategyOption,
    CrossHorizonStrategyPlan,
    HorizonStrategyScore,
)
from strategy_scenario_evaluator import evaluate_strategy_scenarios
from strategy_selection import (
    MODEL_VERSION,
    SELECTION_BASIS,
    build_strategy_selection,
)


def _score(name, value):
    length = {"target": 1, "short": 3, "medium": 5, "long": 8}[name]
    return HorizonStrategyScore(
        horizon_name=name,
        gameweeks=tuple(range(6, 6 + length)),
        projected_points=float(value),
        captaincy_points=0.0,
        transfer_hit_cost=0.0,
        strategic_score=float(value),
        data_complete=True,
        warnings=(),
    )


def _scenario(scenario_id, option_id, flexibility, hit_cost=0.0):
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
                action=StrategyAction(action_type="transfer", description="Act"),
            ),
            StrategyDecisionPoint(
                gameweek=7,
                action=StrategyAction(action_type="reassess", description="Reassess"),
                is_reassessment=True,
            ),
        ),
        free_transfers_consumed=1,
        hits_taken=1 if hit_cost else 0,
        hit_cost=hit_cost,
        remaining_transfer_flexibility=flexibility,
        data_complete=True,
    )


def _evaluation_plan():
    horizons = (
        ("target", (6,)),
        ("short", (6, 7, 8)),
        ("medium", (6, 7, 8, 9, 10)),
        ("long", tuple(range(6, 14))),
    )
    option_a = CrossHorizonStrategyOption(
        option_id="A",
        option_type="transfer",
        description="A",
        horizon_scores=(
            _score("target", 70),
            _score("short", 185),
            _score("medium", 290),
            _score("long", 440),
        ),
        data_complete=True,
    )
    option_b = CrossHorizonStrategyOption(
        option_id="B",
        option_type="transfer",
        description="B",
        horizon_scores=(
            _score("target", 65),
            _score("short", 180),
            _score("medium", 300),
            _score("long", 450),
        ),
        data_complete=True,
    )
    cross_plan = CrossHorizonStrategyPlan(
        decision_gameweek=5,
        target_gameweek=6,
        horizons=horizons,
        horizon_winners=(
            ("target", "A"),
            ("short", "A"),
            ("medium", "B"),
            ("long", "B"),
        ),
        selected_option_id="B",
        reconciliation="LONG_HORIZON_LEADER_WITH_EXPLICIT_TRADE_OFFS",
        rationale=("A leads immediate views; B leads longer views.",),
        options=(option_a, option_b),
        data_complete=True,
    )
    return evaluate_strategy_scenarios(
        scenarios=(
            _scenario("SCENARIO_A", "A", flexibility=2),
            _scenario("SCENARIO_B", "B", flexibility=0, hit_cost=4.0),
        ),
        cross_horizon_plan=cross_plan,
    )


def test_selection_contract_defers_actual_winner():
    result = build_strategy_selection(evaluation_plan=_evaluation_plan())
    assert result.selected_scenario_id is None
    assert result.selection_basis == SELECTION_BASIS
    assert result.model_version == MODEL_VERSION


def test_selection_preserves_all_scenario_candidates():
    result = build_strategy_selection(evaluation_plan=_evaluation_plan())
    assert tuple(item.scenario_id for item in result.candidates) == (
        "SCENARIO_A",
        "SCENARIO_B",
    )


def test_selection_exposes_horizon_leaders():
    result = build_strategy_selection(evaluation_plan=_evaluation_plan())
    assert result.leader_for("target") == "SCENARIO_A"
    assert result.leader_for("long") == "SCENARIO_B"


def test_selection_preserves_authoritative_scores():
    result = build_strategy_selection(evaluation_plan=_evaluation_plan())
    candidate = result.candidate_for("SCENARIO_B")
    assert candidate.long_score == 450.0
    assert candidate.medium_score == 300.0
    assert candidate.target_to_long_delta == 385.0


def test_selection_exposes_horizon_leader_conflict():
    result = build_strategy_selection(evaluation_plan=_evaluation_plan())
    assert any(
        item.tradeoff_type == "HORIZON_LEADER_CONFLICT"
        for item in result.tradeoffs
    )


def test_selection_exposes_transfer_flexibility_tradeoff():
    result = build_strategy_selection(evaluation_plan=_evaluation_plan())
    tradeoff = next(
        item for item in result.tradeoffs
        if item.tradeoff_type == "TRANSFER_FLEXIBILITY"
    )
    assert "SCENARIO_A" in tradeoff.scenario_ids
    assert "SCENARIO_B" in tradeoff.scenario_ids


def test_selection_exposes_hit_cost_tradeoff():
    result = build_strategy_selection(evaluation_plan=_evaluation_plan())
    tradeoff = next(
        item for item in result.tradeoffs
        if item.tradeoff_type == "TRANSFER_HIT_COST"
    )
    assert "SCENARIO_B" in tradeoff.scenario_ids
    assert "4.00" in tradeoff.description


def test_selection_keeps_future_choice_out_of_d1():
    result = build_strategy_selection(evaluation_plan=_evaluation_plan())
    assert result.selected_scenario_id is None
    assert result.selected_scenario_id is None
