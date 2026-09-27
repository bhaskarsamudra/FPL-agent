from chip_engine import assess_chips


def test_wildcard_is_considered_for_large_transfer_opportunity():
    rows = assess_chips(
        available_chips=["wildcard"],
        horizon_gameweeks=[6, 7, 8],
        current_squad_expected_points=30,
        best_transfer_expected_gain=6,
        bench_expected_points=8,
        captain_expected_points=10,
    )

    assert rows[0].recommendation == "CONSIDER"


def test_free_hit_holds_without_blank_fixture_signal():
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
