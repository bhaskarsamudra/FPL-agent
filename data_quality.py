"""
data_quality.py

Central NO-DATA-NO-ANSWER gates for the strategist.

A missing or stale critical input must reduce recommendation confidence or
block the recommendation entirely. The LLM must never be used to fill a
missing factual field.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DataQuality:
    ok: bool
    critical_missing: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def status(self) -> str:
        if not self.ok:
            return "BLOCKED"
        if self.warnings:
            return "DEGRADED"
        return "OK"


def validate_strategy_inputs(
    *,
    manager_state: Any,
    projections: dict[int, dict[str, Any]],
    target_gameweek: int,
) -> DataQuality:
    """Validate the minimum inputs required before final strategy output."""

    missing = []
    warnings = []

    if manager_state is None:
        missing.append("manager_state")

    if int(getattr(manager_state, "gameweek", -1)) != int(target_gameweek):
        missing.append("manager_state_gameweek")

    squad = list(getattr(manager_state, "squad", ())) if manager_state else []
    if len(squad) != 15:
        missing.append("15_player_squad")

    for player in squad:
        player_id = int(player["id"])
        projection = projections.get(player_id)

        if not projection:
            missing.append(f"projection:{player_id}")
            continue

        if not projection.get("projection_complete", False):
            warnings.append(
                f"projection_incomplete:{player_id}"
            )

    return DataQuality(
        ok=not missing,
        critical_missing=tuple(missing),
        warnings=tuple(warnings),
    )
