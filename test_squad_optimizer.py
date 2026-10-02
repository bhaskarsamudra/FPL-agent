from fpl_rules import FALLBACK_2026_27_RULES
from fpl_squad_rules import validate_squad, validate_starting_xi
from squad_optimizer import optimize_squad


def _player(player_id, position, team_id, price, xp, complete=True):
    position_id = {"GK": 1, "DEF": 2, "MID": 3, "FWD": 4}[position]
    return {
        "id": player_id,
        "name": f"P{player_id}",
        "position": position,
        "position_id": position_id,
        "team_id": team_id,
        "price": price,
    }


def _dataset():
    players = []
    projections = {}
    player_id = 1
    for position, count in (("GK", 4), ("DEF", 8), ("MID", 8), ("FWD", 6)):
        for index in range(count):
            # Spread players across clubs so the max-three rule can be tested.
            team_id = (index % 6) + 1
            price = {"GK": 50, "DEF": 50, "MID": 55, "FWD": 60}[position]
            xp = {"GK": 5, "DEF": 6, "MID": 7, "FWD": 8}[position] + index
            player = _player(player_id, position, team_id, price, xp)
            players.append(player)
            projections[player_id] = {
                "horizon_expected_points": float(xp),
                "projection_complete": True,
            }
            player_id += 1
    return players, projections


def test_optimizer_returns_legal_15_player_squad():
    players, projections = _dataset()
    result = optimize_squad(
        players=players,
        projections=projections,
        budget=100.0,
        rules=FALLBACK_2026_27_RULES,
    )

    assert len(result.squad) == 15
    assert len(result.starting_xi) == 11
    assert validate_squad(result.squad, FALLBACK_2026_27_RULES) == []
    assert validate_starting_xi(result.starting_xi, FALLBACK_2026_27_RULES) == []
    assert result.squad_cost <= 100.0
    assert result.remaining_bank >= 0


def test_optimizer_respects_three_player_club_limit():
    players, projections = _dataset()
    # Make one club's players very attractive; the optimizer must still cap it.
    for player in players:
        if player["team_id"] == 1:
            projections[player["id"]]["horizon_expected_points"] += 100

    result = optimize_squad(
        players=players,
        projections=projections,
        budget=100.0,
        rules=FALLBACK_2026_27_RULES,
    )

    club_one_count = sum(1 for p in result.squad if p["team_id"] == 1)
    assert club_one_count <= 3


def test_optimizer_accounts_for_transfer_hits():
    players, projections = _dataset()
    current_squad = players[:15]

    result = optimize_squad(
        players=players,
        projections=projections,
        budget=100.0,
        rules=FALLBACK_2026_27_RULES,
        current_squad=current_squad,
        free_transfers=1,
    )

    expected_hit = max(0, result.transfer_count - 1) * 4
    assert result.transfer_hit == expected_hit
    assert result.net_strategy_value == result.starting_xi_expected_points - expected_hit


def test_incomplete_projection_is_not_silently_marked_complete():
    players, projections = _dataset()
    for projection in projections.values():
        projection["projection_complete"] = False

    result = optimize_squad(
        players=players,
        projections=projections,
        budget=100.0,
        rules=FALLBACK_2026_27_RULES,
    )

    assert not result.data_complete or result.warnings


def test_optimizer_is_deterministic():
    players, projections = _dataset()
    first = optimize_squad(
        players=players,
        projections=projections,
        budget=100.0,
        rules=FALLBACK_2026_27_RULES,
    )
    second = optimize_squad(
        players=players,
        projections=projections,
        budget=100.0,
        rules=FALLBACK_2026_27_RULES,
    )

    assert [p["id"] for p in first.squad] == [p["id"] for p in second.squad]
    assert [p["id"] for p in first.starting_xi] == [p["id"] for p in second.starting_xi]
