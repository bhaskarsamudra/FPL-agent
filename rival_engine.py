"""
rival_engine.py

Mini-league and rival analytics.

The rival layer provides context to the universal FPL strategy engine.
It does not create a separate optimization objective for each league.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class RivalSnapshot:
    entry_id: int
    rank: int
    team_name: str
    manager_name: str
    total_points: int
    gap_to_user: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_rival_snapshots(
    *,
    standings: list[dict[str, Any]],
    user_team_id: int,
) -> list[RivalSnapshot]:
    """Convert official classic-league standings into auditable snapshots."""

    user = next(
        (
            row for row in standings
            if int(row.get("entry", -1)) == int(user_team_id)
        ),
        None,
    )

    if user is None:
        raise ValueError("User team was not found in league standings.")

    user_total = int(user.get("total", 0))

    rows = []

    for row in standings:
        entry_id = int(row.get("entry", -1))
        if entry_id == int(user_team_id):
            continue

        rows.append(
            RivalSnapshot(
                entry_id=entry_id,
                rank=int(row.get("rank", 0)),
                team_name=str(row.get("entry_name", "")),
                manager_name=str(row.get("player_name", "")),
                total_points=int(row.get("total", 0)),
                gap_to_user=user_total - int(row.get("total", 0)),
            )
        )

    return sorted(rows, key=lambda item: item.rank)


def identify_nearest_rivals(
    rivals: list[RivalSnapshot],
    *,
    limit: int = 5,
) -> list[RivalSnapshot]:
    """Return the nearest standings competitors by absolute point gap."""

    return sorted(
        rivals,
        key=lambda rival: (abs(rival.gap_to_user), rival.rank),
    )[:max(0, limit)]
