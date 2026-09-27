"""
captain_engine.py

Captain and vice-captain candidate evaluation.

This engine separates expected value from upside/differential context.
It does not make a rank prediction.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class CaptainCandidate:
    player_id: int
    player_name: str
    expected_points: float
    ownership_percent: float
    ceiling_proxy: float
    captain_score: float
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def rank_captain_candidates(
    *,
    squad: list[dict[str, Any]],
    projections: dict[int, dict[str, Any]],
    max_candidates: int = 5,
) -> list[CaptainCandidate]:
    """
    Rank captain candidates by expected points with a transparent ceiling
    proxy. Ownership is reported for context rather than used to create a
    hidden risk preference.
    """

    rows = []

    for player in squad:
        player_id = int(player["id"])
        projection = projections.get(player_id)

        if not projection:
            continue

        expected = float(projection.get("horizon_expected_points", 0.0))
        ownership = float(player.get("selected_by_percent", 0.0) or 0.0)

        # Current FPL data does not provide a validated player ceiling model.
        # Until that model exists, total horizon xP is the only defensible
        # quantitative core. The ceiling proxy is therefore explicitly
        # labelled as a placeholder diagnostic.
        ceiling_proxy = expected

        reasons = [
            f"Horizon expected points: {expected:.2f}.",
            f"Official FPL ownership: {ownership:.1f}%.",
        ]

        rows.append(
            CaptainCandidate(
                player_id=player_id,
                player_name=str(player.get("name", player_id)),
                expected_points=expected,
                ownership_percent=ownership,
                ceiling_proxy=ceiling_proxy,
                captain_score=expected,
                reasons=tuple(reasons),
            )
        )

    rows.sort(
        key=lambda row: (row.captain_score, row.expected_points),
        reverse=True,
    )

    return rows[:max_candidates]
