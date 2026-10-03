from transfer_engine import generate_transfer_candidates


def test_positive_transfer_is_generated():
    squad = [
        {"id": 1, "name": "Sell", "position_id": 3, "price": 60},
    ]
    market = [
        {"id": 2, "name": "Buy", "position_id": 3, "price": 65},
    ]
    projections = {
        1: {"horizon_expected_points": 10, "projection_complete": True},
        2: {"horizon_expected_points": 15, "projection_complete": True},
    }

    rows = generate_transfer_candidates(
        squad=squad,
        market=market,
        projections=projections,
        bank=1.0,
        free_transfers=1,
    )

    assert len(rows) == 1
    assert rows[0].expected_gain == 5


def test_no_transfer_without_free_transfer():
    rows = generate_transfer_candidates(
        squad=[{"id": 1, "name": "Sell", "position_id": 3, "price": 60}],
        market=[{"id": 2, "name": "Buy", "position_id": 3, "price": 60}],
        projections={
            1: {"horizon_expected_points": 10, "projection_complete": True},
            2: {"horizon_expected_points": 15, "projection_complete": True},
        },
        bank=0,
        free_transfers=0,
    )
    assert rows == []
