from strategy_scenario import StrategyAction, StrategyDecisionPoint, StrategyScenario


def test_strategy_scenario_keeps_initial_action_separate_from_reassessment_points():
    initial = StrategyAction(
        action_type="transfer",
        description="Transfer A to C.",
        sell_player_id=1,
        buy_player_id=3,
    )
    reassess = StrategyDecisionPoint(
        gameweek=7,
        action=StrategyAction(
            action_type="reassess",
            description="Reassess with refreshed information.",
        ),
        is_reassessment=True,
        triggers=("availability_change",),
    )
    scenario = StrategyScenario(
        scenario_id="S1",
        description="Initial transfer with future reassessment.",
        decision_gameweek=5,
        target_gameweek=6,
        horizon_gameweeks=(6, 7, 8),
        decision_points=(
            StrategyDecisionPoint(gameweek=6, action=initial),
            reassess,
        ),
        free_transfers_consumed=1,
        hits_taken=0,
        hit_cost=0.0,
        remaining_transfer_flexibility=0,
        data_complete=True,
    )

    assert scenario.initial_action == initial
    assert scenario.reassessment_gameweeks == (7,)
    assert scenario.to_dict()["scenario_id"] == "S1"


def test_strategy_action_supports_transfer_cost_and_hit_cost():
    action = StrategyAction(
        action_type="transfer",
        description="Transfer A to B.",
        sell_player_id=1,
        buy_player_id=2,
        transfer_cost=1.5,
        hit_cost=4.0,
    )

    assert action.transfer_cost == 1.5
    assert action.hit_cost == 4.0
