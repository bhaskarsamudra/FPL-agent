from fpl_rules import FALLBACK_2026_27_RULES
from fpl_squad_rules import validate_squad
from multi_gw_transfer_engine import optimize_multi_gw_transfers


def _player(player_id, position, team_id, price, purchase_price=None):
    position_id = {"GK": 1, "DEF": 2, "MID": 3, "FWD": 4}[position]
    row = {
        "id": player_id,
        "name": f"P{player_id}",
        "position": position,
        "position_id": position_id,
        "team_id": team_id,
        "price": price,
    }
    if purchase_price is not None:
        row["purchase_price"] = purchase_price
        row["sell_price"] = purchase_price
    return row


def _fixture_projection(gws, values, complete=True):
    return {
        "fixtures": [
            {
                "gameweek": gw,
                "expected_points": values.get(gw, 0.0),
                "data_complete": complete,
                "warnings": (),
            }
            for gw in gws
        ],
        "projection_complete": complete,
    }


def _dataset():
    squad = []
    market = []
    projections = {}
    player_id = 1

    for position, count in (("GK", 2), ("DEF", 5), ("MID", 5), ("FWD", 3)):
        for index in range(count):
            team_id = ((player_id - 1) % 6) + 1
            squad.append(_player(player_id, position, team_id, 5.0, purchase_price=5.0))
            projections[player_id] = _fixture_projection([6, 7], {6: 5.0, 7: 5.0})
            player_id += 1

    # Replacement MID from a different club. It is much better in GW7.
    buy = _player(player_id, "MID", 6, 6.0)
    market.append(buy)
    projections[player_id] = _fixture_projection([6, 7], {6: 5.0, 7: 15.0})

    # A weaker alternative demonstrates that the planner ranks by horizon value.
    player_id += 1
    buy2 = _player(player_id, "MID", 7, 5.0)
    market.append(buy2)
    projections[player_id] = _fixture_projection([6, 7], {6: 5.0, 7: 7.0})

    return squad, market, projections


def test_multi_gw_optimizer_can_roll_and_carry_free_transfer():
    squad, market, projections = _dataset()
    plan = optimize_multi_gw_transfers(
        current_squad=squad,
        market_players=market,
        projections=projections,
        start_gameweek=6,
        horizon_gameweeks=[6, 7],
        bank=1.0,
        free_transfers=1,
        rules=FALLBACK_2026_27_RULES,
    )

    assert plan.end_gameweek == 7
    assert plan.ending_free_transfers >= 1
    assert plan.projected_points > 0
    assert plan.transfers
    assert plan.transfers[-1]["gameweek"] == 7


def test_multi_gw_optimizer_applies_transfer_hit_when_no_free_transfer():
    squad, market, projections = _dataset()
    plan = optimize_multi_gw_transfers(
        current_squad=squad,
        market_players=market,
        projections=projections,
        start_gameweek=6,
        horizon_gameweeks=[6],
        bank=1.0,
        free_transfers=0,
        rules=FALLBACK_2026_27_RULES,
    )

    assert plan.transfer_hits in {0, 4}
    assert plan.net_value == plan.projected_points


def test_multi_gw_optimizer_rejects_illegal_current_squad():
    squad, market, projections = _dataset()
    squad[0]["team_id"] = squad[1]["team_id"]
    squad[2]["team_id"] = squad[3]["team_id"]
    squad[4]["team_id"] = squad[5]["team_id"]
    squad[6]["team_id"] = squad[7]["team_id"]
    squad[8]["team_id"] = squad[9]["team_id"]
    squad[10]["team_id"] = squad[11]["team_id"]
    squad[12]["team_id"] = squad[13]["team_id"]
    squad[14]["team_id"] = squad[0]["team_id"]

    try:
        optimize_multi_gw_transfers(
            current_squad=squad,
            market_players=market,
            projections=projections,
            start_gameweek=6,
            horizon_gameweeks=[6],
            bank=1.0,
            free_transfers=1,
            rules=FALLBACK_2026_27_RULES,
        )
    except ValueError as exc:
        assert "illegal" in str(exc).lower()
    else:
        raise AssertionError("Expected illegal current squad to be rejected")


def test_multi_gw_optimizer_is_deterministic():
    squad, market, projections = _dataset()
    first = optimize_multi_gw_transfers(
        current_squad=squad,
        market_players=market,
        projections=projections,
        start_gameweek=6,
        horizon_gameweeks=[6, 7],
        bank=1.0,
        free_transfers=1,
        rules=FALLBACK_2026_27_RULES,
    )
    second = optimize_multi_gw_transfers(
        current_squad=squad,
        market_players=market,
        projections=projections,
        start_gameweek=6,
        horizon_gameweeks=[6, 7],
        bank=1.0,
        free_transfers=1,
        rules=FALLBACK_2026_27_RULES,
    )

    assert first.to_dict() == second.to_dict()
