"""
multi_gw_transfer_engine.py

Batch 11 — deterministic multi-gameweek transfer planning.

This module searches transfer sequences over a bounded planning horizon. It
uses the existing FPL squad rules and the Batch 10 legal squad optimizer's
projection contract, but does not call the FPL API or make captain/chip
choices.

The V1 planner evaluates zero or one transfer per gameweek. That is
intentional: it keeps the search transparent while correctly modelling free
transfer carry-over, transfer hits, bank evolution, squad legality, and
point projections by gameweek. A later version can expand the branching
factor after the contracts are validated.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from fpl_rules import FPLRules
from fpl_squad_rules import validate_squad


MODEL_VERSION = "multi_gw_transfer_v1"


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if number != number or number in (float("inf"), float("-inf")):
            return default
        return number
    except (TypeError, ValueError):
        return default


def _price_millions(player: dict[str, Any], field: str = "price") -> float:
    raw = _number(player.get(field), 0.0)
    return raw / 10.0 if raw >= 10.0 else raw


def _projection_for_gw(
    projections: dict[int, dict[str, Any]],
    player_id: int,
    gameweek: int,
) -> tuple[float, bool, tuple[str, ...]]:
    row = projections.get(int(player_id), {})
    fixtures = row.get("fixtures", [])
    matching = [f for f in fixtures if int(f.get("gameweek", -1)) == int(gameweek)]
    if not matching:
        return 0.0, False, (f"No projection available for player {player_id} in GW{gameweek}.",)
    points = sum(_number(f.get("expected_points")) for f in matching)
    complete = all(bool(f.get("data_complete")) for f in matching)
    warnings = tuple(
        warning
        for fixture in matching
        for warning in fixture.get("warnings", ())
    )
    return points, complete, tuple(dict.fromkeys(warnings))


def _player_sell_price(player: dict[str, Any]) -> float:
    """Use explicit FPL selling price when supplied; otherwise current price."""
    if player.get("sell_price") is not None:
        return _price_millions(player, "sell_price")
    if player.get("selling_price") is not None:
        return _price_millions(player, "selling_price")
    if player.get("purchase_price") is not None:
        # The optimizer deliberately does not invent FPL's profit-rounding rule.
        # A purchase price is therefore only a fallback when no explicit
        # selling price exists, and the result carries a warning.
        return _price_millions(player, "purchase_price")
    return _price_millions(player)


def _buy_price(player: dict[str, Any]) -> float:
    return _price_millions(player)


def _squad_cost(squad: Iterable[dict[str, Any]]) -> float:
    return sum(_buy_price(player) for player in squad)


def _next_free_transfers(
    free_transfers: int,
    transfers_used: int,
    rules: FPLRules,
) -> int:
    remaining = max(0, free_transfers - transfers_used)
    return min(rules.max_free_transfers, remaining + 1)


def _transfer_hit(
    transfers_used: int,
    free_transfers: int,
    rules: FPLRules,
) -> int:
    return max(0, transfers_used - free_transfers) * rules.extra_transfer_cost


def _replace_player(
    squad: list[dict[str, Any]],
    sell_id: int,
    buy: dict[str, Any],
) -> list[dict[str, Any]]:
    result = []
    replaced = False
    for player in squad:
        if int(player["id"]) == int(sell_id):
            result.append(dict(buy))
            replaced = True
        else:
            result.append(dict(player))
    if not replaced:
        raise ValueError(f"Player {sell_id} is not in the squad.")
    return result


def _candidate_transfers(
    *,
    squad: list[dict[str, Any]],
    market: list[dict[str, Any]],
    bank: float,
    rules: FPLRules,
    projections: dict[int, dict[str, Any]],
    gameweek: int,
    max_candidates: int,
) -> list[tuple[list[dict[str, Any]], float, int, tuple[str, ...]]]:
    squad_ids = {int(player["id"]) for player in squad}
    candidates: list[tuple[list[dict[str, Any]], float, int, tuple[str, ...]]] = []

    for sell in squad:
        sell_id = int(sell["id"])
        position = sell.get("position") or {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}.get(int(sell.get("position_id", 0)))
        sell_price = _player_sell_price(sell)
        for buy in market:
            buy_id = int(buy.get("id", -1))
            if buy_id in squad_ids or buy.get("id") is None:
                continue
            buy_position = buy.get("position") or {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}.get(int(buy.get("position_id", 0)))
            if buy_position != position:
                continue

            buy_price = _buy_price(buy)
            net_cost = buy_price - sell_price
            if net_cost > bank + 1e-9:
                continue

            new_squad = _replace_player(squad, sell_id, buy)
            errors = validate_squad(new_squad, rules)
            if errors:
                continue

            sell_xp, sell_complete, sell_warnings = _projection_for_gw(projections, sell_id, gameweek)
            buy_xp, buy_complete, buy_warnings = _projection_for_gw(projections, buy_id, gameweek)
            gain = buy_xp - sell_xp
            warnings = tuple(dict.fromkeys((*sell_warnings, *buy_warnings)))
            if not (sell_complete and buy_complete):
                warnings = tuple(dict.fromkeys((*warnings, "Transfer uses an incomplete projection.")))

            candidates.append((new_squad, gain, int(buy_id), warnings))

    candidates.sort(key=lambda row: (-row[1], row[2]))
    return candidates[:max_candidates]


@dataclass(frozen=True)
class MultiGWPlan:
    """Deterministic multi-GW transfer plan."""

    start_gameweek: int
    end_gameweek: int
    transfers: tuple[dict[str, Any], ...]
    projected_points: float
    transfer_hits: int
    net_value: float
    ending_bank: float
    ending_free_transfers: int
    data_complete: bool
    warnings: tuple[str, ...]
    model_version: str = MODEL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class _State:
    squad: tuple[dict[str, Any], ...]
    bank: float
    free_transfers: int
    projected_points: float
    transfer_hits: int
    transfers: tuple[dict[str, Any], ...]
    data_complete: bool
    warnings: tuple[str, ...]


def optimize_multi_gw_transfers(
    *,
    current_squad: list[dict[str, Any]],
    market_players: list[dict[str, Any]],
    projections: dict[int, dict[str, Any]],
    start_gameweek: int,
    horizon_gameweeks: list[int],
    bank: float,
    free_transfers: int,
    rules: FPLRules,
    beam_width: int = 50,
    max_transfer_candidates: int = 30,
) -> MultiGWPlan:
    """Find a bounded deterministic transfer sequence over several GWs."""
    if not horizon_gameweeks:
        raise ValueError("horizon_gameweeks must not be empty.")
    if any(int(gw) < int(start_gameweek) for gw in horizon_gameweeks):
        raise ValueError("horizon_gameweeks cannot precede start_gameweek.")
    if bank < 0:
        raise ValueError("bank cannot be negative.")
    if free_transfers < 0:
        raise ValueError("free_transfers cannot be negative.")
    if beam_width < 1 or max_transfer_candidates < 1:
        raise ValueError("beam_width and max_transfer_candidates must be positive.")

    initial_errors = validate_squad(current_squad, rules)
    if initial_errors:
        raise ValueError(f"Current squad is illegal: {initial_errors}")

    states = [
        _State(
            squad=tuple(dict(p) for p in current_squad),
            bank=float(bank),
            free_transfers=min(rules.max_free_transfers, int(free_transfers)),
            projected_points=0.0,
            transfer_hits=0,
            transfers=(),
            data_complete=True,
            warnings=(),
        )
    ]

    for gameweek in horizon_gameweeks:
        next_states: dict[tuple[Any, ...], _State] = {}
        for state in states:
            squad = [dict(p) for p in state.squad]
            gw_points = 0.0
            complete = state.data_complete
            warnings = list(state.warnings)
            for player in squad:
                points, player_complete, player_warnings = _projection_for_gw(
                    projections, int(player["id"]), int(gameweek)
                )
                gw_points += points
                complete = complete and player_complete
                warnings.extend(player_warnings)

            # Option 0: roll the transfer.
            rolled_ft = _next_free_transfers(state.free_transfers, 0, rules)
            rolled = _State(
                squad=tuple(squad),
                bank=state.bank,
                free_transfers=rolled_ft,
                projected_points=state.projected_points + gw_points,
                transfer_hits=state.transfer_hits,
                transfers=state.transfers,
                data_complete=complete,
                warnings=tuple(dict.fromkeys(warnings)),
            )
            key = (tuple(sorted(int(p["id"]) for p in rolled.squad)), round(rolled.bank, 4), rolled.free_transfers)
            next_states[key] = rolled

            # Option 1: make one legal transfer before this GW.
            for new_squad, immediate_gain, buy_id, transfer_warnings in _candidate_transfers(
                squad=squad,
                market=market_players,
                bank=state.bank,
                rules=rules,
                projections=projections,
                gameweek=int(gameweek),
                max_candidates=max_transfer_candidates,
            ):
                transfers_used = 1
                hit = _transfer_hit(transfers_used, state.free_transfers, rules)
                sell_ids = {int(p["id"]) for p in squad} - {int(p["id"]) for p in new_squad}
                sell_id = next(iter(sell_ids))
                sell_player = next(p for p in squad if int(p["id"]) == sell_id)
                buy_player = next(p for p in new_squad if int(p["id"]) == buy_id)
                cost = _buy_price(buy_player) - _player_sell_price(sell_player)
                new_bank = state.bank - cost
                if new_bank < -1e-9:
                    continue

                new_points = 0.0
                transfer_complete = True
                transfer_warn = list(transfer_warnings)
                for player in new_squad:
                    points, player_complete, player_warnings = _projection_for_gw(
                        projections, int(player["id"]), int(gameweek)
                    )
                    new_points += points
                    transfer_complete = transfer_complete and player_complete
                    transfer_warn.extend(player_warnings)

                transfer_record = {
                    "gameweek": int(gameweek),
                    "player_out": sell_id,
                    "player_in": buy_id,
                    "net_cost": cost,
                    "hit": hit,
                    "immediate_xp_change": immediate_gain,
                }
                candidate = _State(
                    squad=tuple(new_squad),
                    bank=max(0.0, new_bank),
                    free_transfers=_next_free_transfers(state.free_transfers, transfers_used, rules),
                    projected_points=state.projected_points + new_points - hit,
                    transfer_hits=state.transfer_hits + hit,
                    transfers=state.transfers + (transfer_record,),
                    data_complete=complete and transfer_complete,
                    warnings=tuple(dict.fromkeys((*warnings, *transfer_warn))),
                )
                key = (tuple(sorted(int(p["id"]) for p in candidate.squad)), round(candidate.bank, 4), candidate.free_transfers)
                previous = next_states.get(key)
                if previous is None or candidate.projected_points > previous.projected_points:
                    next_states[key] = candidate

        states = sorted(
            next_states.values(),
            key=lambda state: (-state.projected_points, state.transfer_hits, tuple(p["id"] for p in state.squad)),
        )[:beam_width]
        if not states:
            raise ValueError(f"No feasible multi-GW state remains after GW{gameweek}.")

    best = states[0]
    return MultiGWPlan(
        start_gameweek=int(start_gameweek),
        end_gameweek=int(horizon_gameweeks[-1]),
        transfers=best.transfers,
        projected_points=best.projected_points,
        transfer_hits=best.transfer_hits,
        net_value=best.projected_points,
        ending_bank=best.bank,
        ending_free_transfers=best.free_transfers,
        data_complete=best.data_complete,
        warnings=tuple(dict.fromkeys(best.warnings)),
    )
