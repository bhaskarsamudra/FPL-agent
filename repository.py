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
from typing import Any, Iterable


class RepositoryError(Exception):
    """Base exception for persistence-layer errors."""


class Repository(ABC):
    """
    Abstract persistence contract.

    Domain/business code should depend on this abstraction rather than
    executing SQL directly.
    """

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

    @abstractmethod
    def get_dataset_freshness(
        self,
        dataset_name: str,
    ) -> Any:
        """Return freshness metadata for one dataset, or None."""
        raise NotImplementedError

    @abstractmethod
    def upsert_dataset_freshness(
        self,
        dataset_name: str,
        last_successful_ingestion_id: int | None = None,
        last_attempted_ingestion_id: int | None = None,
        last_successful_refresh_at: str | None = None,
        last_attempted_refresh_at: str | None = None,
        freshness_threshold_seconds: int | None = None,
        freshness_status: str | None = None,
        current_gameweek_id: int | None = None,
    ) -> int:
        """Insert or update freshness metadata for one dataset."""
        raise NotImplementedError

    @abstractmethod
    def upsert_user(
        self,
        external_user_key: str,
        display_name: str | None = None,
    ) -> int:
        """Insert or update one application user."""
        raise NotImplementedError

    @abstractmethod
    def upsert_manager(
        self,
        user_id: int,
        fpl_manager_id: int,
        manager_name: str | None = None,
        team_name: str | None = None,
    ) -> int:
        """Insert or update one FPL manager."""
        raise NotImplementedError

    @abstractmethod
    def upsert_manager_gameweek_state(
        self,
        manager_id: int,
        season_id: int,
        gameweek_id: int,
        points: int | None = None,
        total_points: int | None = None,
        overall_rank: int | None = None,
        rank: int | None = None,
        bank: float | None = None,
        team_value: float | None = None,
        event_transfers: int | None = None,
        event_transfers_cost: int | None = None,
        points_on_bench: int | None = None,
        source_timestamp: str | None = None,
        ingestion_run_id: int | None = None,
    ) -> int:
        """Insert or update one manager Gameweek state record."""
        raise NotImplementedError

    @abstractmethod
    def upsert_manager_pick(
        self,
        manager_id: int,
        season_id: int,
        gameweek_id: int,
        player_id: int,
        position: int | None = None,
        multiplier: int | None = None,
        is_captain: bool = False,
        is_vice_captain: bool = False,
        purchase_price: float | None = None,
        ingestion_run_id: int | None = None,
    ) -> int:
        """Insert or update one manager pick."""
        raise NotImplementedError

    @abstractmethod
    def create_manager_transfer(
        self,
        manager_id: int,
        season_id: int,
        gameweek_id: int,
        transfer_timestamp: str | None = None,
        player_in_id: int | None = None,
        player_out_id: int | None = None,
        cost: int | None = None,
        external_transfer_id: str | None = None,
        ingestion_run_id: int | None = None,
    ) -> int:
        """Create one manager transfer record."""
        raise NotImplementedError

    @abstractmethod
    def upsert_manager_chip(
        self,
        manager_id: int,
        season_id: int,
        chip_type: str,
        gameweek_id: int | None = None,
        used_at: str | None = None,
    ) -> int:
        """Insert or update one manager chip usage record."""
        raise NotImplementedError

    @abstractmethod
    def upsert_league(
        self,
        fpl_league_id: int,
        season_id: int,
        name: str | None = None,
        league_type: str | None = None,
    ) -> int:
        """Insert or update one FPL league for a season."""
        raise NotImplementedError

    @abstractmethod
    def upsert_league_member(
        self,
        league_id: int,
        manager_id: int,
    ) -> int:
        """Insert or update one manager membership in one league."""
        raise NotImplementedError

    @abstractmethod
    def upsert_league_standing(
        self,
        league_id: int,
        manager_id: int,
        season_id: int,
        gameweek_id: int,
        rank: int | None = None,
        total_points: int | None = None,
        last_rank: int | None = None,
        rank_change: int | None = None,
        ingestion_run_id: int | None = None,
    ) -> int:
        """Insert or update one league-specific manager standing."""
        raise NotImplementedError

    @abstractmethod
    def upsert_rival_squad_snapshot(
        self,
        league_id: int,
        manager_id: int,
        season_id: int,
        gameweek_id: int,
        player_id: int,
        position: int | None = None,
        is_captain: bool = False,
        is_vice_captain: bool = False,
        multiplier: int | None = None,
        ingestion_run_id: int | None = None,
    ) -> int:
        """Insert or update one league-specific rival squad snapshot row."""
        raise NotImplementedError
