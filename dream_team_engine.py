"""
dream_team_engine.py

Official FPL Dream Team truth and strategic gap analysis.

Dream Team has two deliberately different roles in the Strategist:

1. Gameweek Dream Team: an observed weekly performance ceiling. It is useful
   for measuring how close our decisions came to the best realised XI, but it
   is not a pre-GW target that can be known without leakage.
2. Season-to-date Dream Team: an evolving long-horizon reference for squad
   construction and opportunity-gap analysis. Only the version published by
   FPL by the decision timestamp may be used for a pre-GW decision.

This module does not predict Dream Team players. It only normalises official
FPL Dream Team responses and compares observed outcomes with supplied manager
outcomes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence


MODEL_VERSION = "dream_team_v1"


@dataclass(frozen=True)
class DreamTeamPlayer:
    """One player in an official Dream Team snapshot."""

    player_id: int
    points: float
    position: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DreamTeamSnapshot:
    """Normalised official Dream Team snapshot."""

    scope: str
    gameweek: int | None
    players: tuple[DreamTeamPlayer, ...]
    total_points: float
    top_player_id: int | None
    top_player_points: float | None
    source_endpoint: str
    source_retrieved_at: str | None = None
    data_complete: bool = True
    warnings: tuple[str, ...] = ()
    model_version: str = MODEL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DreamTeamGap:
    """Observed gap between our outcome and an official Dream Team."""

    scope: str
    gameweek: int | None
    our_points: float
    dream_team_points: float
    total_gap: float
    overlap_player_ids: tuple[int, ...]
    missed_player_ids: tuple[int, ...]
    our_player_ids: tuple[int, ...]
    data_complete: bool
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        number = float(value)
        if number != number or number in (float("inf"), float("-inf")):
            return None
        return number
    except (TypeError, ValueError):
        return None


def _extract_team_rows(payload: Any) -> list[Mapping[str, Any]]:
    """Extract Dream Team player rows from known/compatible API shapes."""

    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, Mapping)]

    if not isinstance(payload, Mapping):
        return []

    for key in ("team", "players", "dream_team", "dreamteam"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, Mapping)]

    return []


def parse_dream_team(
    payload: Mapping[str, Any] | list[Mapping[str, Any]],
    *,
    scope: str,
    gameweek: int | None,
    source_endpoint: str,
    source_retrieved_at: str | None = None,
) -> DreamTeamSnapshot:
    """Normalise an official Dream Team API response.

    The official endpoint is the authority. The parser intentionally accepts
    minor response-shape variations so a change in wrapper shape does not
    force strategy code to change.
    """

    if scope not in {"gameweek", "season_to_date"}:
        raise ValueError("scope must be 'gameweek' or 'season_to_date'")
    if scope == "gameweek" and (gameweek is None or int(gameweek) < 1):
        raise ValueError("gameweek Dream Team requires a positive gameweek")
    if scope == "season_to_date" and gameweek is not None:
        raise ValueError("season_to_date Dream Team must not have a gameweek")

    rows = _extract_team_rows(payload)
    warnings: list[str] = []
    players: list[DreamTeamPlayer] = []

    for index, row in enumerate(rows):
        player_id = _as_int(
            row.get("element", row.get("player_id", row.get("id")))
        )
        points = _as_float(row.get("points", row.get("total_points")))
        position = _as_int(row.get("position", row.get("slot")))

        if player_id is None or points is None:
            warnings.append(
                f"Dream Team row {index} is missing a valid player ID or points value."
            )
            continue

        players.append(
            DreamTeamPlayer(
                player_id=player_id,
                points=points,
                position=position,
            )
        )

    top_player = payload.get("top_player") if isinstance(payload, Mapping) else None
    top_player_id = None
    top_player_points = None
    if isinstance(top_player, Mapping):
        top_player_id = _as_int(
            top_player.get("element", top_player.get("player_id", top_player.get("id")))
        )
        top_player_points = _as_float(top_player.get("points", top_player.get("total_points")))
    elif top_player is not None:
        top_player_id = _as_int(top_player)

    if top_player_id is None and players:
        top = max(players, key=lambda item: (item.points, -item.player_id))
        top_player_id = top.player_id
        top_player_points = top.points

    if top_player_points is None and top_player_id is not None:
        matching = next((p for p in players if p.player_id == top_player_id), None)
        if matching is not None:
            top_player_points = matching.points

    if not players:
        warnings.append("Official Dream Team payload contained no usable player rows.")

    # The endpoint is authoritative for the selected players. Summing the
    # supplied player points gives us a stable internal total even if the
    # response wrapper does not expose a separate total field.
    total_points = sum(player.points for player in players)

    return DreamTeamSnapshot(
        scope=scope,
        gameweek=(None if gameweek is None else int(gameweek)),
        players=tuple(players),
        total_points=total_points,
        top_player_id=top_player_id,
        top_player_points=top_player_points,
        source_endpoint=str(source_endpoint),
        source_retrieved_at=source_retrieved_at,
        data_complete=bool(players) and not warnings,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def compare_gameweek_dream_team(
    *,
    snapshot: DreamTeamSnapshot,
    our_points: float,
    our_player_ids: Sequence[int],
) -> DreamTeamGap:
    """Compare one realised manager Gameweek with that GW's Dream Team."""

    if snapshot.scope != "gameweek":
        raise ValueError("snapshot must be a gameweek Dream Team")
    our_ids = tuple(dict.fromkeys(int(pid) for pid in our_player_ids))
    dream_ids = tuple(player.player_id for player in snapshot.players)

    return DreamTeamGap(
        scope="gameweek",
        gameweek=snapshot.gameweek,
        our_points=float(our_points),
        dream_team_points=float(snapshot.total_points),
        total_gap=float(snapshot.total_points) - float(our_points),
        overlap_player_ids=tuple(pid for pid in dream_ids if pid in our_ids),
        missed_player_ids=tuple(pid for pid in dream_ids if pid not in our_ids),
        our_player_ids=our_ids,
        data_complete=snapshot.data_complete,
        warnings=snapshot.warnings,
    )


def compare_season_dream_team(
    *,
    snapshot: DreamTeamSnapshot,
    our_reference_points: float,
    our_player_ids: Sequence[int],
) -> DreamTeamGap:
    """Compare our supplied season-to-date reference with official S2D Dream Team.

    ``our_reference_points`` must be calculated from information valid at the
    same snapshot/decision timestamp. This function deliberately does not
    invent a cumulative score from a current squad alone.
    """

    if snapshot.scope != "season_to_date":
        raise ValueError("snapshot must be a season-to-date Dream Team")
    our_ids = tuple(dict.fromkeys(int(pid) for pid in our_player_ids))
    dream_ids = tuple(player.player_id for player in snapshot.players)

    return DreamTeamGap(
        scope="season_to_date",
        gameweek=None,
        our_points=float(our_reference_points),
        dream_team_points=float(snapshot.total_points),
        total_gap=float(snapshot.total_points) - float(our_reference_points),
        overlap_player_ids=tuple(pid for pid in dream_ids if pid in our_ids),
        missed_player_ids=tuple(pid for pid in dream_ids if pid not in our_ids),
        our_player_ids=our_ids,
        data_complete=snapshot.data_complete,
        warnings=snapshot.warnings,
    )
