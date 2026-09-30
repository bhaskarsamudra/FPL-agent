"""
SQLite repository implementation for FPL-Agent.

This module contains SQLite-specific persistence behaviour.

Business and strategy modules should depend on the Repository abstraction
rather than importing sqlite3 directly.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any, Iterable

from repository import Repository, RepositoryError
from sqlite_db import DEFAULT_DB_PATH, connect_sqlite


class SQLiteRepository(Repository):
    """SQLite implementation of the FPL-Agent repository contract."""

    def __init__(self, database_path: str | Path = DEFAULT_DB_PATH):
        """
        Create a repository connected to the specified SQLite database.

        SQLite connection configuration is delegated to sqlite_db.py.
        """
        self.database_path = Path(database_path)
        self.connection = connect_sqlite(self.database_path)

        # Tracks whether the repository is currently inside an explicit
        # transaction. Repository write methods must not commit
        # independently while a transaction is active.
        self._transaction_active = False

    def close(self) -> None:
        """Close the SQLite database connection."""
        self.connection.close()

    @staticmethod
    def _utc_now() -> str:
        """
        Return the current UTC timestamp in ISO-8601 format.

        Repository-generated lifecycle timestamps use UTC so that the
        database remains independent of the user's local timezone.
        """
        return datetime.now(timezone.utc).isoformat()

    def _commit_if_needed(self) -> None:
        """
        Commit a write when we are not inside an explicit transaction.

        When repository.transaction() is active, the surrounding
        transaction controls the final commit or rollback.
        """
        if not self._transaction_active:
            self.connection.commit()

    def execute(
        self,
        sql: str,
        parameters: Iterable[Any] = (),
    ) -> int:
        """
        Execute a write statement.

        Outside an explicit transaction, the statement is committed
        automatically.

        Inside repository.transaction(), the surrounding transaction
        controls the final commit or rollback.

        Returns:
            Number of affected rows.
        """
        try:
            cursor = self.connection.execute(
                sql,
                tuple(parameters),
            )

            self._commit_if_needed()

            return cursor.rowcount

        except sqlite3.Error as exc:
            if not self._transaction_active:
                self.connection.rollback()

            raise RepositoryError(str(exc)) from exc

    def fetch_one(
        self,
        sql: str,
        parameters: Iterable[Any] = (),
    ) -> sqlite3.Row | None:
        """Execute a query and return one row, or None."""
        try:
            return self.connection.execute(
                sql,
                tuple(parameters),
            ).fetchone()

        except sqlite3.Error as exc:
            raise RepositoryError(str(exc)) from exc

    def fetch_all(
        self,
        sql: str,
        parameters: Iterable[Any] = (),
    ) -> list[sqlite3.Row]:
        """Execute a query and return all rows."""
        try:
            return self.connection.execute(
                sql,
                tuple(parameters),
            ).fetchall()

        except sqlite3.Error as exc:
            raise RepositoryError(str(exc)) from exc

    @contextmanager
    def transaction(self):
        """
        Run operations inside one explicit transaction.

        Successful completion commits.

        Any exception causes the transaction to roll back.

        Nested repository transactions are intentionally unsupported.
        """
        if self._transaction_active:
            raise RepositoryError(
                "Nested repository transactions are not supported."
            )

        try:
            self.connection.execute("BEGIN")
            self._transaction_active = True

            yield self

            self.connection.commit()

        except Exception:
            self.connection.rollback()
            raise

        finally:
            self._transaction_active = False

    # ------------------------------------------------------------------
    # Season methods
    # ------------------------------------------------------------------

    def create_season(
        self,
        season_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
        status: str = "ACTIVE",
        is_current: bool = False,
    ) -> int:
        """Create a season and return its internal database ID."""

        timestamp = self._utc_now()

        try:
            cursor = self.connection.execute(
                """
                INSERT INTO seasons (
                    season_code,
                    start_date,
                    end_date,
                    status,
                    is_current,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    season_code,
                    start_date,
                    end_date,
                    status,
                    int(is_current),
                    timestamp,
                    timestamp,
                ),
            )

            self._commit_if_needed()

            return int(cursor.lastrowid)

        except sqlite3.Error as exc:
            if not self._transaction_active:
                self.connection.rollback()

            raise RepositoryError(str(exc)) from exc

    def get_season(
        self,
        season_code: str,
    ) -> sqlite3.Row | None:
        """Return a season by its FPL season code."""
        return self.fetch_one(
            """
            SELECT *
            FROM seasons
            WHERE season_code = ?
            """,
            (season_code,),
        )

    # ------------------------------------------------------------------
    # Gameweek methods
    # ------------------------------------------------------------------

    def create_gameweek(
        self,
        season_id: int,
        gameweek: int,
        name: str | None = None,
        deadline_time: str | None = None,
        finished: bool = False,
        data_checked: bool = False,
        is_current: bool = False,
        is_next: bool = False,
        is_previous: bool = False,
    ) -> int:
        """
        Create a gameweek and return its internal database ID.

        Gameweeks intentionally do not have created_at/updated_at
        lifecycle timestamps.

        A gameweek is a canonical football/FPL event reference entity.
        Its temporal meaning is represented by fields such as
        deadline_time and its relationship to fixtures and ingestion
        timestamps, rather than by CRUD timestamps.
        """

        try:
            cursor = self.connection.execute(
                """
                INSERT INTO gameweeks (
                    season_id,
                    gameweek,
                    name,
                    deadline_time,
                    finished,
                    data_checked,
                    is_current,
                    is_next,
                    is_previous
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    season_id,
                    gameweek,
                    name,
                    deadline_time,
                    int(finished),
                    int(data_checked),
                    int(is_current),
                    int(is_next),
                    int(is_previous),
                ),
            )

            self._commit_if_needed()

            return int(cursor.lastrowid)

        except sqlite3.Error as exc:
            if not self._transaction_active:
                self.connection.rollback()

            raise RepositoryError(str(exc)) from exc

    def get_gameweek(
        self,
        season_id: int,
        gameweek: int,
    ) -> sqlite3.Row | None:
        """Return a gameweek for a specific season."""
        return self.fetch_one(
            """
            SELECT *
            FROM gameweeks
            WHERE season_id = ?
              AND gameweek = ?
            """,
            (
                season_id,
                gameweek,
            ),
        )

    # ------------------------------------------------------------------
    # Team methods
    # ------------------------------------------------------------------

    def create_team(
        self,
        fpl_team_id: int,
        name: str,
        short_name: str | None = None,
        code: int | None = None,
    ) -> int:
        """Create a team and return its internal database ID."""

        timestamp = self._utc_now()

        try:
            cursor = self.connection.execute(
                """
                INSERT INTO teams (
                    fpl_team_id,
                    name,
                    short_name,
                    code,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    fpl_team_id,
                    name,
                    short_name,
                    code,
                    timestamp,
                    timestamp,
                ),
            )

            self._commit_if_needed()

            return int(cursor.lastrowid)

        except sqlite3.Error as exc:
            if not self._transaction_active:
                self.connection.rollback()

            raise RepositoryError(str(exc)) from exc

    def get_team(
        self,
        fpl_team_id: int,
    ) -> sqlite3.Row | None:
        """Return a team by its official FPL team ID."""
        return self.fetch_one(
            """
            SELECT *
            FROM teams
            WHERE fpl_team_id = ?
            """,
            (fpl_team_id,),
        )

    # ------------------------------------------------------------------
    # Player methods
    # ------------------------------------------------------------------

    def create_player(
        self,
        fpl_player_id: int,
        first_name: str,
        second_name: str,
        web_name: str | None = None,
    ) -> int:
        """Create a player and return its internal database ID."""

        timestamp = self._utc_now()

        try:
            cursor = self.connection.execute(
                """
                INSERT INTO players (
                    fpl_player_id,
                    first_name,
                    second_name,
                    web_name,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    fpl_player_id,
                    first_name,
                    second_name,
                    web_name,
                    timestamp,
                    timestamp,
                ),
            )

            self._commit_if_needed()

            return int(cursor.lastrowid)

        except sqlite3.Error as exc:
            if not self._transaction_active:
                self.connection.rollback()

            raise RepositoryError(str(exc)) from exc

    def get_player(
        self,
        fpl_player_id: int,
    ) -> sqlite3.Row | None:
        """Return a player by its official FPL player ID."""
        return self.fetch_one(
            """
            SELECT *
            FROM players
            WHERE fpl_player_id = ?
            """,
            (fpl_player_id,),
        )