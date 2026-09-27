"""
Squad and starting-XI validation helpers.

These functions enforce game legality and do not make strategic decisions.
"""

from collections import Counter
from typing import Iterable

from fpl_rules import FPLRules


def validate_squad(
    players: Iterable[dict],
    rules: FPLRules,
) -> list[str]:
    """Validate a 15-player squad against the supplied season rules."""
    players = list(players)
    errors: list[str] = []

    if len(players) != rules.squad_size:
        errors.append(
            f"Squad must contain exactly {rules.squad_size} players; "
            f"received {len(players)}."
        )

    positions = Counter(player.get("position") for player in players)
    for position, maximum in rules.position_limits.items():
        if positions[position] > maximum:
            errors.append(
                f"Too many {position} players: {positions[position]} > {maximum}."
            )

    unknown_positions = set(positions) - set(rules.position_limits)
    if unknown_positions:
        errors.append(f"Unknown positions: {sorted(unknown_positions)}.")

    teams = Counter(player.get("team_id") for player in players)
    for team_id, count in teams.items():
        if team_id is None:
            errors.append("Every player must have a team_id.")
        elif count > rules.max_players_per_club:
            errors.append(
                f"Too many players from team {team_id}: "
                f"{count} > {rules.max_players_per_club}."
            )

    ids = [player.get("id") for player in players]
    if None in ids:
        errors.append("Every player must have an id.")
    if len(ids) != len(set(ids)):
        errors.append("Squad contains duplicate player IDs.")

    return errors


def validate_starting_xi(
    players: Iterable[dict],
    rules: FPLRules,
) -> list[str]:
    """Validate an 11-player starting XI against the supplied rules."""
    players = list(players)
    errors: list[str] = []

    if len(players) != rules.starting_xi_size:
        errors.append(
            f"Starting XI must contain exactly {rules.starting_xi_size} players; "
            f"received {len(players)}."
        )
        return errors

    positions = Counter(player.get("position") for player in players)

    if positions["GK"] != 1:
        errors.append(f"Starting XI must contain exactly 1 GK; found {positions['GK']}.")
    if positions["DEF"] < rules.min_defenders:
        errors.append(
            f"Starting XI must contain at least {rules.min_defenders} DEF; "
            f"found {positions['DEF']}."
        )
    if positions["MID"] < rules.min_midfielders:
        errors.append(
            f"Starting XI must contain at least {rules.min_midfielders} MID; "
            f"found {positions['MID']}."
        )
    if positions["FWD"] < rules.min_forwards:
        errors.append(
            f"Starting XI must contain at least {rules.min_forwards} FWD; "
            f"found {positions['FWD']}."
        )

    return errors
