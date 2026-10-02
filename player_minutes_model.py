"""
player_minutes_model.py

Batch 9 — transparent player start-probability and expected-minutes model.

Purpose
-------
Convert official FPL player availability and playing-time evidence into
an auditable point-in-time estimate of:

- availability probability
- start probability
- expected minutes

This is deliberately a V1 baseline. It does not claim to solve football
rotation perfectly and it does not use future information.

Important modelling boundary
----------------------------
The model uses season-to-date FPL fields when no recent history is supplied.
It does not silently invent substitute appearances. Expected minutes are
therefore based on expected starts:

    expected_minutes = 90 × start_probability

A player with some historical minutes but no reliable start evidence is
degraded rather than given an invented starting probability.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


MODEL_VERSION = "player_minutes_v1"


@dataclass(frozen=True)
class PlayerMinutesProjection:
    """Auditable point-in-time playing-time projection."""

    player_id: int
    availability_probability: float
    start_probability: float
    expected_minutes: float
    data_complete: bool
    warnings: tuple[str, ...]
    model_version: str = MODEL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _number(value: Any) -> float | None:
    """Return a finite float or None when the input is unavailable."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if number != number or abs(number) == float("inf"):
        return None

    return number


def _availability_probability(
    player: dict[str, Any],
) -> tuple[float, list[str], bool]:
    """
    Read the official FPL chance-of-playing field.

    A null chance is treated as normal availability because FPL uses null
    for players without a specific availability percentage. This is not
    treated as missing data.
    """
    warnings: list[str] = []
    chance = _number(player.get("chance_of_playing_this_round"))

    if chance is None:
        return 1.0, warnings, True

    return min(1.0, max(0.0, chance / 100.0)), warnings, True


def _season_start_signal(
    player: dict[str, Any],
) -> tuple[float | None, list[str], bool]:
    """
    Estimate starting propensity from season-to-date minutes and starts.

    The denominator converts minutes into an approximate number of 90-minute
    appearances. The result is bounded to [0, 1].

    This is evidence about the player's observed role, not a guarantee that
    the player starts the target fixture.
    """
    warnings: list[str] = []

    minutes = _number(player.get("minutes"))
    starts = _number(player.get("starts"))

    if minutes is None or starts is None:
        return (
            None,
            ["Starting evidence unavailable: minutes/starts data is missing."],
            False,
        )

    minutes = max(0.0, minutes)
    starts = max(0.0, starts)

    if minutes <= 0 and starts <= 0:
        return (
            None,
            ["Starting evidence unavailable: player has no historical minutes."],
            False,
        )

    if starts <= 0:
        return (
            0.0,
            ["Player has historical minutes but no recorded starts."],
            True,
        )

    inferred_90s = max(starts, minutes / 90.0)
    signal = starts / inferred_90s

    return min(1.0, max(0.0, signal)), warnings, True


def project_player_minutes(
    *,
    player: dict[str, Any],
) -> PlayerMinutesProjection:
    """
    Build a point-in-time playing-time projection.

    The player's status is an authoritative availability gate:
    inactive/unavailable statuses produce zero expected minutes.

    Status values used by the FPL API:
        a = available
        d = doubtful
        i = injured
        s = suspended
        u = unavailable
    """
    warnings: list[str] = []
    complete = True

    try:
        player_id = int(player["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Player must contain a valid integer 'id'.") from exc

    availability, availability_warnings, availability_complete = (
        _availability_probability(player)
    )
    warnings.extend(availability_warnings)
    complete = complete and availability_complete

    start_signal, start_warnings, start_complete = _season_start_signal(player)
    warnings.extend(start_warnings)
    complete = complete and start_complete

    status = str(player.get("status", "a")).strip().lower()

    if status in {"i", "s", "u"}:
        return PlayerMinutesProjection(
            player_id=player_id,
            availability_probability=0.0,
            start_probability=0.0,
            expected_minutes=0.0,
            data_complete=complete,
            warnings=tuple(
                dict.fromkeys(
                    warnings
                    + [f"Player status '{status}' blocks expected minutes."]
                )
            ),
        )

    if start_signal is None:
        # Do not manufacture a starting probability.
        return PlayerMinutesProjection(
            player_id=player_id,
            availability_probability=availability,
            start_probability=0.0,
            expected_minutes=0.0,
            data_complete=False,
            warnings=tuple(
                dict.fromkeys(
                    warnings
                    + ["Start probability unavailable; expected minutes set to zero."]
                )
            ),
        )

    start_probability = min(
        1.0,
        max(0.0, availability * start_signal),
    )
    expected_minutes = 90.0 * start_probability

    return PlayerMinutesProjection(
        player_id=player_id,
        availability_probability=availability,
        start_probability=start_probability,
        expected_minutes=expected_minutes,
        data_complete=complete,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def project_player_minutes_batch(
    players: list[dict[str, Any]],
) -> dict[int, PlayerMinutesProjection]:
    """Project playing time for a collection of FPL players."""
    if not isinstance(players, list):
        raise TypeError("players must be a list.")

    return {
        int(player["id"]): project_player_minutes(player=player)
        for player in players
    }
