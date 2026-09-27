"""
manager_state.py

Builds a structured, auditable manager state from official FPL API data.

The LLM must not be the source of truth for:
- squad
- bank
- free transfers
- chips
- rank
- team value
- current Gameweek

This module converts official API responses into a stable state contract.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class ManagerState:
    """Point-in-time structured state for one FPL manager."""

    team_id: int
    gameweek: int
    team_name: str
    manager_name: str

    bank: float
    team_value: float
    free_transfers: int

    overall_points: int
    overall_rank: int | None

    squad: tuple[dict[str, Any], ...]
    chips_played: dict[str, int]

    source: str = "official_fpl_api"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary."""

        return asdict(self)


def calculate_free_transfers(
    history: dict[str, Any],
    current_gameweek: int,
) -> int:
    """
    Calculate the manager's available free transfers.

    Wildcard/Free Hit transfer accounting is handled according to the
    official season-history event records already returned by FPL.

    We cap accumulated free transfers at five, matching current FPL rules.
    If FPL changes the rule, this function is the single place to update.
    """

    if not isinstance(history, dict):
        raise ValueError("history must be a dictionary.")

    current = history.get("current", [])
    chips = history.get("chips", [])

    unlimited_transfer_gws = {
        int(chip["event"])
        for chip in chips
        if chip.get("name") in {"wildcard", "freehit"}
        and chip.get("event") is not None
    }

    free_transfers = 1

    for row in sorted(
        current,
        key=lambda item: int(item.get("event", 0)),
    ):
        event = int(row.get("event", 0))

        if event > current_gameweek:
            continue

        if event == 1:
            free_transfers = 1
            continue

        transfers = int(row.get("event_transfers", 0) or 0)

        if event in unlimited_transfer_gws:
            transfers = 0

        free_transfers = min(
            5,
            max(0, free_transfers - transfers) + 1,
        )

    return max(1, free_transfers)


def build_manager_state(
    *,
    team_id: int,
    gameweek: int,
    picks_data: dict[str, Any],
    manager_data: dict[str, Any],
    history_data: dict[str, Any],
    player_universe: list[dict[str, Any]],
) -> ManagerState:
    """
    Build ManagerState from official FPL responses.

    The function refuses to fabricate missing squad/player information.
    """

    if not isinstance(picks_data, dict):
        raise ValueError("picks_data must be a dictionary.")
    if not isinstance(manager_data, dict):
        raise ValueError("manager_data must be a dictionary.")
    if not isinstance(history_data, dict):
        raise ValueError("history_data must be a dictionary.")

    picks = picks_data.get("picks")
    if not isinstance(picks, list) or len(picks) != 15:
        raise ValueError("Manager picks must contain exactly 15 players.")

    players_by_id = {
        int(player["id"]): player
        for player in player_universe
        if player.get("id") is not None
    }

    squad = []

    for pick in picks:
        player_id = int(pick["element"])

        if player_id not in players_by_id:
            raise ValueError(
                f"Player {player_id} from manager picks is missing "
                "from the official player universe."
            )

        player = dict(players_by_id[player_id])
        player["squad_position"] = int(pick.get("position", 0))
        player["multiplier"] = int(pick.get("multiplier", 1) or 1)
        player["is_captain"] = bool(pick.get("is_captain"))
        player["is_vice_captain"] = bool(pick.get("is_vice_captain"))
        player["purchase_price"] = int(pick.get("purchase_price", player["price"]))
        squad.append(player)

    entry_history = picks_data.get("entry_history", {})
    chips_played = {
        str(chip["name"]): int(chip.get("event", 0))
        for chip in history_data.get("chips", [])
        if chip.get("name")
    }

    bank = int(entry_history.get("bank", 0) or 0) / 10.0
    team_value = int(entry_history.get("value", 0) or 0) / 10.0

    first_name = manager_data.get("player_first_name", "")
    last_name = manager_data.get("player_last_name", "")

    return ManagerState(
        team_id=int(team_id),
        gameweek=int(gameweek),
        team_name=str(manager_data.get("name", f"Team {team_id}")),
        manager_name=f"{first_name} {last_name}".strip(),
        bank=bank,
        team_value=team_value,
        free_transfers=calculate_free_transfers(
            history_data,
            current_gameweek=gameweek,
        ),
        overall_points=int(
            manager_data.get("summary_overall_points", 0) or 0
        ),
        overall_rank=(
            int(manager_data["summary_overall_rank"])
            if manager_data.get("summary_overall_rank") is not None
            else None
        ),
        squad=tuple(squad),
        chips_played=chips_played,
    )
