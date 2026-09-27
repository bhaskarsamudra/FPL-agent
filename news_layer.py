"""
news_layer.py

Structured player news/status layer based on official FPL bootstrap data.

This is deliberately limited to information actually supplied by FPL:
status, availability percentages and the API's player news text.

External journalism can be added later through a separate provider without
changing this contract.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class PlayerNewsSignal:
    player_id: int
    status: str
    news: str
    chance_this_round: int | None
    chance_next_round: int | None
    actionable: bool
    source: str = "official_fpl_api"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_player_news_signals(
    players: list[dict[str, Any]],
) -> dict[int, PlayerNewsSignal]:
    """Build auditable news/status signals from normalized player data."""

    result = {}

    for player in players:
        player_id = int(player["id"])
        news = str(player.get("news") or "").strip()
        status = str(player.get("status") or "a")

        chance_this = player.get("chance_of_playing_this_round")
        chance_next = player.get("chance_of_playing_next_round")

        chance_this_int = (
            int(chance_this) if chance_this is not None else None
        )
        chance_next_int = (
            int(chance_next) if chance_next is not None else None
        )

        actionable = bool(
            news
            or status not in {"a"}
            or (
                chance_this_int is not None
                and chance_this_int < 100
            )
            or (
                chance_next_int is not None
                and chance_next_int < 100
            )
        )

        result[player_id] = PlayerNewsSignal(
            player_id=player_id,
            status=status,
            news=news,
            chance_this_round=chance_this_int,
            chance_next_round=chance_next_int,
            actionable=actionable,
        )

    return result
