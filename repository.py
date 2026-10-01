"""
Repository contracts for FPL-Agent persistence.

The rest of the application should depend on repository behaviour rather
than knowing which database technology is being used.

SQLite is the first implementation, but the same contract can later be
implemented by another database backend.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from typing import Any, Iterable, Mapping


class RepositoryError(Exception):
    """Base exception for persistence-layer errors."""


class Repository(ABC):
    """
    Abstract persistence contract.

    Domain/business code should depend on this abstraction rather than
    executing SQL directly.
    """

    # ------------------------------------------------------------------
    # Generic persistence operations
    # ------------------------------------------------------------------

    @abstractmethod
    def execute(
        self,
        sql: str,
        parameters: Iterable[Any] = (),
    ) -> int:
        """
        Execute a write statement.

        Returns:
            Number of affected rows.
        """
        raise NotImplementedError

    @abstractmethod
    def fetch_one(
        self,
        sql: str,
        parameters: Iterable[Any] = (),
    ) -> Any:
        """
        Execute a query and return one row, or None.
        """
        raise NotImplementedError

    @abstractmethod
    def fetch_all(
        self,
        sql: str,
        parameters: Iterable[Any] = (),
    ) -> list[Any]:
        """
        Execute a query and return all rows.
        """
        raise NotImplementedError

    @abstractmethod
    def transaction(self) -> AbstractContextManager:
        """
        Return a context manager representing a database transaction.

        Successful completion commits.
        Exceptions roll back.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Ingestion run methods
    # ------------------------------------------------------------------

    @abstractmethod
    def create_ingestion_run(
        self,
        source_system: str,
        source_type: str,
        endpoint_or_file: str,
        started_at: str,
        source_retrieved_at: str | None = None,
        status: str = "RUNNING",
        records_received: int | None = None,
        records_written: int | None = None,
        records_rejected: int | None = None,
        content_hash: str | None = None,
        validation_status: str | None = None,
        error_message: str | None = None,
    ) -> int:
        """Create an ingestion execution record and return its ID."""
        raise NotImplementedError

    @abstractmethod
    def complete_ingestion_run(
        self,
        ingestion_run_id: int,
        status: str,
        completed_at: str | None = None,
        records_received: int | None = None,
        records_written: int | None = None,
        records_rejected: int | None = None,
        validation_status: str | None = None,
        error_message: str | None = None,
    ) -> int:
        """Complete an ingestion run and return affected row count."""
        raise NotImplementedError

    @abstractmethod
    def get_ingestion_run(
        self,
        ingestion_run_id: int,
    ) -> Any:
        """Return one ingestion run by internal ID, or None."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Team methods
    # ------------------------------------------------------------------

    @abstractmethod
    def upsert_team(
        self,
        fpl_team_id: int,
        name: str,
        short_name: str | None = None,
        code: int | None = None,
    ) -> int:
        """Insert or update a stable FPL team identity."""
        raise NotImplementedError

    @abstractmethod
    def create_team_snapshot(
        self,
        season_id: int,
        team_id: int,
        snapshot_at: str,
        snapshot: Mapping[str, Any],
        ingestion_run_id: int | None = None,
    ) -> int:
        """Create one point-in-time team snapshot."""
        raise NotImplementedError

    @abstractmethod
    def get_latest_team_snapshot(
        self,
        team_id: int,
        season_id: int,
    ) -> Any:
        """Return the latest team snapshot for a season."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Player methods
    # ------------------------------------------------------------------

    @abstractmethod
    def upsert_player(
        self,
        fpl_player_id: int,
        first_name: str | None = None,
        second_name: str | None = None,
        web_name: str | None = None,
    ) -> int:
        """Insert or update a stable FPL player identity."""
        raise NotImplementedError

    @abstractmethod
    def create_player_snapshot(
        self,
        season_id: int,
        player_id: int,
        snapshot_at: str,
        snapshot: Mapping[str, Any],
        ingestion_run_id: int | None = None,
    ) -> int:
        """Create one point-in-time player snapshot."""
        raise NotImplementedError

    @abstractmethod
    def get_latest_player_snapshot(
        self,
        player_id: int,
        season_id: int,
    ) -> Any:
        """Return the latest player snapshot for a season."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Fixture methods
    # ------------------------------------------------------------------

    @abstractmethod
    def upsert_fixture(
        self,
        season_id: int,
        fpl_fixture_id: int,
        home_team_id: int,
        away_team_id: int,
        gameweek_id: int | None = None,
        kickoff_time: str | None = None,
        started: bool = False,
        finished: bool = False,
        home_score: int | None = None,
        away_score: int | None = None,
        home_difficulty: int | None = None,
        away_difficulty: int | None = None,
    ) -> int:
        """Insert or update a fixture and return its internal ID."""
        raise NotImplementedError

    @abstractmethod
    def get_fixture(
        self,
        fpl_fixture_id: int,
    ) -> Any:
        """Return a fixture by official FPL fixture ID."""
        raise NotImplementedError

    @abstractmethod
    def get_fixtures_for_gameweek(
        self,
        season_id: int,
        gameweek_id: int,
    ) -> list[Any]:
        """Return all fixtures belonging to a gameweek."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Current player-gameweek statistics
    # ------------------------------------------------------------------

    @abstractmethod
    def upsert_current_player_gameweek_stats(
        self,
        season_id: int,
        player_id: int,
        fixture_id: int,
        stats: Mapping[str, Any],
        gameweek_id: int | None = None,
        ingestion_run_id: int | None = None,
    ) -> int:
        """Insert or update current-season player-fixture statistics."""
        raise NotImplementedError

    @abstractmethod
    def get_current_player_gameweek_stats(
        self,
        season_id: int,
        player_id: int,
        fixture_id: int,
    ) -> Any:
        """Return current-season statistics for one player-fixture pair."""
        raise NotImplementedError