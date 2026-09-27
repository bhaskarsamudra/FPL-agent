"""
chip_engine.py

Chip decision framework.

This module does not claim that a chip is optimal merely because one
Gameweek has a high projected score. It compares the candidate chip with
the current no-chip baseline and exposes missing data.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class ChipAssessment:
    chip: str
    recommendation: str
    opportunity_value: float
    confidence: str
    reasons: tuple[str, ...]
    data_complete: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SUPPORTED_CHIPS = ("wildcard", "freehit", "bboost", "3xc")


def assess_chips(
    *,
    available_chips: list[str],
    horizon_gameweeks: list[int],
    current_squad_expected_points: float,
    best_transfer_expected_gain: float,
    bench_expected_points: float,
    captain_expected_points: float,
    fixture_count_by_gameweek: dict[int, int] | None = None,
) -> list[ChipAssessment]:
    """
    Produce transparent chip assessments.

    This is deliberately a framework, not a final chip optimizer. The full
    chip model needs validated double/blank Gameweek opportunity modelling.
    """

    fixture_count_by_gameweek = fixture_count_by_gameweek or {}
    assessments = []

    for chip in available_chips:
        if chip not in SUPPORTED_CHIPS:
            continue

        reasons = []
        complete = True

        if chip == "wildcard":
            opportunity = max(0.0, best_transfer_expected_gain)
            recommendation = (
                "CONSIDER"
                if opportunity > 4.0
                else "HOLD"
            )
            reasons.append(
                "Wildcard value currently comes from the quality of the "
                "best multi-player restructuring opportunity."
            )

        elif chip == "freehit":
            blank_gws = [
                gw for gw in horizon_gameweeks
                if fixture_count_by_gameweek.get(gw, 1) == 0
            ]
            opportunity = float(len(blank_gws)) * 2.0
            recommendation = "CONSIDER" if blank_gws else "HOLD"
            reasons.append(
                f"Detected {len(blank_gws)} blank-style Gameweek(s) in the "
                "provided horizon."
            )
            if not fixture_count_by_gameweek:
                complete = False
                reasons.append("Blank/fixture map was not supplied.")

        elif chip == "bboost":
            opportunity = max(0.0, bench_expected_points)
            recommendation = (
                "CONSIDER" if opportunity >= 10.0 else "HOLD"
            )
            reasons.append(
                f"Current bench projected contribution: {bench_expected_points:.2f}."
            )

        else:  # Triple Captain
            opportunity = max(0.0, captain_expected_points)
            recommendation = (
                "CONSIDER" if opportunity >= 8.0 else "HOLD"
            )
            reasons.append(
                f"Captain candidate horizon projection: {captain_expected_points:.2f}."
            )

        confidence = "medium" if complete else "low"

        assessments.append(
            ChipAssessment(
                chip=chip,
                recommendation=recommendation,
                opportunity_value=opportunity,
                confidence=confidence,
                reasons=tuple(reasons),
                data_complete=complete,
            )
        )

    return assessments
