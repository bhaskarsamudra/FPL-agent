"""
chip_engine.py

Counterfactual chip planning for the FPL Strategist.

The engine compares a no-chip baseline with a specific chip instance used in a
specific Gameweek. It does not declare a chip optimal from a simple DGW/BGW
rule. It exposes the projected incremental value, structured context, and data
quality so a later strategy layer can compare alternative timings.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any, Mapping, Sequence

from fpl_rules import ChipInstanceRule, FPLRules, FALLBACK_2026_27_RULES
from scenario_engine import Scenario, ScenarioResult, evaluate_scenario


MODEL_VERSION = "chip_v2"
SUPPORTED_CHIPS = ("wildcard", "freehit", "bboost", "3xc")


@dataclass(frozen=True)
class ChipScenarioEvaluation:
    """Auditable baseline-vs-chip counterfactual for one chip instance."""

    chip_instance_id: str
    chip: str
    target_gameweek: int
    horizon_start_gameweek: int
    horizon_end_gameweek: int
    baseline_projected_points: float
    chip_projected_points: float
    incremental_value: float
    data_complete: bool
    warnings: tuple[str, ...] = ()
    feature_context: dict[str, Any] | None = None
    model_version: str = MODEL_VERSION
    rules_version: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ChipAssessment:
    """Backward-compatible high-level chip assessment."""

    chip: str
    recommendation: str
    opportunity_value: float
    confidence: str
    reasons: tuple[str, ...]
    data_complete: bool
    chip_instance_id: str | None = None
    target_gameweek: int | None = None
    baseline_projected_points: float | None = None
    chip_projected_points: float | None = None
    incremental_value: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def available_chip_instances(
    *,
    rules: FPLRules,
    current_gameweek: int,
    used_instance_ids: Sequence[str] = (),
    used_chip_types: Sequence[str] = (),
) -> tuple[ChipInstanceRule, ...]:
    """Return chip instances currently available under season rules.

    ``used_instance_ids`` is the preferred precise input. ``used_chip_types``
    is retained as a compatibility fallback for older manager-state contracts
    that stored one entry per chip type rather than per chip instance.
    """

    used_ids = {str(item) for item in used_instance_ids}
    used_types = {str(item) for item in used_chip_types}
    current = int(current_gameweek)

    return tuple(
        instance
        for instance in rules.chip_instances
        if instance.is_available(current)
        and instance.instance_id not in used_ids
        and instance.chip_type not in used_types
    )


def _validate_target(
    chip_instance: ChipInstanceRule,
    target_gameweek: int,
    horizon_gameweeks: Sequence[int],
) -> None:
    target = int(target_gameweek)
    horizon = tuple(int(gw) for gw in horizon_gameweeks)
    if not horizon:
        raise ValueError("horizon_gameweeks must not be empty")
    if tuple(sorted(horizon)) != horizon:
        raise ValueError("horizon_gameweeks must be in ascending order")
    if target not in horizon:
        raise ValueError("target_gameweek must be inside horizon_gameweeks")
    if not chip_instance.is_available(target):
        raise ValueError(
            f"Chip instance {chip_instance.instance_id} is not available in GW{target}."
        )


def build_chip_scenario(
    *,
    baseline: Scenario,
    chip_instance: ChipInstanceRule,
    target_gameweek: int,
    horizon_gameweeks: Sequence[int],
    replacement_player_ids: Sequence[int] = (),
    replacement_gameweeks: Sequence[int] = (),
    bench_player_ids: Sequence[int] = (),
    captain_player_id: int | None = None,
    captain_multiplier: float | None = None,
) -> Scenario:
    """Build the atomic counterfactual scenario for a chip.

    For Free Hit the replacement players apply only to ``target_gameweek``.
    For Wildcard they apply to the supplied ``replacement_gameweeks`` (normally
    target GW through the planning horizon). Bench Boost adds the supplied bench
    players only in the target GW. Triple Captain changes only the target
    Gameweek captain multiplier.
    """

    horizon = tuple(int(gw) for gw in horizon_gameweeks)
    _validate_target(chip_instance, target_gameweek, horizon)
    chip = chip_instance.chip_type
    scenario = replace(
        baseline,
        scenario_id=f"{baseline.scenario_id}__{chip_instance.instance_id}__GW{target_gameweek}",
        scenario_type=f"chip_{chip}",
        description=(
            f"{chip_instance.instance_id} used in GW{target_gameweek}"
        ),
    )

    if chip == "3xc":
        if captain_player_id is None:
            raise ValueError("captain_player_id is required for Triple Captain")
        scenario = scenario.with_captain(
            target_gameweek,
            captain_player_id,
            captain_multiplier if captain_multiplier is not None else 3.0,
        )

    elif chip == "bboost":
        if not bench_player_ids:
            raise ValueError("bench_player_ids are required for Bench Boost")
        active = tuple(
            dict.fromkeys(
                scenario.players_for_gameweek(target_gameweek)
                + tuple(int(pid) for pid in bench_player_ids)
            )
        )
        scenario = scenario.with_gameweek_players((target_gameweek,), active)

    elif chip == "freehit":
        if not replacement_player_ids:
            raise ValueError("replacement_player_ids are required for Free Hit")
        scenario = scenario.with_gameweek_players(
            (target_gameweek,),
            tuple(int(pid) for pid in replacement_player_ids),
        )

    elif chip == "wildcard":
        if not replacement_player_ids:
            raise ValueError("replacement_player_ids are required for Wildcard")
        weeks = tuple(int(gw) for gw in replacement_gameweeks) or horizon[horizon.index(target_gameweek):]
        if any(gw not in horizon for gw in weeks):
            raise ValueError("replacement_gameweeks must be inside horizon_gameweeks")
        scenario = scenario.with_gameweek_players(
            weeks,
            tuple(int(pid) for pid in replacement_player_ids),
        )

    else:
        raise ValueError(f"Unsupported chip type: {chip}")

    return scenario


def evaluate_chip_counterfactual(
    *,
    chip_instance: ChipInstanceRule,
    target_gameweek: int,
    baseline_scenario: Scenario,
    chip_scenario: Scenario,
    projections: dict[int, dict[str, Any]],
    horizon_gameweeks: Sequence[int],
    feature_context: Mapping[str, Any] | None = None,
    rules_version: str = "unknown",
) -> ChipScenarioEvaluation:
    """Compare a chip scenario with the identical no-chip baseline."""

    _validate_target(chip_instance, target_gameweek, horizon_gameweeks)
    baseline_result: ScenarioResult = evaluate_scenario(
        scenario=baseline_scenario,
        projections=projections,
        gameweeks=list(horizon_gameweeks),
    )
    chip_result: ScenarioResult = evaluate_scenario(
        scenario=chip_scenario,
        projections=projections,
        gameweeks=list(horizon_gameweeks),
    )

    warnings = tuple(dict.fromkeys(baseline_result.warnings + chip_result.warnings))
    complete = baseline_result.data_complete and chip_result.data_complete

    return ChipScenarioEvaluation(
        chip_instance_id=chip_instance.instance_id,
        chip=chip_instance.chip_type,
        target_gameweek=int(target_gameweek),
        horizon_start_gameweek=int(horizon_gameweeks[0]),
        horizon_end_gameweek=int(horizon_gameweeks[-1]),
        baseline_projected_points=baseline_result.projected_points,
        chip_projected_points=chip_result.projected_points,
        incremental_value=chip_result.projected_points - baseline_result.projected_points,
        data_complete=complete,
        warnings=warnings,
        feature_context=dict(feature_context or {}),
        rules_version=rules_version,
    )


def rank_chip_opportunities(
    evaluations: Sequence[ChipScenarioEvaluation],
) -> tuple[ChipScenarioEvaluation, ...]:
    """Rank complete chip counterfactuals by projected incremental value.

    This is an evidence ordering, not a final strategic verdict. Incomplete
    evaluations are retained but placed after complete evaluations.
    """

    return tuple(
        sorted(
            evaluations,
            key=lambda item: (
                not item.data_complete,
                -item.incremental_value,
                item.target_gameweek,
                item.chip_instance_id,
            ),
        )
    )


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
    """Backward-compatible wrapper for the original chip interface.

    New strategy code should use chip instances and counterfactual evaluations.
    This wrapper intentionally retains the old transparent behavior so existing
    callers remain stable while Batch 15 is adopted incrementally.
    """

    fixture_count_by_gameweek = fixture_count_by_gameweek or {}
    assessments: list[ChipAssessment] = []

    for chip in available_chips:
        if chip not in SUPPORTED_CHIPS:
            continue

        reasons: list[str] = []
        complete = True

        if chip == "wildcard":
            opportunity = max(0.0, best_transfer_expected_gain)
            recommendation = "CONSIDER" if opportunity > 4.0 else "HOLD"
            reasons.append(
                "Legacy compatibility assessment: wildcard value is represented by the supplied restructuring gain."
            )
        elif chip == "freehit":
            blank_gws = [
                gw for gw in horizon_gameweeks
                if fixture_count_by_gameweek.get(gw, 1) == 0
            ]
            opportunity = float(len(blank_gws)) * 2.0
            recommendation = "CONSIDER" if blank_gws else "HOLD"
            reasons.append(f"Detected {len(blank_gws)} blank-style Gameweek(s) in the provided horizon.")
            if not fixture_count_by_gameweek:
                complete = False
                reasons.append("Blank/fixture map was not supplied.")
        elif chip == "bboost":
            opportunity = max(0.0, bench_expected_points)
            recommendation = "CONSIDER" if opportunity >= 10.0 else "HOLD"
            reasons.append(f"Legacy compatibility assessment: bench contribution {bench_expected_points:.2f}.")
        else:
            opportunity = max(0.0, captain_expected_points)
            recommendation = "CONSIDER" if opportunity >= 8.0 else "HOLD"
            reasons.append(f"Legacy compatibility assessment: captain projection {captain_expected_points:.2f}.")

        assessments.append(
            ChipAssessment(
                chip=chip,
                recommendation=recommendation,
                opportunity_value=opportunity,
                confidence="medium" if complete else "low",
                reasons=tuple(reasons),
                data_complete=complete,
            )
        )

    return assessments
