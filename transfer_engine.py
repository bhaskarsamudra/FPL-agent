"""
transfer_engine.py

Deterministic transfer-candidate generation and ranking.

The engine does not decide based on player popularity alone. It evaluates
the projected gain against transfer cost and preserves squad constraints.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class TransferCandidate:
    sell_player_id: int
    buy_player_id: int
    sell_name: str
    buy_name: str
    position_id: int
    net_cost: float
    expected_gain: float
    score: float
    rationale: tuple[str, ...]
    data_complete: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _player_xp(projections: dict[int, dict[str, Any]], player_id: int) -> float:
    row = projections.get(int(player_id), {})
    return _number(row.get("horizon_expected_points"))


def generate_transfer_candidates(
    *,
    squad: list[dict[str, Any]],
    market: list[dict[str, Any]],
    projections: dict[int, dict[str, Any]],
    bank: float,
    free_transfers: int,
    max_candidates: int = 250,
) -> list[TransferCandidate]:
    """
    Generate legal one-for-one transfer candidates.

    Formation and squad-size constraints are simplified to position matching
    in this V1 engine. Full club-count/formation validation belongs in the
    later squad-optimizer layer.
    """

    if free_transfers < 1:
        return []

    squad_ids = {int(player["id"]) for player in squad}
    candidates = []

    for sell in squad:
        sell_id = int(sell["id"])
        position_id = int(sell["position_id"])
        sell_price = _number(sell.get("price")) / 10.0 if _number(sell.get("price")) >= 10 else _number(sell.get("price"))

        sell_xp = _player_xp(projections, sell_id)

        for buy in market:
            buy_id = int(buy["id"])

            if buy_id in squad_ids:
                continue

            if int(buy["position_id"]) != position_id:
                continue

            buy_price = _number(buy.get("price")) / 10.0 if _number(buy.get("price")) >= 10 else _number(buy.get("price"))
            net_cost = buy_price - sell_price

            if net_cost > bank:
                continue

            buy_xp = _player_xp(projections, buy_id)
            expected_gain = buy_xp - sell_xp

            if expected_gain <= 0:
                continue

            complete = bool(
                projections.get(sell_id, {}).get("projection_complete")
                and projections.get(buy_id, {}).get("projection_complete")
            )

            rationale = [
                f"{buy.get('name', buy_id)} projects {expected_gain:.2f} points "
                "above the outgoing player over the strategy horizon."
            ]

            if not complete:
                rationale.append(
                    "Projection is incomplete; treat this candidate as a watchlist item, "
                    "not a final transfer recommendation."
                )

            # V1 score prioritizes projected gain while mildly penalizing
            # cash usage. This is a ranking aid, not a calibrated probability.
            score = expected_gain - max(0.0, net_cost) * 0.05

            candidates.append(
                TransferCandidate(
                    sell_player_id=sell_id,
                    buy_player_id=buy_id,
                    sell_name=str(sell.get("name", sell_id)),
                    buy_name=str(buy.get("name", buy_id)),
                    position_id=position_id,
                    net_cost=net_cost,
                    expected_gain=expected_gain,
                    score=score,
                    rationale=tuple(rationale),
                    data_complete=complete,
                )
            )

    candidates.sort(
        key=lambda row: (row.data_complete, row.score),
        reverse=True,
    )

    return candidates[:max_candidates]
