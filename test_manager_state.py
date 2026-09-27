from manager_state import calculate_free_transfers, build_manager_state


def test_free_transfers_basic_roll():
    history = {
        "current": [
            {"event": 1, "event_transfers": 0},
            {"event": 2, "event_transfers": 0},
            {"event": 3, "event_transfers": 0},
        ],
        "chips": [],
    }
    assert calculate_free_transfers(history, 3) == 3


def test_free_transfers_are_capped():
    history = {
        "current": [
            {"event": i, "event_transfers": 0}
            for i in range(1, 10)
        ],
        "chips": [],
    }
    assert calculate_free_transfers(history, 9) == 5


def test_manager_state_builds_verified_squad():
    players = [
        {
            "id": i,
            "name": f"P{i}",
            "price": 50,
            "position_id": 2,
            "team_id": 1,
        }
        for i in range(1, 16)
    ]
    picks = [
        {
            "element": i,
            "position": i,
            "multiplier": 1,
            "is_captain": i == 1,
            "is_vice_captain": i == 2,
            "purchase_price": 50,
        }
        for i in range(1, 16)
    ]

    state = build_manager_state(
        team_id=123,
        gameweek=5,
        picks_data={
            "picks": picks,
            "entry_history": {
                "bank": 10,
                "value": 1000,
            },
        },
        manager_data={
            "name": "Test FC",
            "player_first_name": "Test",
            "player_last_name": "Manager",
            "summary_overall_points": 100,
            "summary_overall_rank": 1000,
        },
        history_data={
            "current": [
                {"event": 1, "event_transfers": 0},
                {"event": 2, "event_transfers": 0},
            ],
            "chips": [],
        },
        player_universe=players,
    )

    assert state.team_id == 123
    assert len(state.squad) == 15
    assert state.bank == 1.0
    assert state.team_value == 100.0
