from chip_engine import (
    available_chip_instances,
    assess_chips,
    build_chip_scenario,
    evaluate_chip_counterfactual,
    rank_chip_opportunities,
)
from fpl_rules import FALLBACK_2026_27_RULES
from scenario_engine import Scenario


def _projection(*values):
    return {
        "fixtures": [
            {
                "gameweek": gw,
                "expected_points": points,
                "data_complete": True,
                "warnings": (),
            }
            for gw, points in enumerate(values, start=11)
        ]
    }


def test_available_chip_instances_respect_two_wildcard_windows():
    first_half = available_chip_instances(
        rules=FALLBACK_2026_27_RULES,
        current_gameweek=10,
    )
    assert "wildcard_1" in {item.instance_id for item in first_half}
    assert "wildcard_2" not in {item.instance_id for item in first_half}

    second_half = available_chip_instances(
        rules=FALLBACK_2026_27_RULES,
        current_gameweek=20,
    )
    assert "wildcard_1" not in {item.instance_id for item in second_half}
    assert "wildcard_2" in {item.instance_id for item in second_half}


def test_triple_captain_counterfactual_adds_one_extra_captain_multiple():
    baseline = Scenario(
        scenario_id="baseline",
        scenario_type="baseline",
        description="Current XI",
        player_ids=(1, 2),
        captain_by_gameweek=((11, 1),),
        captain_multiplier_by_gameweek=((11, 2.0),),
    )
    instance = next(item for item in FALLBACK_2026_27_RULES.chip_instances if item.chip_type == "3xc")
    chip = build_chip_scenario(
        baseline=baseline,
        chip_instance=instance,
        target_gameweek=11,
        horizon_gameweeks=[11],
        captain_player_id=1,
    )

    result = evaluate_chip_counterfactual(
        chip_instance=instance,
        target_gameweek=11,
        baseline_scenario=baseline,
        chip_scenario=chip,
        projections={1: _projection(10), 2: _projection(5)},
        horizon_gameweeks=[11],
        rules_version="2026/27-test",
    )

    assert result.baseline_projected_points == 25
    assert result.chip_projected_points == 35
    assert result.incremental_value == 10
    assert result.data_complete is True


def test_bench_boost_adds_bench_players_only_in_target_gameweek():
    baseline = Scenario(
        scenario_id="baseline",
        scenario_type="baseline",
        description="Current XI",
        player_ids=(1, 2),
        captain_by_gameweek=((11, 1),),
        captain_multiplier_by_gameweek=((11, 1.0),),
    )
    instance = next(item for item in FALLBACK_2026_27_RULES.chip_instances if item.chip_type == "bboost")
    chip = build_chip_scenario(
        baseline=baseline,
        chip_instance=instance,
        target_gameweek=11,
        horizon_gameweeks=[11, 12],
        bench_player_ids=(3,),
    )

    result = evaluate_chip_counterfactual(
        chip_instance=instance,
        target_gameweek=11,
        baseline_scenario=baseline,
        chip_scenario=chip,
        projections={1: _projection(5, 5), 2: _projection(5, 5), 3: _projection(7, 7)},
        horizon_gameweeks=[11, 12],
    )

    assert result.baseline_projected_points == 20
    assert result.chip_projected_points == 27
    assert result.incremental_value == 7


def test_free_hit_replaces_only_target_gameweek():
    baseline = Scenario(
        scenario_id="baseline",
        scenario_type="baseline",
        description="Current XI",
        player_ids=(1, 2),
    )
    instance = next(item for item in FALLBACK_2026_27_RULES.chip_instances if item.chip_type == "freehit")
    chip = build_chip_scenario(
        baseline=baseline,
        chip_instance=instance,
        target_gameweek=11,
        horizon_gameweeks=[11, 12],
        replacement_player_ids=(3, 4),
    )

    result = evaluate_chip_counterfactual(
        chip_instance=instance,
        target_gameweek=11,
        baseline_scenario=baseline,
        chip_scenario=chip,
        projections={
            1: _projection(5, 5),
            2: _projection(5, 5),
            3: _projection(10, 0),
            4: _projection(10, 0),
        },
        horizon_gameweeks=[11, 12],
    )

    assert result.baseline_projected_points == 20
    assert result.chip_projected_points == 30
    assert result.incremental_value == 10


def test_wildcard_replaces_future_horizon_from_target_gameweek():
    baseline = Scenario(
        scenario_id="baseline",
        scenario_type="baseline",
        description="Current XI",
        player_ids=(1, 2),
    )
    instance = next(item for item in FALLBACK_2026_27_RULES.chip_instances if item.chip_type == "wildcard")
    chip = build_chip_scenario(
        baseline=baseline,
        chip_instance=instance,
        target_gameweek=11,
        horizon_gameweeks=[11, 12],
        replacement_player_ids=(3, 4),
    )

    result = evaluate_chip_counterfactual(
        chip_instance=instance,
        target_gameweek=11,
        baseline_scenario=baseline,
        chip_scenario=chip,
        projections={
            1: _projection(5, 5),
            2: _projection(5, 5),
            3: _projection(8, 8),
            4: _projection(8, 8),
        },
        horizon_gameweeks=[11, 12],
    )

    assert result.baseline_projected_points == 20
    assert result.chip_projected_points == 32
    assert result.incremental_value == 12


def test_incomplete_chip_counterfactual_exposes_warnings():
    baseline = Scenario(
        scenario_id="baseline",
        scenario_type="baseline",
        description="Current XI",
        player_ids=(1, 2),
    )
    instance = next(item for item in FALLBACK_2026_27_RULES.chip_instances if item.chip_type == "bboost")
    chip = build_chip_scenario(
        baseline=baseline,
        chip_instance=instance,
        target_gameweek=11,
        horizon_gameweeks=[11],
        bench_player_ids=(3,),
    )

    result = evaluate_chip_counterfactual(
        chip_instance=instance,
        target_gameweek=11,
        baseline_scenario=baseline,
        chip_scenario=chip,
        projections={1: _projection(5), 2: _projection(5)},
        horizon_gameweeks=[11],
    )

    assert result.data_complete is False
    assert result.warnings


def test_rank_chip_opportunities_orders_complete_evidence_first():
    baseline = Scenario(
        scenario_id="baseline",
        scenario_type="baseline",
        description="Current XI",
        player_ids=(1,),
    )
    instance = next(item for item in FALLBACK_2026_27_RULES.chip_instances if item.chip_type == "3xc")
    chip = build_chip_scenario(
        baseline=baseline,
        chip_instance=instance,
        target_gameweek=11,
        horizon_gameweeks=[11],
        captain_player_id=1,
    )
    complete = evaluate_chip_counterfactual(
        chip_instance=instance,
        target_gameweek=11,
        baseline_scenario=baseline,
        chip_scenario=chip,
        projections={1: _projection(10)},
        horizon_gameweeks=[11],
    )
    incomplete = evaluate_chip_counterfactual(
        chip_instance=instance,
        target_gameweek=11,
        baseline_scenario=baseline,
        chip_scenario=chip,
        projections={},
        horizon_gameweeks=[11],
    )

    ranked = rank_chip_opportunities([incomplete, complete])
    assert ranked[0].data_complete is True


def test_legacy_assess_chips_remains_compatible():
    rows = assess_chips(
        available_chips=["freehit"],
        horizon_gameweeks=[6, 7],
        current_squad_expected_points=30,
        best_transfer_expected_gain=2,
        bench_expected_points=8,
        captain_expected_points=10,
        fixture_count_by_gameweek={6: 10, 7: 10},
    )
    assert rows[0].recommendation == "HOLD"
