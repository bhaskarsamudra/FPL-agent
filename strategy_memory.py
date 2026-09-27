"""
strategy_memory.py

Structured strategic memory.

Conversation text is not treated as authoritative state. This module stores
decision snapshots and outcomes in a JSON-safe structure so the strategy
engine can later learn from actual results without relying on LLM memory.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class DecisionSnapshot:
    gameweek: int
    timestamp: str
    action: str
    player_in: int | None
    player_out: int | None
    captain_id: int | None
    chip: str | None
    expected_gain: float | None
    confidence: str
    rationale: tuple[str, ...]
    outcome_points: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def append_decision(
    memory: list[dict[str, Any]],
    decision: DecisionSnapshot,
) -> list[dict[str, Any]]:
    """Return a new memory list with one validated decision appended."""

    if not isinstance(memory, list):
        raise ValueError("memory must be a list.")

    return [
        *memory,
        decision.to_dict(),
    ]


def record_outcome(
    memory: list[dict[str, Any]],
    *,
    gameweek: int,
    outcome_points: float,
) -> list[dict[str, Any]]:
    """
    Attach the observed outcome to the latest matching decision.

    If no matching decision exists, the memory is returned unchanged.
    """

    updated = [dict(row) for row in memory]

    for row in reversed(updated):
        if int(row.get("gameweek", -1)) == int(gameweek):
            row["outcome_points"] = float(outcome_points)
            break

    return updated
