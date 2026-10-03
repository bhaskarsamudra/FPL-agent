"""Batch 17C SQLite idempotency regression tests."""

from copy import deepcopy

from refresh_manager import FPLRefreshManager
from sqlite_db import initialize_database
from sqlite_repository import SQLiteRepository
from test_refresh_manager import FakeFPLSource


def count(repository, table):
    row = repository.fetch_one(f"SELECT COUNT(*) AS count FROM {table}")
    return int(row["count"])


def make_repository(tmp_path):
    """Create the schema before opening the repository connection."""
    database_path = tmp_path / "fpl.db"
    initialize_database(database_path)
    return SQLiteRepository(database_path)


def test_identical_refresh_does_not_duplicate_master_or_current_state(tmp_path):
    source = FakeFPLSource()
    repo = make_repository(tmp_path)
    try:
        manager = FPLRefreshManager(source, repository=repo, season_code="2026/27")
        first = manager.refresh_global_data()
        second = manager.refresh_global_data()

        assert first.status == "success", first.error
        assert second.status == "success", second.error
        assert count(repo, "seasons") == 1
        assert count(repo, "gameweeks") == 2
        assert count(repo, "teams") == 2
        assert count(repo, "players") == 2
        assert count(repo, "fixtures") == 1
        assert count(repo, "current_player_gameweek_stats") == 2
        assert count(repo, "ingestion_runs") == 2
    finally:
        repo.close()


def test_identical_refresh_preserves_append_style_snapshots(tmp_path):
    """Snapshots are observations and intentionally remain append-style."""
    source = FakeFPLSource()
    repo = make_repository(tmp_path)
    try:
        manager = FPLRefreshManager(source, repository=repo, season_code="2026/27")
        first = manager.refresh_global_data()
        second = manager.refresh_global_data()

        assert first.status == "success", first.error
        assert second.status == "success", second.error
        assert count(repo, "player_snapshots") == 4
        assert count(repo, "team_snapshots") == 4
    finally:
        repo.close()


def test_changed_player_payload_updates_current_state_without_duplication(tmp_path):
    source = FakeFPLSource()
    repo = make_repository(tmp_path)
    try:
        manager = FPLRefreshManager(source, repository=repo, season_code="2026/27")
        first = manager.refresh_global_data()
        assert first.status == "success", first.error

        original_player = repo.get_player(1)
        assert original_player is not None
        original_stats = repo.fetch_one(
            """
            SELECT * FROM current_player_gameweek_stats
            WHERE player_id = ? ORDER BY id LIMIT 1
            """,
            (int(original_player["id"]),),
        )
        assert original_stats is not None

        changed = deepcopy(source.fetch_bootstrap_static())
        changed["elements"][0]["web_name"] = "PlayerA-Updated"
        source.fetch_bootstrap_static = lambda: changed

        second = manager.refresh_global_data()
        assert second.status == "success", second.error
        assert count(repo, "players") == 2
        assert count(repo, "current_player_gameweek_stats") == 2

        updated_player = repo.get_player(1)
        assert updated_player is not None
        assert updated_player["web_name"] == "PlayerA-Updated"

        updated_stats = repo.fetch_one(
            """
            SELECT * FROM current_player_gameweek_stats
            WHERE player_id = ? ORDER BY id LIMIT 1
            """,
            (int(updated_player["id"]),),
        )
        assert updated_stats is not None
        assert int(updated_stats["id"]) == int(original_stats["id"])
    finally:
        repo.close()


def test_changed_fixture_updates_existing_fixture_without_duplication(tmp_path):
    source = FakeFPLSource()
    repo = make_repository(tmp_path)
    try:
        manager = FPLRefreshManager(source, repository=repo, season_code="2026/27")
        first = manager.refresh_global_data()
        assert first.status == "success", first.error

        original = repo.get_fixture(101)
        assert original is not None
        original_id = int(original["id"])

        changed = deepcopy(source.fetch_fixtures())
        changed[0]["team_h_score"] = 3
        source.fetch_fixtures = lambda: changed

        second = manager.refresh_global_data()
        assert second.status == "success", second.error
        assert count(repo, "fixtures") == 1

        updated = repo.get_fixture(101)
        assert updated is not None
        assert int(updated["id"]) == original_id
        assert updated["home_score"] == 3
    finally:
        repo.close()


def test_successful_refresh_points_freshness_to_latest_ingestion(tmp_path):
    source = FakeFPLSource()
    repo = make_repository(tmp_path)
    try:
        manager = FPLRefreshManager(source, repository=repo, season_code="2026/27")
        first = manager.refresh_global_data()
        second = manager.refresh_global_data()
        assert first.status == "success", first.error
        assert second.status == "success", second.error

        runs = repo.fetch_all(
            "SELECT id, status FROM ingestion_runs ORDER BY id"
        )
        assert [row["status"] for row in runs] == ["SUCCESS", "SUCCESS"]

        freshness = repo.fetch_all(
            """
            SELECT * FROM dataset_freshness
            WHERE dataset_name IN ('bootstrap_static', 'fixtures')
            ORDER BY dataset_name
            """
        )
        assert len(freshness) == 2
        for row in freshness:
            assert row["freshness_status"] == "FRESH"
            assert int(row["last_successful_ingestion_id"]) == int(runs[-1]["id"])
            assert int(row["last_attempted_ingestion_id"]) == int(runs[-1]["id"])
    finally:
        repo.close()
