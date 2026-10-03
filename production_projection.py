"""
production_projection.py

Batch 18A - authoritative production projection pipeline.

This module connects the existing modelling layers without replacing them.
It is deliberately small and deterministic:

    completed fixtures before target GW
        -> point-in-time team states
        -> expected team goals per future fixture
        -> player fixture projections
        -> multi-GW player projections

The important architectural rule is that the team state is built only from
completed fixtures BEFORE the target Gameweek.  The current player universe is
not used to calculate historical team performance, because current cumulative
player statistics could otherwise leak information from after the decision
point into the forecast.

The module does not make transfer, captain or chip decisions.  Those remain
responsibilities of the strategy layer.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

from expected_goals_model import calculate_league_averages, predict_expected_goals
from player_fixture_model import (
    PlayerFixtureProjection,
    aggregate_player_projections,
    build_fixture_player_projections,
)
from team_data import build_team_performance


MODEL_VERSION = "production_projection_v1"


@dataclass(frozen=True)
class ProductionProjectionResult:
    """Auditable result returned by the production projection pipeline."""

    target_gameweek: int
    horizon_gameweeks: tuple[int, ...]
    projections: dict[int, dict[str, Any]]
    fixture_projections: tuple[PlayerFixtureProjection, ...]
    team_expected_goals: dict[int, dict[int, float]]
    data_complete: bool
    warnings: tuple[str, ...]
    model_version: str = MODEL_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return asdict(self)


def _validate_horizon(
    *,
    target_gameweek: int,
    horizon_gameweeks: Sequence[int],
) -> tuple[int, ...]:
    """Validate and normalize the requested future Gameweek horizon."""

    if not isinstance(horizon_gameweeks, Sequence) or isinstance(
        horizon_gameweeks, (str, bytes)
    ):
        raise TypeError("horizon_gameweeks must be a sequence of Gameweek numbers.")

    horizon = tuple(int(gameweek) for gameweek in horizon_gameweeks)

    if not horizon:
        raise ValueError("horizon_gameweeks must contain at least one Gameweek.")

    if len(set(horizon)) != len(horizon):
        raise ValueError("horizon_gameweeks must not contain duplicate Gameweeks.")

    if horizon[0] != int(target_gameweek):
        raise ValueError(
            "The first horizon Gameweek must equal target_gameweek."
        )

    if any(gameweek < target_gameweek for gameweek in horizon):
        raise ValueError(
            "horizon_gameweeks cannot contain Gameweeks before target_gameweek."
        )

    return horizon


def _future_fixtures_for_horizon(
    *,
    fixtures: Sequence[dict[str, Any]],
    horizon_gameweeks: tuple[int, ...],
) -> list[dict[str, Any]]:
    """Return only uncompleted fixtures inside the requested horizon."""

    horizon = set(horizon_gameweeks)
    result = []

    for fixture in fixtures:
        gameweek = fixture.get("gameweek")
        if gameweek is None:
            continue

        if int(gameweek) not in horizon:
            continue

        # Finished fixtures are historical outcomes and must never become
        # future projection inputs.
        if bool(fixture.get("finished", False)):
            continue

        result.append(dict(fixture))

    return sorted(
        result,
        key=lambda row: (
            int(row.get("gameweek", 0)),
            str(row.get("kickoff_time") or ""),
            int(row.get("fixture_id", 0) or 0),
        ),
    )


def _completed_fixtures_before_target(
    *,
    fixtures: Sequence[dict[str, Any]],
    target_gameweek: int,
) -> list[dict[str, Any]]:
    """Return completed fixtures strictly before the target Gameweek."""

    result = []

    for fixture in fixtures:
        gameweek = fixture.get("gameweek")
        if gameweek is None:
            continue

        if int(gameweek) >= int(target_gameweek):
            continue

        if not bool(fixture.get("finished", False)):
            continue

        # A completed fixture must have both scores to form a factual team
        # state. Incomplete records are ignored rather than fabricated.
        if fixture.get("home_score") is None or fixture.get("away_score") is None:
            continue

        result.append(dict(fixture))

    return result


def _team_expected_goals_for_fixture(
    *,
    fixture: dict[str, Any],
    team_states: dict[int, dict[str, Any]],
    league_averages: dict[str, float],
) -> tuple[dict[int, float] | None, str | None]:
    """Predict expected goals for both teams in one future fixture."""

    home_team_id = int(fixture["home_team_id"])
    away_team_id = int(fixture["away_team_id"])

    home_state = team_states.get(home_team_id)
    away_state = team_states.get(away_team_id)

    if home_state is None or away_state is None:
        missing = []
        if home_state is None:
            missing.append(f"home team {home_team_id}")
        if away_state is None:
            missing.append(f"away team {away_team_id}")
        return None, (
            f"No point-in-time team state is available for "
            f"{', '.join(missing)} before GW{fixture['gameweek']}."
        )

    prediction = predict_expected_goals(
        home_team=str(fixture.get("home_team", home_team_id)),
        away_team=str(fixture.get("away_team", away_team_id)),
        home_team_state=home_state,
        away_team_state=away_state,
        league_average_home_goals=float(
            league_averages["home_goals_per_match"]
        ),
        league_average_away_goals=float(
            league_averages["away_goals_per_match"]
        ),
    )

    return {
        home_team_id: prediction.expected_home_goals,
        away_team_id: prediction.expected_away_goals,
    }, None


def build_production_projections(
    *,
    players: list[dict[str, Any]],
    fixtures: list[dict[str, Any]],
    target_gameweek: int,
    horizon_gameweeks: Sequence[int],
    bootstrap_data: dict[str, Any],
) -> ProductionProjectionResult:
    """
    Build authoritative player projections for a future Gameweek horizon.

    Parameters
    ----------
    players:
        Point-in-time player universe available at the decision timestamp.
        For a live decision this should come from the latest verified FPL
        refresh, not from future data.

    fixtures:
        Structured FPL fixtures. Completed fixtures before the target GW are
        used to form team states; uncompleted fixtures in the requested
        horizon are forecast.

    target_gameweek:
        First Gameweek in the forecast horizon.

    horizon_gameweeks:
        Explicit Gameweeks to evaluate, for example ``[6, 7, 8]``. An
        explicit list naturally supports Blank Gameweeks and Double
        Gameweeks.

    bootstrap_data:
        Verified FPL bootstrap data used by the existing FPL scoring model.

    Returns
    -------
    ProductionProjectionResult
        Multi-GW player projections in the shape consumed by the existing
        transfer/captain/strategy engines.
    """

    if not isinstance(players, list):
        raise TypeError("players must be a list.")
    if not isinstance(fixtures, list):
        raise TypeError("fixtures must be a list.")
    if not isinstance(bootstrap_data, dict):
        raise TypeError("bootstrap_data must be a dictionary.")

    target_gameweek = int(target_gameweek)
    horizon = _validate_horizon(
        target_gameweek=target_gameweek,
        horizon_gameweeks=horizon_gameweeks,
    )

    historical_fixtures = _completed_fixtures_before_target(
        fixtures=fixtures,
        target_gameweek=target_gameweek,
    )
    future_fixtures = _future_fixtures_for_horizon(
        fixtures=fixtures,
        horizon_gameweeks=horizon,
    )

    warnings: list[str] = []

    if not historical_fixtures:
        return ProductionProjectionResult(
            target_gameweek=target_gameweek,
            horizon_gameweeks=horizon,
            projections={},
            fixture_projections=(),
            team_expected_goals={},
            data_complete=False,
            warnings=(
                "No completed fixtures are available before the target Gameweek.",
            ),
        )

    if not future_fixtures:
        return ProductionProjectionResult(
            target_gameweek=target_gameweek,
            horizon_gameweeks=horizon,
            projections={},
            fixture_projections=(),
            team_expected_goals={},
            data_complete=False,
            warnings=(
                "No future fixtures are available in the requested horizon.",
            ),
        )

    # IMPORTANT: Do not pass the current player universe here. The team-state
    # builder must use completed match results only, otherwise current player
    # statistics could leak information from after the target decision point.
    team_performance = build_team_performance(
        historical_fixtures,
        player_universe=None,
    )
    team_states = {
        int(team_id): dict(state)
        for team_id, state in team_performance.items()
    }

    league_averages = calculate_league_averages(
        list(team_states.values())
    )

    aggregated_fixture_projections: list[PlayerFixtureProjection] = []
    team_expected_goals: dict[int, dict[int, float]] = {}
    complete = True

    for fixture in future_fixtures:
        expected_goals, warning = _team_expected_goals_for_fixture(
            fixture=fixture,
            team_states=team_states,
            league_averages=league_averages,
        )

        fixture_id = fixture.get("fixture_id")
        if expected_goals is None:
            complete = False
            if warning:
                warnings.append(
                    f"Fixture {fixture_id}: {warning}"
                )
            continue

        team_expected_goals[int(fixture_id)] = {
            int(team_id): float(value)
            for team_id, value in expected_goals.items()
        }

        fixture_projections = build_fixture_player_projections(
            players=players,
            fixture=fixture,
            team_expected_goals=expected_goals,
            bootstrap_data=bootstrap_data,
        )
        aggregated_fixture_projections.extend(fixture_projections)

    if not aggregated_fixture_projections:
        complete = False
        warnings.append(
            "No player fixture projections could be produced for the requested horizon."
        )

    aggregated = aggregate_player_projections(
        aggregated_fixture_projections
    )

    # Preserve the projection contract already consumed by the transfer,
    # captain and strategy engines. The lower-level aggregation model calls
    # the horizon total ``expected_points``; the strategy contract calls it
    # ``horizon_expected_points`` and uses ``projection_complete``.
    players_by_id = {int(player["id"]): player for player in players}
    projections: dict[int, dict[str, Any]] = {}

    for player_id, row in aggregated.items():
        player = players_by_id.get(int(player_id), {})
        projection = dict(row)
        projection["player_name"] = player.get("name", player.get("web_name"))
        projection["team_id"] = player.get("team_id")
        projection["price"] = player.get("price")
        projection["horizon_expected_points"] = float(
            row.get("expected_points", 0.0)
        )
        projection["projection_complete"] = bool(
            row.get("data_complete", False)
        )
        projections[int(player_id)] = projection

    if any(not row.get("projection_complete", False) for row in projections.values()):
        complete = False

    return ProductionProjectionResult(
        target_gameweek=target_gameweek,
        horizon_gameweeks=horizon,
        projections=projections,
        fixture_projections=tuple(aggregated_fixture_projections),
        team_expected_goals=team_expected_goals,
        data_complete=complete,
        warnings=tuple(dict.fromkeys(warnings)),
    )
