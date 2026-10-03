"""
strategy_selection_policy.py

Batch 18D-D2 - deterministic strategy selection policy.

The policy selects among already-evaluated StrategyScenarioComparison objects.
It does not recalculate projections and does not introduce arbitrary weighted
horizon scores. Horizon performance is treated as four equally important
lenses using rank-based balance; transfer hit cost and retained flexibility are
used as explicit tie-break dimensions.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Sequence

from strategy_selection import StrategyScenarioComparison, StrategySelection


POLICY_VERSION = "strategy_selection_policy_v1"
SELECTION_BASIS = "BALANCED_HORIZON_RANK_POLICY_V1"
NO_COMPLETE_BASIS = "NO_COMPLETE_CANDIDATE"
HORIZONS = ("target", "short", "medium", "long")


def _rank_candidates(
    candidates: Sequence[StrategyScenarioComparison],
    horizon_name: str,
) -> dict[str, int]:
    """Rank complete candidates for one horizon, highest score first."""
    available = [
        item
        for item in candidates
        if item.data_complete and item.score_for(horizon_name) is not None
    ]
    ordered = sorted(
        available,
        key=lambda item: (
            -(item.score_for(horizon_name) or float("-inf")),
            item.hit_cost,
            -item.remaining_transfer_flexibility,
            item.scenario_id,
        ),
    )
    return {item.scenario_id: index + 1 for index, item in enumerate(ordered)}


def _selection_key(
    candidate: StrategyScenarioComparison,
    ranks: dict[str, dict[str, int]],
) -> tuple:
    """Build a deterministic, weight-free comparison key.

    Horizon ranks are sorted from worst to best. This is a maximin-style
    balance rule: the weakest horizon position is protected first, then the
    overall rank profile, without allowing the 8-GW horizon to dominate.
    """
    candidate_ranks = [ranks[name][candidate.scenario_id] for name in HORIZONS]
    return (
        tuple(sorted(candidate_ranks, reverse=True)),
        sum(candidate_ranks),
        candidate.hit_cost,
        -candidate.remaining_transfer_flexibility,
        candidate.scenario_id,
    )


def apply_strategy_selection_policy(
    selection: StrategySelection,
) -> StrategySelection:
    """Apply D2's deterministic, weight-free selection policy.

    The policy first seeks the strongest balanced rank profile across Target,
    3-GW, 5-GW and 8-GW. Hit cost and retained transfer flexibility resolve
    otherwise equivalent profiles. It never invents future actions or
    recalculates projection values.
    """
    complete = tuple(item for item in selection.candidates if item.data_complete)
    if not complete:
        warning = "No complete strategy scenario is available for deterministic selection."
        return replace(
            selection,
            selected_scenario_id=None,
            selection_basis=NO_COMPLETE_BASIS,
            model_version=POLICY_VERSION,
            warnings=tuple(dict.fromkeys((*selection.warnings, warning))),
            selection_rationale=(),
            data_complete=False,
        )

    ranks = {horizon: _rank_candidates(complete, horizon) for horizon in HORIZONS}
    eligible = [
        candidate
        for candidate in complete
        if all(candidate.scenario_id in ranks[horizon] for horizon in HORIZONS)
    ]
    if not eligible:
        warning = "No complete strategy scenario has complete scores across all four horizons."
        return replace(
            selection,
            selected_scenario_id=None,
            selection_basis=NO_COMPLETE_BASIS,
            model_version=POLICY_VERSION,
            warnings=tuple(dict.fromkeys((*selection.warnings, warning))),
            selection_rationale=(),
            data_complete=False,
        )

    selected = min(eligible, key=lambda item: _selection_key(item, ranks))
    selected_ranks = tuple(ranks[horizon][selected.scenario_id] for horizon in HORIZONS)
    rationale = (
        f"Selected {selected.scenario_id} using balanced horizon rank profile "
        f"(target/3-GW/5-GW/8-GW ranks: {selected_ranks}).",
        "The policy does not assign arbitrary point weights to horizons; the 8-GW horizon cannot dominate selection by itself.",
        f"Transfer hit cost ({selected.hit_cost:.2f}) and retained transfer flexibility "
        f"({selected.remaining_transfer_flexibility}) are deterministic tie-break dimensions.",
    )
    return replace(
        selection,
        selected_scenario_id=selected.scenario_id,
        selection_basis=SELECTION_BASIS,
        model_version=POLICY_VERSION,
        warnings=selection.warnings,
        selection_rationale=rationale,
        data_complete=True,
    )
