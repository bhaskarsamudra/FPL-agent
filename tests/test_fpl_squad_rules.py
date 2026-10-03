"""Tests for season-aware squad legality."""

from fpl_rules import FALLBACK_2026_27_RULES
from fpl_squad_rules import validate_squad, validate_starting_xi


def test_valid_squad():
    squad = []
    for player_id in range(1, 16):
        if player_id <= 2:
            position = "GK"
        elif player_id <= 7:
            position = "DEF"
        elif player_id <= 12:
            position = "MID"
        else:
            position = "FWD"

        squad.append(
            {
                "id": player_id,
                "position": position,
                "team_id": (player_id - 1) // 3 + 1,
            }
        )

    assert validate_squad(squad, FALLBACK_2026_27_RULES) == []


def test_invalid_squad_detects_limits():
    squad = [
        {"id": i, "position": "MID", "team_id": 1}
        for i in range(1, 16)
    ]
    errors = validate_squad(squad, FALLBACK_2026_27_RULES)

    assert any("Too many MID" in error for error in errors)
    assert any("Too many players from team 1" in error for error in errors)


def test_valid_starting_xi():
    xi = (
        [{"position": "GK"}]
        + [{"position": "DEF"} for _ in range(3)]
        + [{"position": "MID"} for _ in range(5)]
        + [{"position": "FWD"} for _ in range(2)]
    )
    assert validate_starting_xi(xi, FALLBACK_2026_27_RULES) == []


def test_invalid_starting_xi():
    xi = (
        [{"position": "GK"}]
        + [{"position": "DEF"} for _ in range(2)]
        + [{"position": "MID"} for _ in range(7)]
        + [{"position": "FWD"}]
    )
    errors = validate_starting_xi(xi, FALLBACK_2026_27_RULES)
    assert any("at least 3 DEF" in error for error in errors)
