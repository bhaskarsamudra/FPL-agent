"""
strategy_scenario_engine.py

Batch 18C - cross-horizon strategy reconciliation.

This module evaluates the same point-in-time strategic alternatives across the
Target Gameweek and three planning windows:

- target: the immediate Gameweek;
- short: target + next 2 Gameweeks (3 GW total);
- medium: target + next 4 Gameweeks (5 GW total);
- long: target + next 7 Gameweeks (8 GW total).

The horizons are evaluation lenses, not independent recommendations. The
module keeps the current decision action bounded to information available at
the decision timestamp. It does not pretend to know future prices, injuries,
team news, or future free-transfer state.

The strategic layer can therefore explain conflicts such as "B is best for
GW6, but C is better across the next three Gameweeks" without inventing a
future transfer sequence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

from captain_engine import build_captaincy_horizon


MODEL_VERSION = "strategy_scenario_v1"
SELECTION_BASIS = "PROVISIONAL_LONG_HORIZON_EVALUATION_ANCHOR"
HORIZON_DEFINITIONS = {
    "target": 1,
    "short": 3,
    "medium": 5,
    "long": 8,
}


@dataclass(frozen=True)
class HorizonStrategyScore:
    """One strategic option evaluated over one horizon."""

    horizon_name: str
    gameweeks: tuple[int, ...]
    projected_points: float
    captaincy_points: float
    transfer_hit_cost: float
    strategic_score: float
    data_complete: bool
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CrossHorizonStrategyOption:
    """One current decision alternative evaluated across all horizons."""

    option_id: str
    option_type: str
    description: str
    horizon_scores: tuple[HorizonStrategyScore, ...]
    data_complete: bool
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def score_for(self, horizon_name: str) -> HorizonStrategyScore | None:
        return next(
            (row for row in self.horizon_scores if row.horizon_name == horizon_name),
            None,
        )


@dataclass(frozen=True)
class CrossHorizonStrategyPlan:
    """Reconciled strategic view across target/3/5/8-GW horizons."""

    decision_gameweek: int
    target_gameweek: int
    horizons: tuple[tuple[str, tuple[int, ...]], ...]
    horizon_winners: tuple[tuple[str, str | None], ...]
    selected_option_id: str | None
    reconciliation: str
    rationale: tuple[str, ...]
    options: tuple[CrossHorizonStrategyOption, ...]
    data_complete: bool
    warnings: tuple[str, ...] = ()
    model_version: str = MODEL_VERSION
    selection_basis: str = SELECTION_BASIS

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def winner_for(self, horizon_name: str) -> str | None:
        return dict(self.horizon_winners).get(horizon_name)


def build_strategy_horizons(target_gameweek: int) -> tuple[tuple[str, tuple[int, ...]], ...]:
    """Build deterministic target/3/5/8 Gameweek evaluation windows."""

    target = int(target_gameweek)
    if target < 1:
        raise ValueError("target_gameweek must be positive.")

    return tuple(
        (
            name,
            tuple(range(target, target + length)),
        )
        for name, length in HORIZON_DEFINITIONS.items()
    )


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if number != number or number in (float("inf"), float("-inf")):
            return default
        return number
    except (TypeError, ValueError):
        return default


def _fixture_points(
    projections: dict[int, dict[str, Any]],
    player_id: int,
    gameweeks: Sequence[int],
) -> tuple[float, bool, tuple[str, ...]]:
    projection = projections.get(int(player_id))
    if projection is None:
        return 0.0, False, (f"No projection available for player {player_id}.",)

    requested = {int(gw) for gw in gameweeks}
    rows = [
        row
        for row in projection.get("fixtures", ())
        if int(row.get("gameweek", -1)) in requested
    ]
    if not rows:
        return 0.0, False, (
            f"No fixture projection available for player {player_id} in the requested horizon.",
        )

    points = sum(_number(row.get("expected_points")) for row in rows)
    observed_gameweeks = {int(row.get("gameweek", -1)) for row in rows}
    missing_gameweeks = sorted(requested - observed_gameweeks)
    complete = (
        bool(projection.get("projection_complete", False))
        and not missing_gameweeks
        and all(bool(row.get("data_complete", False)) for row in rows)
    )
    warnings = list(
        warning
        for row in rows
        for warning in row.get("warnings", ())
    )
    if missing_gameweeks:
        warnings.append(
            "Missing fixture projections for GW"
            + ", GW".join(str(gw) for gw in missing_gameweeks)
            + "."
        )
    return points, complete, tuple(dict.fromkeys(warnings))


def _scenario_squad(
    *,
    manager_squad: Sequence[dict[str, Any]],
    option: Any,
) -> list[dict[str, Any]]:
    squad = [dict(player) for player in manager_squad]
    transfer = getattr(option, "transfer", None)
    if transfer is None:
        return squad

    sell_id = int(transfer.sell_player_id)
    buy_id = int(transfer.buy_player_id)
    sell = next((row for row in squad if int(row["id"]) == sell_id), None)
    if sell is None:
        return squad

    replacement = {
        "id": buy_id,
        "name": transfer.buy_name,
        "position_id": int(transfer.position_id),
        "price": float(sell.get("price", 0.0)) + float(transfer.net_cost),
        "squad_position": int(sell.get("squad_position", 0)),
    }
    return [replacement if int(row["id"]) == sell_id else row for row in squad]


def _captain_bonus(
    *,
    squad: Sequence[dict[str, Any]],
    projections: dict[int, dict[str, Any]],
    gameweeks: Sequence[int],
) -> tuple[float, bool, tuple[str, ...]]:
    context = build_captaincy_horizon(
        squad=list(squad),
        projections=projections,
        horizon_gameweeks=gameweeks,
    )
    bonus = 0.0
    warnings = list(context.warnings)
    complete = context.data_complete
    for opportunity in context.opportunities:
        bonus += opportunity.best_expected_points * (context.captain_multiplier - 1.0)
        if not opportunity.data_complete:
            complete = False
            warnings.extend(opportunity.warnings)
    return bonus, complete, tuple(dict.fromkeys(warnings))


def _evaluate_option_horizon(
    *,
    option: Any,
    manager_squad: Sequence[dict[str, Any]],
    projections: dict[int, dict[str, Any]],
    gameweeks: Sequence[int],
    free_transfers_before: int,
    transfer_hit_points: float,
) -> HorizonStrategyScore:
    squad = _scenario_squad(manager_squad=manager_squad, option=option)
    active_squad = [
        player
        for player in squad
        if int(player.get("squad_position", 99)) <= 11
    ]
    warnings = list(getattr(option, "warnings", ()) or ())
    complete = bool(getattr(option, "data_complete", False))

    projected = 0.0
    for player in active_squad:
        points, player_complete, player_warnings = _fixture_points(
            projections,
            int(player["id"]),
            gameweeks,
        )
        projected += points
        complete = complete and player_complete
        warnings.extend(player_warnings)

    captain_bonus, captain_complete, captain_warnings = _captain_bonus(
        squad=active_squad,
        projections=projections,
        gameweeks=gameweeks,
    )
    complete = complete and captain_complete
    warnings.extend(captain_warnings)

    hit = 0.0
    if getattr(option, "option_type", None) == "transfer" and free_transfers_before < 1:
        hit = float(transfer_hit_points)
        complete = False
        warnings.append(
            f"No free transfer available; a {transfer_hit_points:.1f}-point hit applies."
        )

    return HorizonStrategyScore(
        horizon_name="",
        gameweeks=tuple(int(gw) for gw in gameweeks),
        projected_points=projected,
        captaincy_points=captain_bonus,
        transfer_hit_cost=hit,
        strategic_score=projected + captain_bonus - hit,
        data_complete=complete,
        warnings=tuple(dict.fromkeys(str(item) for item in warnings)),
    )


def _horizon_winner(
    options: Sequence[CrossHorizonStrategyOption],
    horizon_name: str,
) -> str | None:
    complete = [
        option
        for option in options
        if (score := option.score_for(horizon_name)) is not None and score.data_complete
    ]
    if not complete:
        return None
    return max(
        complete,
        key=lambda option: (
            option.score_for(horizon_name).strategic_score,  # type: ignore[union-attr]
            option.option_id,
        ),
    ).option_id


def evaluate_cross_horizon_strategies(
    *,
    decision_gameweek: int,
    target_gameweek: int,
    manager_squad: Sequence[dict[str, Any]],
    projections: dict[int, dict[str, Any]],
    options: Sequence[Any],
    free_transfers_before: int,
    transfer_hit_points: float = 4.0,
) -> CrossHorizonStrategyPlan:
    """Evaluate current strategy alternatives across all four planning lenses.

    The current Batch 18C selector uses the longest supported planning horizon
    as a *provisional evaluation anchor*. This is deliberately not the final
    cross-horizon optimizer: shorter horizons remain explicit so the strategist
    can surface immediate and medium-term trade-offs, while future multi-step
    transfer sequences and hybrid strategies remain for the subsequent
    scenario-generation/optimization layer.
    """

    horizons = build_strategy_horizons(target_gameweek)
    evaluated: list[CrossHorizonStrategyOption] = []

    for option in options:
        scores: list[HorizonStrategyScore] = []
        option_warnings = list(getattr(option, "warnings", ()) or ())
        option_complete = bool(getattr(option, "data_complete", False))

        for horizon_name, gameweeks in horizons:
            raw = _evaluate_option_horizon(
                option=option,
                manager_squad=manager_squad,
                projections=projections,
                gameweeks=gameweeks,
                free_transfers_before=free_transfers_before,
                transfer_hit_points=transfer_hit_points,
            )
            score = HorizonStrategyScore(
                horizon_name=horizon_name,
                gameweeks=raw.gameweeks,
                projected_points=raw.projected_points,
                captaincy_points=raw.captaincy_points,
                transfer_hit_cost=raw.transfer_hit_cost,
                strategic_score=raw.strategic_score,
                data_complete=raw.data_complete,
                warnings=raw.warnings,
            )
            scores.append(score)
            option_warnings.extend(score.warnings)
            option_complete = option_complete and score.data_complete

        evaluated.append(
            CrossHorizonStrategyOption(
                option_id=str(option.option_id),
                option_type=str(option.option_type),
                description=str(option.description),
                horizon_scores=tuple(scores),
                data_complete=option_complete,
                warnings=tuple(dict.fromkeys(option_warnings)),
            )
        )

    winners = tuple(
        (name, _horizon_winner(evaluated, name))
        for name, _ in horizons
    )
    long_winner = dict(winners).get("long")
    complete_options = [option for option in evaluated if option.data_complete]
    selected = next(
        (option for option in complete_options if option.option_id == long_winner),
        None,
    )

    rationale: list[str] = []
    reconciliation = "NO_COMPLETE_STRATEGY"
    if selected is not None:
        unique_winners = {winner for _, winner in winners if winner is not None}
        if len(unique_winners) == 1:
            reconciliation = "CONSISTENT_ACROSS_HORIZONS"
            rationale.append(
                f"{selected.option_id} is the complete-data leader across target, 3-GW, 5-GW and 8-GW views."
            )
        else:
            reconciliation = "LONG_HORIZON_LEADER_WITH_EXPLICIT_TRADE_OFFS"
            rationale.append(
                f"{selected.option_id} has the highest complete-data expected outcome over the 8-GW planning horizon."
            )
            for horizon_name, winner in winners:
                if winner and winner != selected.option_id:
                    rationale.append(
                        f"{winner} leads the {horizon_name} horizon, so the recommendation carries an explicit {horizon_name}-term trade-off."
                    )
            rationale.append(
                "Future exact transfer sequences are not committed because future prices, availability and team news are not known at the decision timestamp."
            )

    warnings = tuple(
        dict.fromkeys(
            warning
            for option in evaluated
            for warning in option.warnings
        )
    )
    return CrossHorizonStrategyPlan(
        decision_gameweek=int(decision_gameweek),
        target_gameweek=int(target_gameweek),
        horizons=tuple(horizons),
        horizon_winners=winners,
        selected_option_id=selected.option_id if selected else None,
        reconciliation=reconciliation,
        rationale=tuple(rationale),
        options=tuple(evaluated),
        data_complete=selected is not None,
        warnings=warnings,
    )
