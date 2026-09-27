"""
fixture_utils.py

Small deterministic helpers for working with official FPL fixtures.
"""

from __future__ import annotations

from typing import Any


def future_fixtures_for_team(
    fixtures: list[dict[str, Any]],
    team_id: int,
    start_gameweek: int,
    horizon: int = 3,
) -> list[dict[str, Any]]:
    """Return future fixtures for a team within the requested GW horizon."""

    if horizon <= 0:
        return []

    end_gameweek = start_gameweek + horizon - 1
    result = []

    for fixture in fixtures:
        gw = fixture.get("gameweek", fixture.get("event"))
        if gw is None:
            continue

        if not start_gameweek <= int(gw) <= end_gameweek:
            continue

        if int(fixture.get("home_team_id", fixture.get("team_h", -1))) == int(team_id):
            result.append(
                {
                    "gameweek": int(gw),
                    "opponent_team_id": int(
                        fixture.get("away_team_id", fixture.get("team_a"))
                    ),
                    "home": True,
                    "fdr": fixture.get("home_difficulty", fixture.get("team_h_difficulty")),
                    "fixture_id": fixture.get("fixture_id", fixture.get("id")),
                }
            )

        elif int(fixture.get("away_team_id", fixture.get("team_a", -1))) == int(team_id):
            result.append(
                {
                    "gameweek": int(gw),
                    "opponent_team_id": int(
                        fixture.get("home_team_id", fixture.get("team_h"))
                    ),
                    "home": False,
                    "fdr": fixture.get("away_difficulty", fixture.get("team_a_difficulty")),
                    "fixture_id": fixture.get("fixture_id", fixture.get("id")),
                }
            )

    return sorted(result, key=lambda row: (row["gameweek"], row["fixture_id"] or 0))
