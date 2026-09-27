"""
strategist_pipeline.py

Thin orchestration layer between verified manager state and strategy engines.

This module is intentionally deterministic. It provides the NO-DATA-NO-ANSWER
gate before the strategy engine is allowed to produce final recommendations.
"""

from __future__ import annotations

from typing import Any

from data_quality import validate_strategy_inputs
from strategy_engine import StrategyRecommendation, StrategyResult, build_strategy


def run_strategy_pipeline(
    *,
    manager_state: Any,
    market_players: list[dict[str, Any]],
    projections: dict[int, dict[str, Any]],
    available_chips: list[str],
    horizon_gameweeks: list[int],
    fixture_count_by_gameweek: dict[int, int] | None = None,
) -> StrategyResult:
    """
    Run the strategy engine only when critical inputs are present.

    Incomplete model projections are allowed as degraded information, but
    they must not be presented as fully verified final recommendations.
    """

    target_gameweek = int(getattr(manager_state, "gameweek", -1))
    quality = validate_strategy_inputs(
        manager_state=manager_state,
        projections=projections,
        target_gameweek=target_gameweek,
    )

    if not quality.ok:
        return StrategyResult(
            gameweek=target_gameweek,
            recommendations=(
                StrategyRecommendation(
                    action="NO_ANSWER",
                    priority="HIGH",
                    confidence="LOW",
                    summary="Critical strategy inputs are missing.",
                    evidence=quality.critical_missing,
                    source_status="blocked by data-quality gate",
                ),
            ),
            transfers=(),
            captains=(),
            chips=(),
            data_complete=False,
            warnings=quality.critical_missing + quality.warnings,
        )

    result = build_strategy(
        manager_state=manager_state,
        market_players=market_players,
        projections=projections,
        available_chips=available_chips,
        horizon_gameweeks=horizon_gameweeks,
        fixture_count_by_gameweek=fixture_count_by_gameweek,
    )

    if quality.warnings:
        return StrategyResult(
            gameweek=result.gameweek,
            recommendations=tuple(
                result.recommendations
                + (
                    StrategyRecommendation(
                        action="DEGRADED_DATA",
                        priority="HIGH",
                        confidence="LOW",
                        summary="Some model inputs are incomplete.",
                        evidence=quality.warnings,
                        source_status="degraded model inputs",
                    ),
                )
            ),
            transfers=result.transfers,
            captains=result.captains,
            chips=result.chips,
            data_complete=False,
            warnings=result.warnings + quality.warnings,
        )

    return result
