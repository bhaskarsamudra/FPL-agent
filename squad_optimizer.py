"""
squad_optimizer.py

Deterministic legal FPL squad optimizer.

This module is responsible for generating legal 15-player squads from a
candidate pool and selecting the best legal starting XI for each candidate.
It does not make captain/chip/rival decisions and does not call the FPL API.

The optimizer uses a bounded beam search so that the search remains
transparent and deterministic while avoiding an unbounded combinatorial
search across the full player market.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from fpl_rules import FPLRules
from fpl_squad_rules import validate_squad, validate_starting_xi


POSITION_ORDER = ("GK", "DEF", "MID", "FWD")


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if number != number or number in (float("inf"), float("-inf")):
            return default
        return number
    except (TypeError, ValueError):
        return default


def _price_millions(player: dict[str, Any]) -> float:
    """Normalize FPL prices that may be supplied as 100ths or millions."""
    raw = _number(player.get("price"), 0.0)
    return raw / 10.0 if raw >= 10.0 else raw


def _position(player: dict[str, Any]) -> str:
    """Return the canonical position code for an optimizer player."""
    value = player.get("position")
    if value in POSITION_ORDER:
        return str(value)

    position_id = int(_number(player.get("position_id", player.get("element_type", 0)), 0))
    return {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}.get(position_id, "")


def _player_projection(
    player: dict[str, Any],
    projections: dict[int, dict[str, Any]],
) -> tuple[float, bool]:
    row = projections.get(int(player["id"]), {})
    value = _number(row.get("horizon_expected_points"), 0.0)
    complete = bool(row.get("projection_complete", False))
    return value, complete


def _player_key(player: dict[str, Any]) -> int:
    return int(player["id"])


def _with_projection_fields(
    player: dict[str, Any],
    projections: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    result = dict(player)
    result["position"] = _position(player)
    result["price_millions"] = _price_millions(player)
    result["horizon_expected_points"] = _player_projection(player, projections)[0]
    result["projection_complete"] = _player_projection(player, projections)[1]
    return result


def _best_starting_xi(
    squad: list[dict[str, Any]],
    rules: FPLRules,
) -> tuple[list[dict[str, Any]], float]:
    """Select the highest-scoring legal XI from a legal 15-player squad."""
    gks = sorted(
        (p for p in squad if p["position"] == "GK"),
        key=lambda p: (-p["horizon_expected_points"], p["id"]),
    )
    defs = sorted(
        (p for p in squad if p["position"] == "DEF"),
        key=lambda p: (-p["horizon_expected_points"], p["id"]),
    )
    mids = sorted(
        (p for p in squad if p["position"] == "MID"),
        key=lambda p: (-p["horizon_expected_points"], p["id"]),
    )
    fwds = sorted(
        (p for p in squad if p["position"] == "FWD"),
        key=lambda p: (-p["horizon_expected_points"], p["id"]),
    )

    # FPL allows any legal formation satisfying the minimum position counts.
    # Enumerate the small number of possible DEF/MID/FWD splits and keep the
    # highest-scoring players for each split. This is exact for a 15-player
    # squad and remains tiny compared with full squad search.
    best: tuple[list[dict[str, Any]], float] | None = None

    for defender_count in range(rules.min_defenders, 6):
        for midfielder_count in range(rules.min_midfielders, 6):
            forward_count = rules.starting_xi_size - 1 - defender_count - midfielder_count
            if forward_count < rules.min_forwards or forward_count > 3:
                continue
            if defender_count > len(defs) or midfielder_count > len(mids) or forward_count > len(fwds):
                continue

            xi = (
                gks[:1]
                + defs[:defender_count]
                + mids[:midfielder_count]
                + fwds[:forward_count]
            )
            if len(xi) != rules.starting_xi_size:
                continue
            if validate_starting_xi(xi, rules):
                continue

            score = sum(p["horizon_expected_points"] for p in xi)
            if best is None or score > best[1] or (
                score == best[1] and tuple(p["id"] for p in xi) < tuple(p["id"] for p in best[0])
            ):
                best = (xi, score)

    if best is None:
        raise ValueError("No legal starting XI can be formed from the supplied squad.")

    return best


@dataclass(frozen=True)
class SquadOptimizationResult:
    """Best legal squad and its deterministic objective details."""

    squad: tuple[dict[str, Any], ...]
    starting_xi: tuple[dict[str, Any], ...]
    squad_cost: float
    remaining_bank: float
    starting_xi_expected_points: float
    squad_expected_points: float
    transfer_count: int
    transfer_hit: int
    net_strategy_value: float
    data_complete: bool
    warnings: tuple[str, ...]
    optimizer_version: str = "squad_optimizer_v1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class _BeamState:
    players: tuple[dict[str, Any], ...]
    cost: float
    projection_sum: float


def _candidate_pool(
    *,
    players: Iterable[dict[str, Any]],
    projections: dict[int, dict[str, Any]],
    rules: FPLRules,
    current_squad: Iterable[dict[str, Any]] | None,
    candidate_limit_per_position: int,
) -> dict[str, list[dict[str, Any]]]:
    """Prepare a bounded, deterministic pool while always retaining the current squad."""
    unique: dict[int, dict[str, Any]] = {}
    for raw in players:
        if "id" not in raw:
            continue
        player = _with_projection_fields(raw, projections)
        if player["position"] not in POSITION_ORDER or player["team_id"] is None:
            continue
        unique[int(player["id"])] = player

    current_ids = {int(p["id"]) for p in (current_squad or ()) if "id" in p}
    pool: dict[str, list[dict[str, Any]]] = {position: [] for position in POSITION_ORDER}

    for position in POSITION_ORDER:
        rows = [p for p in unique.values() if p["position"] == position]
        rows.sort(key=lambda p: (-p["horizon_expected_points"], p["id"]))
        retained = [p for p in rows if p["id"] in current_ids]
        retained_ids = {p["id"] for p in retained}
        top = [p for p in rows if p["id"] not in retained_ids][:candidate_limit_per_position]
        selected = retained + top
        required = rules.position_limits[position]
        if len(selected) < required:
            raise ValueError(
                f"Insufficient {position} candidates: need at least {required}, found {len(selected)}."
            )
        pool[position] = selected

    return pool


def _beam_squads(
    *,
    pool: dict[str, list[dict[str, Any]]],
    rules: FPLRules,
    budget: float,
    beam_width: int,
) -> list[list[dict[str, Any]]]:
    """Build legal 15-player squads using deterministic bounded beam search."""
    states = [_BeamState(players=(), cost=0.0, projection_sum=0.0)]
    slot_positions = [
        "GK", "GK",
        "DEF", "DEF", "DEF", "DEF", "DEF",
        "MID", "MID", "MID", "MID", "MID",
        "FWD", "FWD", "FWD",
    ]

    for position in slot_positions:
        next_states: dict[tuple[int, ...], _BeamState] = {}
        for state in states:
            used_ids = {int(p["id"]) for p in state.players}
            club_counts: dict[int, int] = {}
            for p in state.players:
                club = int(p["team_id"])
                club_counts[club] = club_counts.get(club, 0) + 1

            for player in pool[position]:
                player_id = int(player["id"])
                if player_id in used_ids:
                    continue
                club = int(player["team_id"])
                if club_counts.get(club, 0) >= rules.max_players_per_club:
                    continue

                cost = state.cost + float(player["price_millions"])
                if cost > budget + 1e-9:
                    continue

                players = state.players + (player,)

                # Do not retain a partial squad that can no longer be completed
                # under the three-player-per-club rule. This is a feasibility
                # check only; it does not rank or otherwise bias candidates.
                remaining_slots = len(slot_positions) - (len(players))
                updated_counts = dict(club_counts)
                updated_counts[club] = updated_counts.get(club, 0) + 1
                remaining_capacity = sum(
                    max(0, rules.max_players_per_club - count)
                    for count in updated_counts.values()
                )
                known_clubs = set(updated_counts)
                remaining_capacity += sum(
                    max(0, rules.max_players_per_club)
                    for candidate in pool.values()
                    for candidate_club in {int(row["team_id"]) for row in candidate}
                    if candidate_club not in known_clubs
                )
                if remaining_slots > remaining_capacity:
                    continue

                key = tuple(sorted(int(p["id"]) for p in players))
                candidate = _BeamState(
                    players=players,
                    cost=cost,
                    projection_sum=state.projection_sum + player["horizon_expected_points"],
                )
                previous = next_states.get(key)
                if previous is None or candidate.projection_sum > previous.projection_sum:
                    next_states[key] = candidate

        states = sorted(
            next_states.values(),
            key=lambda state: (-state.projection_sum, state.cost, tuple(p["id"] for p in state.players)),
        )[:beam_width]
        if not states:
            return []

    return [list(state.players) for state in states]


def optimize_squad(
    *,
    players: list[dict[str, Any]],
    projections: dict[int, dict[str, Any]],
    budget: float,
    rules: FPLRules,
    current_squad: list[dict[str, Any]] | None = None,
    free_transfers: int = 0,
    candidate_limit_per_position: int = 12,
    beam_width: int = 2000,
) -> SquadOptimizationResult:
    """
    Find the best legal 15-player squad under the supplied budget.

    Objective:
        best legal starting-XI expected points - transfer hit.

    ``players`` must contain enough candidates to build a legal squad. Current
    squad players are always retained in the bounded candidate pool so a
    transfer plan can be evaluated without accidentally dropping an existing
    player from consideration.
    """
    if budget < 0:
        raise ValueError("Budget cannot be negative.")
    if free_transfers < 0:
        raise ValueError("Free transfers cannot be negative.")
    if candidate_limit_per_position < 1 or beam_width < 1:
        raise ValueError("Candidate limit and beam width must be positive.")

    current_ids = {int(p["id"]) for p in (current_squad or ())}
    pool = _candidate_pool(
        players=players,
        projections=projections,
        rules=rules,
        current_squad=current_squad,
        candidate_limit_per_position=candidate_limit_per_position,
    )

    flattened = [player for rows in pool.values() for player in rows]
    cheapest_by_position = {
        position: min(p["price_millions"] for p in rows)
        for position, rows in pool.items()
    }
    minimum_cost = sum(
        cheapest_by_position[position] * rules.position_limits[position]
        for position in POSITION_ORDER
    )
    if minimum_cost > budget + 1e-9:
        raise ValueError(
            f"Budget {budget:.1f} is below the minimum candidate-pool cost {minimum_cost:.1f}."
        )

    squads = _beam_squads(
        pool=pool,
        rules=rules,
        budget=budget,
        beam_width=beam_width,
    )
    if not squads:
        raise ValueError("No legal squad could be constructed within the supplied budget.")

    best_result: SquadOptimizationResult | None = None
    for squad in squads:
        squad_errors = validate_squad(squad, rules)
        if squad_errors:
            continue

        starting_xi, xi_points = _best_starting_xi(squad, rules)
        squad_points = sum(p["horizon_expected_points"] for p in squad)
        squad_ids = {int(p["id"]) for p in squad}
        transfers = len(squad_ids - current_ids) if current_ids else 0
        transfer_hit = max(0, transfers - free_transfers) * rules.extra_transfer_cost
        cost = sum(p["price_millions"] for p in squad)
        complete = all(bool(p["projection_complete"]) for p in squad)
        warnings: list[str] = []
        if not complete:
            warnings.append("One or more squad projections are incomplete.")

        result = SquadOptimizationResult(
            squad=tuple(sorted(squad, key=lambda p: (POSITION_ORDER.index(p["position"]), p["id"]))),
            starting_xi=tuple(sorted(starting_xi, key=lambda p: (POSITION_ORDER.index(p["position"]), p["id"]))),
            squad_cost=cost,
            remaining_bank=budget - cost,
            starting_xi_expected_points=xi_points,
            squad_expected_points=squad_points,
            transfer_count=transfers,
            transfer_hit=transfer_hit,
            net_strategy_value=xi_points - transfer_hit,
            data_complete=complete,
            warnings=tuple(warnings),
        )

        if best_result is None or (
            result.net_strategy_value,
            result.starting_xi_expected_points,
            result.squad_expected_points,
            -result.squad_cost,
            tuple(p["id"] for p in result.squad),
        ) > (
            best_result.net_strategy_value,
            best_result.starting_xi_expected_points,
            best_result.squad_expected_points,
            -best_result.squad_cost,
            tuple(p["id"] for p in best_result.squad),
        ):
            best_result = result

    if best_result is None:
        raise ValueError("No legal squad passed the validation rules.")

    return best_result
