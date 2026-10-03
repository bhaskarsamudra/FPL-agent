"""Tests for the initial SQLite schema and database infrastructure."""

import sqlite3

import pytest

from sqlite_db import connect_sqlite, initialize_database, list_tables


EXPECTED_TABLES = {
    "schema_migrations",
    "seasons",
    "gameweeks",
    "teams",
    "team_snapshots",
    "players",
    "player_snapshots",
    "fixtures",
    "current_player_gameweek_stats",
    "historical_player_gameweek_stats",
    "historical_matches",
    "users",
    "managers",
    "manager_gameweek_state",
    "manager_picks",
    "manager_transfers",
    "manager_chips",
    "leagues",
    "league_members",
    "league_standings",
    "rival_squad_snapshots",
    "player_availability",
    "rules_versions",
    "rules_payload",
    "ingestion_runs",
    "dataset_freshness",
    "player_predictions",
    "prediction_outcomes",
    "strategy_memory",
    "recommendations",
    "recommendation_audits",
    "recommendation_outcomes",
    "data_lineage",
}


EXPECTED_INDEXES = {
    "idx_player_snapshots_player_season_snapshot",
    "idx_current_player_gw_stats_season_gw_player",
    "idx_historical_player_gw_stats_season_player_gw",
    "idx_fixtures_season_gameweek",
    "idx_fixtures_home_team_kickoff",
    "idx_fixtures_away_team_kickoff",
    "idx_manager_gameweek_state_manager_season_gw",
    "idx_manager_picks_manager_season_gw",
    "idx_league_standings_league_season_gw",
    "idx_rival_squad_snapshots_league_season_gw",
    "idx_player_predictions_season_gw_player",
    "idx_ingestion_runs_source_retrieved",
    "idx_dataset_freshness_status",
}


def test_initialize_database_creates_all_expected_tables(tmp_path):
    """A fresh database must contain the complete approved domain schema."""
    db_path = tmp_path / "fpl.db"
    initialize_database(db_path)

    assert set(list_tables(db_path)) == EXPECTED_TABLES


def test_foreign_keys_are_enabled(tmp_path):
    """Every connection must enforce SQLite foreign-key constraints."""
    db_path = tmp_path / "fpl.db"
    initialize_database(db_path)

    with connect_sqlite(db_path) as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO gameweeks(season_id, gameweek)
                VALUES (999999, 1)
                """
            )


def test_key_unique_constraints_are_enforced(tmp_path):
    """Representative business keys must reject duplicate records."""
    db_path = tmp_path / "fpl.db"
    initialize_database(db_path)

    with connect_sqlite(db_path) as connection:
        connection.execute(
            """
            INSERT INTO seasons(id, season_code, created_at, updated_at)
            VALUES (1, '2026/27', '2026-09-30T00:00:00Z', '2026-09-30T00:00:00Z')
            """
        )
        connection.execute(
            """
            INSERT INTO gameweeks(season_id, gameweek)
            VALUES (1, 1)
            """
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO gameweeks(season_id, gameweek)
                VALUES (1, 1)
                """
            )


def test_expected_indexes_exist(tmp_path):
    """Required query indexes must be created by schema initialization."""
    db_path = tmp_path / "fpl.db"
    initialize_database(db_path)

    with connect_sqlite(db_path) as connection:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'index'
              AND name NOT LIKE 'sqlite_%'
            """
        ).fetchall()

    actual_indexes = {row[0] for row in rows}
    assert EXPECTED_INDEXES.issubset(actual_indexes)


def test_schema_initialization_is_idempotent(tmp_path):
    """Running initialization repeatedly must not duplicate schema objects."""
    db_path = tmp_path / "fpl.db"

    initialize_database(db_path)
    first_tables = list_tables(db_path)

    initialize_database(db_path)
    second_tables = list_tables(db_path)

    assert first_tables == second_tables

    with connect_sqlite(db_path) as connection:
        migration_rows = connection.execute(
            "SELECT version, description FROM schema_migrations ORDER BY version"
        ).fetchall()

    assert [(row[0], row[1]) for row in migration_rows] == [
        (1, "Initial FPL Strategist domain schema")
    ]
