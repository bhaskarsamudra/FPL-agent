"""
player_fixture_model.py

Batch 8 bridge between the validated team-level expected-goals model and
fixture-level FPL player expected points.

This module deliberately keeps the layers separate:

    team expected goals
        -> player xG/xA allocation
        -> clean-sheet probability
        -> expected bonus baseline
        -> existing expected_points.py engine

The allocation is transparent and deterministic. It does not invent a
player projection when the required team/player inputs are unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from math import exp
from typing import Any

from expected_points import ExpectedPoints, expected_points_for_fixture
from player_minutes_model import project_player_minutes


MODEL_VERSION = "player_fixture_xp_v1"


@dataclass(frozen=True)
class PlayerFixtureProjection:
    """Auditable player projection for one fixture."""

    player_id: int
    fixture_id: int | None
    gameweek: int
    team_id: int
    opponent_team_id: int
    was_home: bool

    team_expected_goals: float
    player_xg_share: float
    player_expected_goals: float

    team_expected_assists: float
    player_xa_share: float
    player_expected_assists: float

    clean_sheet_probability: float
    expected_bonus: float

    expected_minutes: float
    start_probability: float
    expected_points: float

    data_complete: bool
    warnings: tuple[str, ...]
    model_version: str = MODEL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _float(value: Any, default: float = 0.0) -> float:
    """Convert a value to a finite float."""

    try:
        result = float(value)
    except (TypeError, ValueError):
        return default

    if result != result or abs(result) == float("inf"):
        return default

    return result


def _positive(value: Any) -> float:
    """Return a non-negative numeric value."""

    return max(0.0, _float(value))


def _player_team_share(
    player: dict[str, Any],
    players: list[dict[str, Any]],
    field: str,
) -> tuple[float | None, str | None]:
    """
    Calculate a player's share of the team's current xG/xA.

    Returns (share, warning). A missing/zero team total is explicit rather
    than silently allocating the team expectation to a player.
    """

    team_id = int(player["team_id"])
    team_players = [
        row for row in players if int(row.get("team_id", -1)) == team_id
    ]

    player_value = _positive(player.get(field))
    team_total = sum(_positive(row.get(field)) for row in team_players)

    if team_total <= 0:
        return None, f"Team {team_id} has no usable {field} total."

    return min(1.0, player_value / team_total), None


def allocate_player_xg(
    *,
    player: dict[str, Any],
    players: list[dict[str, Any]],
    team_expected_goals: float,
) -> tuple[float | None, float | None, tuple[str, ...]]:
    """Allocate team expected goals to a player using current xG share."""

    share, warning = _player_team_share(
        player,
        players,
        "expected_goals",
    )

    if share is None:
        return None, None, (warning or "Player xG share unavailable.",)

    return share, max(0.0, team_expected_goals) * share, ()


def allocate_player_xa(
    *,
    player: dict[str, Any],
    players: list[dict[str, Any]],
    team_expected_assists: float,
) -> tuple[float | None, float | None, tuple[str, ...]]:
    """Allocate team expected assists to a player using current xA share."""

    share, warning = _player_team_share(
        player,
        players,
        "expected_assists",
    )

    if share is None:
        return None, None, (warning or "Player xA share unavailable.",)

    return share, max(0.0, team_expected_assists) * share, ()


def clean_sheet_probability(
    *,
    opponent_expected_goals: float,
) -> float:
    """
    Estimate clean-sheet probability from opponent expected goals.

    Under the baseline Poisson assumption, P(opponent scores zero) = e^-lambda.
    This is deliberately exposed as a baseline probability, not a claim that
    the final clean-sheet model is calibrated.
    """

    expected_goals = max(0.0, _float(opponent_expected_goals))
    return min(1.0, max(0.0, exp(-expected_goals)))


def estimate_expected_bonus(
    *,
    player: dict[str, Any],
    start_probability: float,
) -> tuple[float, str | None]:
    """
    Estimate expected bonus from observed bonus per start.

    This is a transparent baseline only. It requires at least one historical
    start; otherwise bonus remains unavailable rather than being invented.
    """

    starts = _positive(player.get("starts"))
    bonus = _positive(player.get("bonus"))

    if starts <= 0:
        return 0.0, "Expected bonus unavailable: player has no historical starts."

    bonus_per_start = bonus / starts
    expected_bonus = bonus_per_start * min(1.0, max(0.0, start_probability))

    # Keep a single fixture's baseline bonus contribution within a sensible
    # FPL range. The cap is a guardrail, not a calibrated probability model.
    return min(3.0, expected_bonus), None


def build_player_fixture_projection(
    *,
    player: dict[str, Any],
    players: list[dict[str, Any]],
    fixture: dict[str, Any],
    team_expected_goals: dict[int, float],
    team_expected_assists: dict[int, float] | None = None,
    bootstrap_data: dict[str, Any] | None = None,
) -> PlayerFixtureProjection:
    """
    Build one complete/degraded player fixture projection.

    team_expected_goals must contain the two fixture teams. Team expected
    assists are optional because the current football model does not yet
    predict team assists independently. When omitted, team expected goals
    are used as the assist-opportunity baseline. The player's xA share then
    determines his allocation.
    """

    bootstrap_data = bootstrap_data or {}
    fixture_id = fixture.get("fixture_id")
    gameweek = int(fixture["gameweek"])
    team_id = int(player["team_id"])
    home_team_id = int(fixture["home_team_id"])
    away_team_id = int(fixture["away_team_id"])

    if team_id not in {home_team_id, away_team_id}:
        raise ValueError(
            f"Player {player.get('id')} does not belong to fixture {fixture_id}."
        )

    was_home = team_id == home_team_id
    opponent_team_id = away_team_id if was_home else home_team_id

    warnings: list[str] = []
    complete = True

    if team_id not in team_expected_goals:
        raise ValueError(f"Missing expected goals for team {team_id}.")

    if opponent_team_id not in team_expected_goals:
        raise ValueError(f"Missing expected goals for opponent {opponent_team_id}.")

    team_xg = max(0.0, _float(team_expected_goals[team_id]))
    opponent_xg = max(0.0, _float(team_expected_goals[opponent_team_id]))

    xg_share, player_xg, xg_warnings = allocate_player_xg(
        player=player,
        players=players,
        team_expected_goals=team_xg,
    )
    warnings.extend(xg_warnings)

    xa_team_values = team_expected_assists or {}
    if team_id in xa_team_values:
        team_xa = max(0.0, _float(xa_team_values[team_id]))
    else:
        # Derive team expected assists from the current player xA/xG ratio.
        # This keeps the allocation internally consistent without inventing a
        # fixed assist multiplier.
        team_players = [
            row for row in players if int(row.get("team_id", -1)) == team_id
        ]
        team_current_xg = sum(_positive(row.get("expected_goals")) for row in team_players)
        team_current_xa = sum(_positive(row.get("expected_assists")) for row in team_players)

        if team_current_xg <= 0:
            team_xa = 0.0
            warnings.append(
                f"Team {team_id} has no usable current xG for deriving expected assists."
            )
            complete = False
        else:
            team_xa = team_xg * (team_current_xa / team_current_xg)
            warnings.append(
                "Team expected assists derived from the current player xA/xG ratio."
            )

    xa_share, player_xa, xa_warnings = allocate_player_xa(
        player=player,
        players=players,
        team_expected_assists=team_xa,
    )
    warnings.extend(xa_warnings)

    # Batch 9: use the dedicated playing-time model rather than keeping
    # start-probability logic hidden inside the expected-points calculator.
    minutes_projection = project_player_minutes(player=player)
    start_probability = minutes_projection.start_probability
    warnings.extend(minutes_projection.warnings)
    if not minutes_projection.data_complete:
        complete = False

    expected_bonus, bonus_warning = estimate_expected_bonus(
        player=player,
        start_probability=start_probability,
    )
    if bonus_warning:
        warnings.append(bonus_warning)

    cs_probability = clean_sheet_probability(
        opponent_expected_goals=opponent_xg,
    )

    if xg_share is None or player_xg is None:
        complete = False
        player_xg = 0.0
        xg_share = 0.0

    if xa_share is None or player_xa is None:
        complete = False
        player_xa = 0.0
        xa_share = 0.0

    # The assist-opportunity fallback above is deliberate and fully
    # specified, so it does not make the result incomplete by itself.
    result: ExpectedPoints = expected_points_for_fixture(
        player=player,
        gameweek=gameweek,
        expected_goals=player_xg,
        expected_assists=player_xa,
        clean_sheet_probability=cs_probability,
        expected_bonus=expected_bonus,
        bootstrap_data=bootstrap_data,
        start_probability=start_probability,
        expected_minutes=minutes_projection.expected_minutes,
    )

    if not result.data_complete:
        complete = False
        warnings.extend(result.warnings)

    # If the player's xG/xA share was unavailable, the underlying result is
    # explicitly degraded even though the calculator can still return a number.
    if xg_share == 0.0 and _positive(player.get("expected_goals")) == 0.0:
        complete = False
    if xa_share == 0.0 and _positive(player.get("expected_assists")) == 0.0:
        complete = False

    return PlayerFixtureProjection(
        player_id=int(player["id"]),
        fixture_id=int(fixture_id) if fixture_id is not None else None,
        gameweek=gameweek,
        team_id=team_id,
        opponent_team_id=opponent_team_id,
        was_home=was_home,
        team_expected_goals=team_xg,
        player_xg_share=xg_share,
        player_expected_goals=player_xg,
        team_expected_assists=team_xa,
        player_xa_share=xa_share,
        player_expected_assists=player_xa,
        clean_sheet_probability=cs_probability,
        expected_bonus=expected_bonus,
        expected_minutes=result.expected_minutes,
        start_probability=start_probability,
        expected_points=result.expected_points,
        data_complete=complete,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def aggregate_player_projections(
    projections: list[PlayerFixtureProjection],
) -> dict[int, dict[str, Any]]:
    """Aggregate fixture projections into player multi-fixture totals."""

    aggregated: dict[int, dict[str, Any]] = {}

    for projection in projections:
        row = aggregated.setdefault(
            projection.player_id,
            {
                "player_id": projection.player_id,
                "expected_points": 0.0,
                "expected_minutes": 0.0,
                "expected_goals": 0.0,
                "expected_assists": 0.0,
                "expected_clean_sheet": 0.0,
                "expected_bonus": 0.0,
                "fixtures": [],
                "data_complete": True,
                "warnings": [],
                "model_version": MODEL_VERSION,
            },
        )

        row["expected_points"] += projection.expected_points
        row["expected_minutes"] += projection.expected_minutes
        row["expected_goals"] += projection.player_expected_goals
        row["expected_assists"] += projection.player_expected_assists
        row["expected_clean_sheet"] += projection.clean_sheet_probability
        row["expected_bonus"] += projection.expected_bonus
        row["fixtures"].append(projection.to_dict())
        row["data_complete"] = row["data_complete"] and projection.data_complete
        row["warnings"].extend(projection.warnings)

    for row in aggregated.values():
        row["warnings"] = list(dict.fromkeys(row["warnings"]))

    return aggregated


def build_fixture_player_projections(
    *,
    players: list[dict[str, Any]],
    fixture: dict[str, Any],
    team_expected_goals: dict[int, float],
    team_expected_assists: dict[int, float] | None = None,
    bootstrap_data: dict[str, Any] | None = None,
) -> list[PlayerFixtureProjection]:
    """Build projections for all players belonging to the fixture teams."""

    fixture_team_ids = {
        int(fixture["home_team_id"]),
        int(fixture["away_team_id"]),
    }

    return [
        build_player_fixture_projection(
            player=player,
            players=players,
            fixture=fixture,
            team_expected_goals=team_expected_goals,
            team_expected_assists=team_expected_assists,
            bootstrap_data=bootstrap_data,
        )
        for player in players
        if int(player.get("team_id", -1)) in fixture_team_ids
    ]
