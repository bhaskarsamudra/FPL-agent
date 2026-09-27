"""Incremental refresh orchestration for the FPL Strategist."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from data_store import JsonDataStore
from fpl_data_source import FPLDataSource


@dataclass(frozen=True)
class RefreshReport:
    """Summary of one refresh operation."""
    source: str
    started_at: str
    completed_at: str
    status: str
    collections: dict[str, dict[str, int]]
    error: str | None = None


def _timestamp() -> str:
    """Return an auditable UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def _normalise_bootstrap_players(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert bootstrap player records into stable store records."""
    return [
        {"record_id": str(player["id"]), "payload": player}
        for player in payload.get("elements", [])
        if "id" in player
    ]


def _normalise_fixtures(fixtures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert fixture records into stable store records."""
    return [
        {"record_id": str(fixture["id"]), "payload": fixture}
        for fixture in fixtures
        if "id" in fixture
    ]


class FPLRefreshManager:
    """
    Refresh FPL data and persist it for later analysis.

    Global data is shared conceptually across users; manager data is explicitly
    stored in manager-specific collections.
    """

    SOURCE_NAME = "fpl_api"

    def __init__(self, data_source: FPLDataSource, store: JsonDataStore) -> None:
        self.data_source = data_source
        self.store = store

    def refresh_global_data(self) -> RefreshReport:
        """Refresh bootstrap and fixture data."""
        started_at = _timestamp()
        try:
            bootstrap = self.data_source.fetch_bootstrap_static()
            fixtures = self.data_source.fetch_fixtures()

            player_stats = self.store.upsert_records(
                "fpl_players", _normalise_bootstrap_players(bootstrap), self.SOURCE_NAME
            )
            fixture_stats = self.store.upsert_records(
                "fpl_fixtures", _normalise_fixtures(fixtures), self.SOURCE_NAME
            )

            report = RefreshReport(
                self.SOURCE_NAME, started_at, _timestamp(), "success",
                {"fpl_players": player_stats, "fpl_fixtures": fixture_stats},
            )
            self.store.save_refresh_metadata(self.SOURCE_NAME, {
                "status": report.status,
                "started_at": report.started_at,
                "completed_at": report.completed_at,
                "collections": report.collections,
            })
            return report

        except Exception as exc:
            report = RefreshReport(
                self.SOURCE_NAME, started_at, _timestamp(), "failed", {}, str(exc)
            )
            self.store.save_refresh_metadata(self.SOURCE_NAME, {
                "status": report.status,
                "started_at": report.started_at,
                "completed_at": report.completed_at,
                "error": report.error,
            })
            return report

    def refresh_manager_data(self, manager_id: int, gameweek: int) -> RefreshReport:
        """Refresh user-specific picks and season history."""
        started_at = _timestamp()
        try:
            picks = self.data_source.fetch_manager_picks(manager_id, gameweek)
            history = self.data_source.fetch_manager_history(manager_id)

            picks_stats = self.store.upsert_records(
                f"manager_{manager_id}_picks",
                [{"record_id": str(gameweek), "payload": picks}],
                self.SOURCE_NAME,
            )
            history_stats = self.store.upsert_records(
                f"manager_{manager_id}_history",
                [{"record_id": "season_history", "payload": history}],
                self.SOURCE_NAME,
            )

            return RefreshReport(
                self.SOURCE_NAME, started_at, _timestamp(), "success",
                {"manager_picks": picks_stats, "manager_history": history_stats},
            )
        except Exception as exc:
            return RefreshReport(
                self.SOURCE_NAME, started_at, _timestamp(), "failed", {}, str(exc)
            )

    def refresh_if_needed(
        self,
        manager_id: int | None = None,
        gameweek: int | None = None,
    ) -> RefreshReport:
        """
        Run the current explicit V1 refresh policy.

        Freshness windows and dependency-aware scheduling are intentionally
        deferred until this basic persistence contract is tested.
        """
        if manager_id is not None and gameweek is not None:
            return self.refresh_manager_data(manager_id, gameweek)
        return self.refresh_global_data()
