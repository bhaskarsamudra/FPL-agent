"""
SQLite repository implementation for FPL-Agent.

This module contains SQLite-specific persistence behaviour.

Business and strategy modules should depend on the Repository abstraction
rather than importing sqlite3 directly.

The repository stores domain records but does not interpret raw FPL
payloads. Normalisation and validation belong to the layers above it.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any, Iterable, Mapping

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

    @staticmethod
    def _value(
        record: Mapping[str, Any],
        key: str,
        default: Any = None,
    ) -> Any:
        """Return one optional value from a domain record."""
        return record.get(key, default)

    # ------------------------------------------------------------------
    # Generic persistence operations
    # ------------------------------------------------------------------

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
    # Ingestion run methods
    # ------------------------------------------------------------------

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
        """
        Create an ingestion execution/provenance record.

        ingestion_runs records how and when data was obtained. It does
        not represent the data itself.
        """

        created_at = self._utc_now()

        try:
            cursor = self.connection.execute(
                """
                INSERT INTO ingestion_runs (
                    source_system,
                    source_type,
                    endpoint_or_file,
                    started_at,
                    completed_at,
                    source_retrieved_at,
                    status,
                    records_received,
                    records_written,
                    records_rejected,
                    content_hash,
                    validation_status,
                    error_message,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_system,
                    source_type,
                    endpoint_or_file,
                    started_at,
                    None,
                    source_retrieved_at,
                    status,
                    records_received,
                    records_written,
                    records_rejected,
                    content_hash,
                    validation_status,
                    error_message,
                    created_at,
                ),
            )

            self._commit_if_needed()

            return int(cursor.lastrowid)

        except sqlite3.Error as exc:
            if not self._transaction_active:
                self.connection.rollback()

            raise RepositoryError(str(exc)) from exc

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
        """Complete an existing ingestion run."""

        if completed_at is None:
            completed_at = self._utc_now()

        try:
            cursor = self.connection.execute(
                """
                UPDATE ingestion_runs
                SET
                    completed_at = ?,
                    status = ?,
                    records_received = ?,
                    records_written = ?,
                    records_rejected = ?,
                    validation_status = ?,
                    error_message = ?
                WHERE id = ?
                """,
                (
                    completed_at,
                    status,
                    records_received,
                    records_written,
                    records_rejected,
                    validation_status,
                    error_message,
                    ingestion_run_id,
                ),
            )

            self._commit_if_needed()

            return cursor.rowcount

        except sqlite3.Error as exc:
            if not self._transaction_active:
                self.connection.rollback()

            raise RepositoryError(str(exc)) from exc

    def get_ingestion_run(
        self,
        ingestion_run_id: int,
    ) -> sqlite3.Row | None:
        """Return one ingestion run by internal ID."""
        return self.fetch_one(
            """
            SELECT *
            FROM ingestion_runs
            WHERE id = ?
            """,
            (ingestion_run_id,),
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

    def upsert_team(
        self,
        fpl_team_id: int,
        name: str,
        short_name: str | None = None,
        code: int | None = None,
    ) -> int:
        """
        Insert a team if it does not exist, otherwise update its
        descriptive fields.

        The stable internal ID is preserved across updates.
        """

        timestamp = self._utc_now()

        try:
            self.connection.execute(
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
                ON CONFLICT(fpl_team_id)
                DO UPDATE SET
                    name = excluded.name,
                    short_name = excluded.short_name,
                    code = excluded.code,
                    updated_at = excluded.updated_at
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

            row = self.connection.execute(
                """
                SELECT id
                FROM teams
                WHERE fpl_team_id = ?
                """,
                (fpl_team_id,),
            ).fetchone()

            if row is None:
                raise RepositoryError(
                    "Team upsert succeeded but the team could not be retrieved."
                )

            self._commit_if_needed()

            return int(row["id"])

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

    def create_team_snapshot(
        self,
        season_id: int,
        team_id: int,
        snapshot_at: str,
        snapshot: Mapping[str, Any],
        ingestion_run_id: int | None = None,
    ) -> int:
        """Create one point-in-time team snapshot."""

        try:
            cursor = self.connection.execute(
                """
                INSERT INTO team_snapshots (
                    season_id,
                    team_id,
                    snapshot_at,
                    ingestion_run_id,
                    strength,
                    strength_overall_home,
                    strength_overall_away,
                    strength_attack_home,
                    strength_attack_away,
                    strength_defence_home,
                    strength_defence_away
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    season_id,
                    team_id,
                    snapshot_at,
                    ingestion_run_id,
                    self._value(snapshot, "strength"),
                    self._value(snapshot, "strength_overall_home"),
                    self._value(snapshot, "strength_overall_away"),
                    self._value(snapshot, "strength_attack_home"),
                    self._value(snapshot, "strength_attack_away"),
                    self._value(snapshot, "strength_defence_home"),
                    self._value(snapshot, "strength_defence_away"),
                ),
            )

            self._commit_if_needed()

            return int(cursor.lastrowid)

        except sqlite3.Error as exc:
            if not self._transaction_active:
                self.connection.rollback()

            raise RepositoryError(str(exc)) from exc

    def get_latest_team_snapshot(
        self,
        team_id: int,
        season_id: int,
    ) -> sqlite3.Row | None:
        """Return the latest team snapshot for a season."""
        return self.fetch_one(
            """
            SELECT *
            FROM team_snapshots
            WHERE team_id = ?
              AND season_id = ?
            ORDER BY snapshot_at DESC, id DESC
            LIMIT 1
            """,
            (
                team_id,
                season_id,
            ),
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

    def upsert_player(
        self,
        fpl_player_id: int,
        first_name: str | None = None,
        second_name: str | None = None,
        web_name: str | None = None,
    ) -> int:
        """
        Insert a player if it does not exist, otherwise update its
        stable descriptive identity fields.
        """

        timestamp = self._utc_now()

        try:
            self.connection.execute(
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
                ON CONFLICT(fpl_player_id)
                DO UPDATE SET
                    first_name = excluded.first_name,
                    second_name = excluded.second_name,
                    web_name = excluded.web_name,
                    updated_at = excluded.updated_at
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

            row = self.connection.execute(
                """
                SELECT id
                FROM players
                WHERE fpl_player_id = ?
                """,
                (fpl_player_id,),
            ).fetchone()

            if row is None:
                raise RepositoryError(
                    "Player upsert succeeded but the player could not be retrieved."
                )

            self._commit_if_needed()

            return int(row["id"])

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

    def create_player_snapshot(
        self,
        season_id: int,
        player_id: int,
        snapshot_at: str,
        snapshot: Mapping[str, Any],
        ingestion_run_id: int | None = None,
    ) -> int:
        """
        Create one point-in-time player snapshot.

        The snapshot mapping uses the canonical database field names.
        """

        columns = [
            "season_id",
            "player_id",
            "snapshot_at",
            "ingestion_run_id",
            "team_id",
            "position_id",
            "position",
            "price",
            "form",
            "total_points",
            "event_points",
            "points_per_game",
            "selected_by_percent",
            "minutes",
            "starts",
            "goals_scored",
            "assists",
            "clean_sheets",
            "expected_goals",
            "expected_assists",
            "expected_goal_involvements",
            "expected_goals_conceded",
            "bonus",
            "bps",
            "defensive_contribution",
            "influence",
            "creativity",
            "threat",
            "ict_index",
            "status",
            "chance_of_playing_this_round",
            "chance_of_playing_next_round",
            "news",
            "news_added",
            "transfers_in",
            "transfers_out",
            "transfers_in_event",
            "transfers_out_event",
            "can_select",
            "can_transact",
        ]

        values = [
            season_id,
            player_id,
            snapshot_at,
            ingestion_run_id,
            self._value(snapshot, "team_id"),
            self._value(snapshot, "position_id"),
            self._value(snapshot, "position"),
            self._value(snapshot, "price"),
            self._value(snapshot, "form"),
            self._value(snapshot, "total_points"),
            self._value(snapshot, "event_points"),
            self._value(snapshot, "points_per_game"),
            self._value(snapshot, "selected_by_percent"),
            self._value(snapshot, "minutes"),
            self._value(snapshot, "starts"),
            self._value(snapshot, "goals_scored"),
            self._value(snapshot, "assists"),
            self._value(snapshot, "clean_sheets"),
            self._value(snapshot, "expected_goals"),
            self._value(snapshot, "expected_assists"),
            self._value(snapshot, "expected_goal_involvements"),
            self._value(snapshot, "expected_goals_conceded"),
            self._value(snapshot, "bonus"),
            self._value(snapshot, "bps"),
            self._value(snapshot, "defensive_contribution"),
            self._value(snapshot, "influence"),
            self._value(snapshot, "creativity"),
            self._value(snapshot, "threat"),
            self._value(snapshot, "ict_index"),
            self._value(snapshot, "status"),
            self._value(snapshot, "chance_of_playing_this_round"),
            self._value(snapshot, "chance_of_playing_next_round"),
            self._value(snapshot, "news"),
            self._value(snapshot, "news_added"),
            self._value(snapshot, "transfers_in"),
            self._value(snapshot, "transfers_out"),
            self._value(snapshot, "transfers_in_event"),
            self._value(snapshot, "transfers_out_event"),
            self._value(snapshot, "can_select"),
            self._value(snapshot, "can_transact"),
        ]

        placeholders = ", ".join("?" for _ in columns)
        column_sql = ", ".join(columns)

        try:
            cursor = self.connection.execute(
                f"""
                INSERT INTO player_snapshots (
                    {column_sql}
                )
                VALUES ({placeholders})
                """,
                values,
            )

            self._commit_if_needed()

            return int(cursor.lastrowid)

        except sqlite3.Error as exc:
            if not self._transaction_active:
                self.connection.rollback()

            raise RepositoryError(str(exc)) from exc

    def get_latest_player_snapshot(
        self,
        player_id: int,
        season_id: int,
    ) -> sqlite3.Row | None:
        """Return the latest player snapshot for a season."""
        return self.fetch_one(
            """
            SELECT *
            FROM player_snapshots
            WHERE player_id = ?
              AND season_id = ?
            ORDER BY snapshot_at DESC, id DESC
            LIMIT 1
            """,
            (
                player_id,
                season_id,
            ),
        )

    # ------------------------------------------------------------------
    # Fixture methods
    # ------------------------------------------------------------------

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
        """
        Insert or update a fixture.

        The official FPL fixture ID is the stable external identity.
        """

        timestamp = self._utc_now()

        try:
            self.connection.execute(
                """
                INSERT INTO fixtures (
                    fpl_fixture_id,
                    season_id,
                    gameweek_id,
                    home_team_id,
                    away_team_id,
                    kickoff_time,
                    started,
                    finished,
                    home_score,
                    away_score,
                    home_difficulty,
                    away_difficulty,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(fpl_fixture_id)
                DO UPDATE SET
                    season_id = excluded.season_id,
                    gameweek_id = excluded.gameweek_id,
                    home_team_id = excluded.home_team_id,
                    away_team_id = excluded.away_team_id,
                    kickoff_time = excluded.kickoff_time,
                    started = excluded.started,
                    finished = excluded.finished,
                    home_score = excluded.home_score,
                    away_score = excluded.away_score,
                    home_difficulty = excluded.home_difficulty,
                    away_difficulty = excluded.away_difficulty,
                    updated_at = excluded.updated_at
                """,
                (
                    fpl_fixture_id,
                    season_id,
                    gameweek_id,
                    home_team_id,
                    away_team_id,
                    kickoff_time,
                    int(started),
                    int(finished),
                    home_score,
                    away_score,
                    home_difficulty,
                    away_difficulty,
                    timestamp,
                    timestamp,
                ),
            )

            row = self.connection.execute(
                """
                SELECT id
                FROM fixtures
                WHERE fpl_fixture_id = ?
                """,
                (fpl_fixture_id,),
            ).fetchone()

            if row is None:
                raise RepositoryError(
                    "Fixture upsert succeeded but the fixture could not be retrieved."
                )

            self._commit_if_needed()

            return int(row["id"])

        except sqlite3.Error as exc:
            if not self._transaction_active:
                self.connection.rollback()

            raise RepositoryError(str(exc)) from exc

    def get_fixture(
        self,
        fpl_fixture_id: int,
    ) -> sqlite3.Row | None:
        """Return a fixture by official FPL fixture ID."""
        return self.fetch_one(
            """
            SELECT *
            FROM fixtures
            WHERE fpl_fixture_id = ?
            """,
            (fpl_fixture_id,),
        )

    def get_fixtures_for_gameweek(
        self,
        season_id: int,
        gameweek_id: int,
    ) -> list[sqlite3.Row]:
        """Return all fixtures belonging to a gameweek."""
        return self.fetch_all(
            """
            SELECT *
            FROM fixtures
            WHERE season_id = ?
              AND gameweek_id = ?
            ORDER BY kickoff_time ASC, id ASC
            """,
            (
                season_id,
                gameweek_id,
            ),
        )

    # ------------------------------------------------------------------
    # Current player-gameweek statistics
    # ------------------------------------------------------------------

    def upsert_current_player_gameweek_stats(
        self,
        season_id: int,
        player_id: int,
        fixture_id: int,
        stats: Mapping[str, Any],
        gameweek_id: int | None = None,
        ingestion_run_id: int | None = None,
    ) -> int:
        """
        Insert or update current-season player-fixture statistics.

        The natural persistence grain is:

            season + player + fixture
        """

        columns = [
            "season_id",
            "gameweek_id",
            "player_id",
            "fixture_id",
            "opponent_team_id",
            "was_home",
            "kickoff_time",
            "minutes",
            "starts",
            "total_points",
            "goals_scored",
            "assists",
            "clean_sheets",
            "goals_conceded",
            "own_goals",
            "penalties_saved",
            "penalties_missed",
            "saves",
            "bonus",
            "bps",
            "yellow_cards",
            "red_cards",
            "expected_goals",
            "expected_assists",
            "expected_goal_involvements",
            "expected_goals_conceded",
            "influence",
            "creativity",
            "threat",
            "ict_index",
            "clearances_blocks_interceptions",
            "recoveries",
            "tackles",
            "defensive_contribution",
            "value",
            "selected",
            "transfers_balance",
            "transfers_in",
            "transfers_out",
            "ingestion_run_id",
        ]

        values = [
            season_id,
            gameweek_id,
            player_id,
            fixture_id,
            self._value(stats, "opponent_team_id"),
            self._value(stats, "was_home"),
            self._value(stats, "kickoff_time"),
            self._value(stats, "minutes"),
            self._value(stats, "starts"),
            self._value(stats, "total_points"),
            self._value(stats, "goals_scored"),
            self._value(stats, "assists"),
            self._value(stats, "clean_sheets"),
            self._value(stats, "goals_conceded"),
            self._value(stats, "own_goals"),
            self._value(stats, "penalties_saved"),
            self._value(stats, "penalties_missed"),
            self._value(stats, "saves"),
            self._value(stats, "bonus"),
            self._value(stats, "bps"),
            self._value(stats, "yellow_cards"),
            self._value(stats, "red_cards"),
            self._value(stats, "expected_goals"),
            self._value(stats, "expected_assists"),
            self._value(stats, "expected_goal_involvements"),
            self._value(stats, "expected_goals_conceded"),
            self._value(stats, "influence"),
            self._value(stats, "creativity"),
            self._value(stats, "threat"),
            self._value(stats, "ict_index"),
            self._value(stats, "clearances_blocks_interceptions"),
            self._value(stats, "recoveries"),
            self._value(stats, "tackles"),
            self._value(stats, "defensive_contribution"),
            self._value(stats, "value"),
            self._value(stats, "selected"),
            self._value(stats, "transfers_balance"),
            self._value(stats, "transfers_in"),
            self._value(stats, "transfers_out"),
            ingestion_run_id,
        ]

        update_columns = [
            column
            for column in columns
            if column not in {"season_id", "player_id", "fixture_id"}
        ]

        update_sql = ", ".join(
            f"{column} = excluded.{column}"
            for column in update_columns
        )

        placeholders = ", ".join("?" for _ in columns)
        column_sql = ", ".join(columns)

        try:
            self.connection.execute(
                f"""
                INSERT INTO current_player_gameweek_stats (
                    {column_sql}
                )
                VALUES ({placeholders})
                ON CONFLICT(season_id, player_id, fixture_id)
                DO UPDATE SET
                    {update_sql}
                """,
                values,
            )

            row = self.connection.execute(
                """
                SELECT id
                FROM current_player_gameweek_stats
                WHERE season_id = ?
                  AND player_id = ?
                  AND fixture_id = ?
                """,
                (
                    season_id,
                    player_id,
                    fixture_id,
                ),
            ).fetchone()

            if row is None:
                raise RepositoryError(
                    "Player-GW stats upsert succeeded but the record "
                    "could not be retrieved."
                )

            self._commit_if_needed()

            return int(row["id"])

        except sqlite3.Error as exc:
            if not self._transaction_active:
                self.connection.rollback()

            raise RepositoryError(str(exc)) from exc

    def get_current_player_gameweek_stats(
        self,
        season_id: int,
        player_id: int,
        fixture_id: int,
    ) -> sqlite3.Row | None:
        """Return current-season statistics for one player-fixture pair."""
        return self.fetch_one(
            """
            SELECT *
            FROM current_player_gameweek_stats
            WHERE season_id = ?
              AND player_id = ?
              AND fixture_id = ?
            """,
            (
                season_id,
                player_id,
                fixture_id,
            ),
        )