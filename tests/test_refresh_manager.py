"""
Tests for FPL refresh orchestration.

Batch 3 adds SQLite persistence for global FPL data while retaining
the existing JSON persistence path for backward compatibility.
"""

from typing import Generator

import pytest

from data_store import JsonDataStore
from sqlite_db import initialize_database
from fpl_data_source import FPLDataSource
from refresh_manager import FPLRefreshManager
from sqlite_repository import SQLiteRepository


class FakeFPLSource(FPLDataSource):
    """
    Fake FPL source used by tests.

    No live network calls are made.
    """

    def __init__(self):
        super().__init__(base_url="https://example.invalid")

        self.bootstrap_calls = 0
        self.fixture_calls = 0
        self.picks_calls = 0
        self.history_calls = 0

    def fetch_bootstrap_static(self):
        self.bootstrap_calls += 1

        return {
            "events": [
                {
                    "id": 1,
                    "name": "Gameweek 1",
                    "deadline_time": "2026-08-21T17:30:00Z",
                    "finished": True,
                    "data_checked": True,
                    "is_current": False,
                    "is_next": False,
                    "is_previous": True,
                },
                {
                    "id": 2,
                    "name": "Gameweek 2",
                    "deadline_time": "2026-08-28T17:30:00Z",
                    "finished": False,
                    "data_checked": False,
                    "is_current": True,
                    "is_next": False,
                    "is_previous": False,
                },
            ],
            "teams": [
                {
                    "id": 1,
                    "name": "Team A",
                    "short_name": "TMA",
                    "code": 101,
                    "strength": 4,
                    "strength_overall_home": 1100,
                    "strength_overall_away": 1050,
                    "strength_attack_home": 1100,
                    "strength_attack_away": 1050,
                    "strength_defence_home": 1080,
                    "strength_defence_away": 1030,
                },
                {
                    "id": 2,
                    "name": "Team B",
                    "short_name": "TMB",
                    "code": 102,
                    "strength": 3,
                    "strength_overall_home": 1000,
                    "strength_overall_away": 980,
                    "strength_attack_home": 1010,
                    "strength_attack_away": 990,
                    "strength_defence_home": 1000,
                    "strength_defence_away": 970,
                },
            ],
            "element_types": [
                {
                    "id": 1,
                    "singular_name": "Goalkeeper",
                },
                {
                    "id": 2,
                    "singular_name": "Defender",
                },
                {
                    "id": 3,
                    "singular_name": "Midfielder",
                },
                {
                    "id": 4,
                    "singular_name": "Forward",
                },
            ],
            "elements": [
                {
                    "id": 1,
                    "first_name": "Player",
                    "second_name": "A",
                    "web_name": "PlayerA",
                    "team": 1,
                    "element_type": 3,
                    "now_cost": 70,
                    "form": "5.0",
                    "total_points": 20,
                    "event_points": 6,
                    "points_per_game": "5.0",
                    "selected_by_percent": "10.0",
                    "minutes": 180,
                    "starts": 2,
                    "goals_scored": 1,
                    "assists": 1,
                    "clean_sheets": 1,
                    "expected_goals": "0.80",
                    "expected_assists": "0.40",
                    "expected_goal_involvements": "1.20",
                    "expected_goals_conceded": "1.00",
                    "bonus": 3,
                    "bps": 60,
                    "defensive_contribution": 4,
                    "influence": "20.0",
                    "creativity": "30.0",
                    "threat": "40.0",
                    "ict_index": "9.0",
                    "status": "a",
                    "chance_of_playing_this_round": 100,
                    "chance_of_playing_next_round": 100,
                    "news": "",
                    "news_added": None,
                    "transfers_in": 100,
                    "transfers_out": 50,
                    "transfers_in_event": 20,
                    "transfers_out_event": 10,
                    "can_select": True,
                    "can_transact": True,
                },
                {
                    "id": 2,
                    "first_name": "Player",
                    "second_name": "B",
                    "web_name": "PlayerB",
                    "team": 2,
                    "element_type": 4,
                    "now_cost": 65,
                    "form": "4.0",
                    "total_points": 18,
                    "event_points": 5,
                    "points_per_game": "4.5",
                    "selected_by_percent": "8.0",
                    "minutes": 170,
                    "starts": 2,
                    "goals_scored": 2,
                    "assists": 0,
                    "clean_sheets": 0,
                    "expected_goals": "1.00",
                    "expected_assists": "0.20",
                    "expected_goal_involvements": "1.20",
                    "expected_goals_conceded": "1.50",
                    "bonus": 2,
                    "bps": 50,
                    "defensive_contribution": 1,
                    "influence": "18.0",
                    "creativity": "15.0",
                    "threat": "45.0",
                    "ict_index": "8.0",
                    "status": "a",
                    "chance_of_playing_this_round": 100,
                    "chance_of_playing_next_round": 100,
                    "news": "",
                    "news_added": None,
                    "transfers_in": 80,
                    "transfers_out": 40,
                    "transfers_in_event": 15,
                    "transfers_out_event": 5,
                    "can_select": True,
                    "can_transact": True,
                },
            ],
        }

    def fetch_fixtures(self):
        self.fixture_calls += 1

        return [
            {
                "id": 101,
                "event": 2,
                "team_h": 1,
                "team_a": 2,
                "kickoff_time": "2026-08-29T15:00:00Z",
                "started": True,
                "finished": True,
                "team_h_score": 2,
                "team_a_score": 1,
                "team_h_difficulty": 3,
                "team_a_difficulty": 4,
                "stats": [
                    {
                        "identifier": "minutes",
                        "h": [
                            {"element": 1, "value": 90},
                        ],
                        "a": [
                            {"element": 2, "value": 90},
                        ],
                    },
                    {
                        "identifier": "goals_scored",
                        "h": [
                            {"element": 1, "value": 1},
                        ],
                        "a": [
                            {"element": 2, "value": 1},
                        ],
                    },
                    {
                        "identifier": "assists",
                        "h": [
                            {"element": 1, "value": 1},
                        ],
                        "a": [],
                    },
                    {
                        "identifier": "total_points",
                        "h": [
                            {"element": 1, "value": 8},
                        ],
                        "a": [
                            {"element": 2, "value": 5},
                        ],
                    },
                    {
                        "identifier": "bonus",
                        "h": [
                            {"element": 1, "value": 3},
                        ],
                        "a": [
                            {"element": 2, "value": 1},
                        ],
                    },
                    {
                        "identifier": "bps",
                        "h": [
                            {"element": 1, "value": 40},
                        ],
                        "a": [
                            {"element": 2, "value": 25},
                        ],
                    },
                ],
            }
        ]

    def fetch_manager_entry(self, manager_id):
        return {
            "id": manager_id,
            "player_first_name": "Test",
            "player_last_name": "Manager",
            "name": "Test Team",
            "summary_overall_points": 317,
            "summary_overall_rank": 1000,
        }

    def fetch_manager_picks(
        self,
        manager_id,
        gameweek,
    ):
        self.picks_calls += 1

        return {
            "entry_history": {
                "event": gameweek,
                "points": 41,
                "total_points": 317,
                "rank": 500,
                "bank": 10,
                "value": 1005,
                "event_transfers": 1,
                "event_transfers_cost": 0,
                "points_on_bench": 4,
            },
            "picks": [
                {"element": 1, "position": 1, "multiplier": 2, "is_captain": True, "is_vice_captain": False, "purchase_price": 70},
                {"element": 2, "position": 2, "multiplier": 1, "is_captain": False, "is_vice_captain": True, "purchase_price": 65},
            ],
        }

    def fetch_manager_history(self, manager_id):
        self.history_calls += 1

        return {
            "chips": [{"name": "wildcard", "event": 2}],
            "current": [],
        }

    def fetch_manager_transfers(self, manager_id):
        return {
            "transfers": [
                {
                    "id": "transfer-1",
                    "event": 2,
                    "element_in": 1,
                    "element_out": 2,
                    "time": "2026-08-28T10:00:00Z",
                    "cost": 4,
                }
            ]
        }


@pytest.fixture
def sqlite_repository(
    tmp_path,
) -> Generator[SQLiteRepository, None, None]:
    """Provide an isolated SQLite repository for one test."""

    database_path = tmp_path / "fpl.db"

    # Create all approved SQLite tables before using the repository.
    initialize_database(database_path)

    repository = SQLiteRepository(
        database_path
    )

    try:
        yield repository
    finally:
        repository.close()


# ----------------------------------------------------------------------
# Existing JSON compatibility tests
# ----------------------------------------------------------------------


def test_global_refresh_stores_new_records(tmp_path):
    """The legacy JSON path still works."""

    source = FakeFPLSource()

    manager = FPLRefreshManager(
        source,
        JsonDataStore(tmp_path),
    )

    report = manager.refresh_global_data()

    assert report.status == "success"
    assert (
        report.collections["fpl_players"]["records_added"]
        == 2
    )
    assert (
        report.collections["fpl_fixtures"]["records_added"]
        == 1
    )


def test_second_refresh_detects_unchanged_records(tmp_path):
    """Repeated JSON refresh still detects unchanged records."""

    source = FakeFPLSource()

    manager = FPLRefreshManager(
        source,
        JsonDataStore(tmp_path),
    )

    manager.refresh_global_data()

    report = manager.refresh_global_data()

    assert (
        report.collections["fpl_players"]["records_added"]
        == 0
    )

    assert (
        report.collections["fpl_players"]["records_updated"]
        == 0
    )

    assert (
        report.collections["fpl_players"]["records_unchanged"]
        == 2
    )


def test_manager_refresh_is_user_scoped(tmp_path):
    """Manager JSON persistence remains user-scoped."""

    source = FakeFPLSource()

    store = JsonDataStore(tmp_path)

    manager = FPLRefreshManager(
        source,
        store,
    )

    report = manager.refresh_manager_data(
        3325156,
        6,
    )

    assert report.status == "success"

    assert (
        store.get_record(
            "manager_3325156_picks",
            "6",
        )
        is not None
    )

    assert (
        store.get_record(
            "manager_3325156_history",
            "season_history",
        )
        is not None
    )


# ----------------------------------------------------------------------
# Batch 3 SQLite tests
# ----------------------------------------------------------------------


def test_global_refresh_writes_sqlite_global_data(
    sqlite_repository,
):
    """Global refresh should populate the canonical SQLite tables."""

    source = FakeFPLSource()

    manager = FPLRefreshManager(
        source,
        repository=sqlite_repository,
        season_code="2026/27",
    )

    report = manager.refresh_global_data()

    assert report.status == "success", report.error

    assert report.collections["teams"]["records_written"] == 2
    assert report.collections["players"]["records_written"] == 2
    assert report.collections["fixtures"]["records_written"] == 1
    assert (
        report.collections["player_gameweek_stats"][
            "records_written"
        ]
        == 2
    )

    season = sqlite_repository.get_season(
        "2026/27"
    )

    assert season is not None

    gameweek = sqlite_repository.get_gameweek(
        int(season["id"]),
        2,
    )

    assert gameweek is not None

    team = sqlite_repository.get_team(1)

    assert team is not None
    assert team["name"] == "Team A"

    player = sqlite_repository.get_player(1)

    assert player is not None
    assert player["web_name"] == "PlayerA"

    fixture = sqlite_repository.get_fixture(101)

    assert fixture is not None
    assert fixture["home_score"] == 2
    assert fixture["away_score"] == 1


def test_global_refresh_creates_ingestion_run(
    sqlite_repository,
):
    """Every SQLite global refresh must create a provenance record."""

    source = FakeFPLSource()

    manager = FPLRefreshManager(
        source,
        repository=sqlite_repository,
    )

    report = manager.refresh_global_data()

    assert report.status == "success"

    rows = sqlite_repository.fetch_all(
        """
        SELECT *
        FROM ingestion_runs
        ORDER BY id
        """
    )

    assert len(rows) == 1

    ingestion_run = rows[0]

    assert ingestion_run["source_system"] == "fpl_api"
    assert ingestion_run["status"] == "SUCCESS"
    assert (
        ingestion_run["validation_status"]
        == "PASSED"
    )


def test_global_refresh_creates_player_snapshots(
    sqlite_repository,
):
    """Player bootstrap data should become current-season snapshots."""

    source = FakeFPLSource()

    manager = FPLRefreshManager(
        source,
        repository=sqlite_repository,
    )

    report = manager.refresh_global_data()

    assert report.status == "success"

    player = sqlite_repository.get_player(1)

    assert player is not None

    snapshot = sqlite_repository.get_latest_player_snapshot(
        player_id=int(player["id"]),
        season_id=int(
            sqlite_repository.get_season(
                "2026/27"
            )["id"]
        ),
    )

    assert snapshot is not None
    assert snapshot["price"] == 70.0
    assert snapshot["status"] == "a"

    # web_name belongs to the players master table, not player_snapshots.
    assert player["web_name"] == "PlayerA"


def test_global_refresh_creates_team_snapshots(
    sqlite_repository,
):
    """Team bootstrap data should become current-season snapshots."""

    source = FakeFPLSource()

    manager = FPLRefreshManager(
        source,
        repository=sqlite_repository,
    )

    report = manager.refresh_global_data()

    assert report.status == "success"

    team = sqlite_repository.get_team(1)

    assert team is not None

    season = sqlite_repository.get_season(
        "2026/27"
    )

    assert season is not None

    snapshot = (
        sqlite_repository.get_latest_team_snapshot(
            team_id=int(team["id"]),
            season_id=int(season["id"]),
        )
    )

    assert snapshot is not None
    assert snapshot["strength"] == 4


def test_global_refresh_creates_current_player_gameweek_stats(
    sqlite_repository,
):
    """Fixture stats should become canonical player-GW records."""

    source = FakeFPLSource()

    manager = FPLRefreshManager(
        source,
        repository=sqlite_repository,
    )

    report = manager.refresh_global_data()

    assert report.status == "success"

    season = sqlite_repository.get_season(
        "2026/27"
    )

    assert season is not None

    gameweek = sqlite_repository.get_gameweek(
        int(season["id"]),
        2,
    )

    assert gameweek is not None

    fixture = sqlite_repository.get_fixture(
        101,
    )

    assert fixture is not None

    player_a = sqlite_repository.get_player(1)
    player_b = sqlite_repository.get_player(2)

    assert player_a is not None
    assert player_b is not None

    player_a_stats = sqlite_repository.get_current_player_gameweek_stats(
        season_id=int(season["id"]),
        player_id=int(player_a["id"]),
        fixture_id=int(fixture["id"]),
    )

    player_b_stats = sqlite_repository.get_current_player_gameweek_stats(
        season_id=int(season["id"]),
        player_id=int(player_b["id"]),
        fixture_id=int(fixture["id"]),
    )

    assert player_a_stats is not None
    assert player_b_stats is not None

    assert player_a_stats["minutes"] == 90
    assert player_a_stats["goals_scored"] == 1
    assert player_a_stats["assists"] == 1
    assert player_a_stats["total_points"] == 8


def test_global_refresh_is_repeatable(
    sqlite_repository,
):
    """
    Repeating a refresh should update existing master/current records
    rather than create duplicate teams, players or fixtures.
    """

    source = FakeFPLSource()

    manager = FPLRefreshManager(
        source,
        repository=sqlite_repository,
    )

    first_report = manager.refresh_global_data()
    second_report = manager.refresh_global_data()

    assert first_report.status == "success"
    assert second_report.status == "success"

    seasons = sqlite_repository.fetch_all(
        "SELECT * FROM seasons"
    )

    teams = sqlite_repository.fetch_all(
        "SELECT * FROM teams"
    )

    players = sqlite_repository.fetch_all(
        "SELECT * FROM players"
    )

    fixtures = sqlite_repository.fetch_all(
        "SELECT * FROM fixtures"
    )

    assert len(seasons) == 1
    assert len(teams) == 2
    assert len(players) == 2
    assert len(fixtures) == 1

    ingestion_runs = sqlite_repository.fetch_all(
        "SELECT * FROM ingestion_runs"
    )

    assert len(ingestion_runs) == 2


def test_global_refresh_rolls_back_partial_sqlite_persistence(
    tmp_path,
):
    """A persistence failure must roll back the entire canonical refresh."""

    class FailingRepository(SQLiteRepository):
        def __init__(self, db_path):
            initialize_database(db_path)
            super().__init__(db_path)
            self.fail_current_stats = True

        def upsert_current_player_gameweek_stats(self, *args, **kwargs):
            if self.fail_current_stats:
                raise RuntimeError(
                    "simulated player-GW persistence failure"
                )
            return super().upsert_current_player_gameweek_stats(
                *args,
                **kwargs,
            )

    # Use a repository owned by this test so the failure simulation cannot
    # interfere with the shared test fixture lifecycle.
    failing_repository = FailingRepository(tmp_path / "fpl.db")

    try:
        source = FakeFPLSource()
        manager = FPLRefreshManager(
            source,
            repository=failing_repository,
        )

        report = manager.refresh_global_data()

        assert report.status == "failed"
        assert (
            "simulated player-GW persistence failure"
            in report.error
        )

        # All canonical writes from the failed refresh must have rolled back.
        assert failing_repository.fetch_one(
            "SELECT COUNT(*) AS count FROM seasons"
        )["count"] == 0
        assert failing_repository.fetch_one(
            "SELECT COUNT(*) AS count FROM gameweeks"
        )["count"] == 0
        assert failing_repository.fetch_one(
            "SELECT COUNT(*) AS count FROM teams"
        )["count"] == 0
        assert failing_repository.fetch_one(
            "SELECT COUNT(*) AS count FROM team_snapshots"
        )["count"] == 0
        assert failing_repository.fetch_one(
            "SELECT COUNT(*) AS count FROM players"
        )["count"] == 0
        assert failing_repository.fetch_one(
            "SELECT COUNT(*) AS count FROM player_snapshots"
        )["count"] == 0
        assert failing_repository.fetch_one(
            "SELECT COUNT(*) AS count FROM fixtures"
        )["count"] == 0
        assert failing_repository.fetch_one(
            "SELECT COUNT(*) AS count FROM current_player_gameweek_stats"
        )["count"] == 0

        # The ingestion audit record must survive the rollback and show FAILED.
        ingestion_run = failing_repository.fetch_one(
            "SELECT * FROM ingestion_runs ORDER BY id DESC LIMIT 1"
        )
        assert ingestion_run is not None
        assert ingestion_run["status"] == "FAILED"
        assert ingestion_run["validation_status"] == "FAILED"

        # The failed attempt must not be reported as a successful refresh.
        for dataset_name in ("bootstrap_static", "fixtures"):
            freshness = failing_repository.get_dataset_freshness(
                dataset_name
            )
            assert freshness is not None
            assert freshness["last_successful_ingestion_id"] is None
            assert freshness["freshness_status"] == "STALE"
    finally:
        failing_repository.close()


def test_global_refresh_recovers_after_atomic_persistence_failure(
    tmp_path,
):
    """A later successful refresh should work normally after a rolled-back failure."""

    class FailOnceRepository(SQLiteRepository):
        def __init__(self, db_path):
            initialize_database(db_path)
            super().__init__(db_path)
            self.fail_once = True

        def upsert_current_player_gameweek_stats(self, *args, **kwargs):
            if self.fail_once:
                self.fail_once = False
                raise RuntimeError("fail once")
            return super().upsert_current_player_gameweek_stats(
                *args,
                **kwargs,
            )

    repository = FailOnceRepository(tmp_path / "fpl.db")

    try:
        manager = FPLRefreshManager(
            FakeFPLSource(),
            repository=repository,
        )

        first_report = manager.refresh_global_data()
        second_report = manager.refresh_global_data()

        assert first_report.status == "failed"
        assert second_report.status == "success"

        assert repository.fetch_one(
            "SELECT COUNT(*) AS count FROM teams"
        )["count"] == 2
        assert repository.fetch_one(
            "SELECT COUNT(*) AS count FROM players"
        )["count"] == 2
        assert repository.fetch_one(
            "SELECT COUNT(*) AS count FROM fixtures"
        )["count"] == 1

        ingestion_runs = repository.fetch_all(
            "SELECT status FROM ingestion_runs ORDER BY id"
        )
        assert [row["status"] for row in ingestion_runs] == [
            "FAILED",
            "SUCCESS",
        ]
    finally:
        repository.close()


def test_global_refresh_failure_is_recorded(
    sqlite_repository,
):
    """A failed SQLite refresh should record a failed ingestion run."""

    class BrokenSource(FakeFPLSource):
        def fetch_fixtures(self):
            raise RuntimeError(
                "fixture endpoint unavailable"
            )

    source = BrokenSource()

    manager = FPLRefreshManager(
        source,
        repository=sqlite_repository,
    )

    report = manager.refresh_global_data()

    assert report.status == "failed"
    assert (
        "fixture endpoint unavailable"
        in report.error
    )

    # Because the ingestion run is created only after the
    # source retrieval succeeds, a failure during source
    # retrieval does not create a misleading completed run.
    rows = sqlite_repository.fetch_all(
        "SELECT * FROM ingestion_runs"
    )

    assert len(rows) == 0
# ----------------------------------------------------------------------
# Batch 5 SQLite manager-state tests
# ----------------------------------------------------------------------


def test_manager_refresh_persists_sqlite_state(sqlite_repository):
    """Manager refresh should persist canonical SQLite manager state."""

    source = FakeFPLSource()
    manager = FPLRefreshManager(
        source,
        repository=sqlite_repository,
        season_code="2026/27",
    )

    global_report = manager.refresh_global_data()
    assert global_report.status == "success", global_report.error

    report = manager.refresh_manager_data(3325156, 2)

    assert report.status == "success", report.error
    assert report.collections["manager"]["records_written"] == 1
    assert report.collections["manager_picks"]["records_written"] == 2
    assert report.collections["manager_transfers"]["records_written"] == 1
    assert report.collections["manager_chips"]["records_written"] == 1

    user = sqlite_repository.fetch_one(
        "SELECT * FROM users WHERE external_user_key = ?",
        ("3325156",),
    )
    assert user is not None

    manager_row = sqlite_repository.fetch_one(
        "SELECT * FROM managers WHERE fpl_manager_id = ?",
        (3325156,),
    )
    assert manager_row is not None

    season = sqlite_repository.get_season("2026/27")
    gameweek = sqlite_repository.get_gameweek(int(season["id"]), 2)

    state = sqlite_repository.fetch_one(
        """SELECT * FROM manager_gameweek_state
           WHERE manager_id = ? AND season_id = ? AND gameweek_id = ?""",
        (int(manager_row["id"]), int(season["id"]), int(gameweek["id"])),
    )
    assert state["points"] == 41
    assert state["total_points"] == 317
    assert state["bank"] == 1.0
    assert state["team_value"] == 100.5

    picks = sqlite_repository.fetch_all(
        """SELECT * FROM manager_picks
           WHERE manager_id = ? AND season_id = ? AND gameweek_id = ?
           ORDER BY player_id""",
        (int(manager_row["id"]), int(season["id"]), int(gameweek["id"])),
    )
    assert len(picks) == 2
    assert any(row["is_captain"] == 1 for row in picks)

    transfers = sqlite_repository.fetch_all(
        "SELECT * FROM manager_transfers WHERE manager_id = ?",
        (int(manager_row["id"]),),
    )
    assert len(transfers) == 1
    assert transfers[0]["external_transfer_id"] == "transfer-1"

    chips = sqlite_repository.fetch_all(
        "SELECT * FROM manager_chips WHERE manager_id = ?",
        (int(manager_row["id"]),),
    )
    assert len(chips) == 1
    assert chips[0]["chip_type"] == "wildcard"

    runs = sqlite_repository.fetch_all(
        """SELECT * FROM ingestion_runs
           WHERE endpoint_or_file LIKE ?
           ORDER BY id DESC""",
        ("entry/3325156/%",),
    )
    assert len(runs) == 1
    assert runs[0]["status"] == "SUCCESS"


def test_manager_refresh_requires_global_sqlite_state(sqlite_repository):
    """SQLite manager refresh must not invent missing global reference data."""

    source = FakeFPLSource()
    manager = FPLRefreshManager(
        source,
        repository=sqlite_repository,
        season_code="2026/27",
    )

    report = manager.refresh_manager_data(3325156, 2)

    assert report.status == "failed"
    assert "Run the global refresh before manager refresh" in report.error


def test_manager_refresh_is_repeatable_for_transfers(sqlite_repository):
    """Refreshing the same manager twice must not duplicate transfers."""

    source = FakeFPLSource()
    manager = FPLRefreshManager(
        source, repository=sqlite_repository, season_code="2026/27"
    )

    assert manager.refresh_global_data().status == "success"
    assert manager.refresh_manager_data(3325156, 2).status == "success"
    assert manager.refresh_manager_data(3325156, 2).status == "success"

    rows = sqlite_repository.fetch_all(
        "SELECT * FROM manager_transfers WHERE manager_id = ?",
        (1,),
    )
    assert len(rows) == 1


def test_manager_refresh_failure_completes_ingestion_run(sqlite_repository):
    """A failure after ingestion-run creation should be recorded as FAILED."""

    class BrokenManagerSource(FakeFPLSource):
        def fetch_manager_picks(self, manager_id, gameweek):
            return {
                "entry_history": {"event": gameweek, "points": 1},
                "picks": [{"element": 999, "position": 1}],
            }

    source = BrokenManagerSource()
    manager = FPLRefreshManager(
        source, repository=sqlite_repository, season_code="2026/27"
    )
    assert manager.refresh_global_data().status == "success"

    report = manager.refresh_manager_data(3325156, 2)

    assert report.status == "failed"
    runs = sqlite_repository.fetch_all(
        "SELECT * FROM ingestion_runs WHERE endpoint_or_file LIKE ?",
        ("entry/3325156/%",),
    )
    assert len(runs) == 1
    assert runs[0]["status"] == "FAILED"


# ----------------------------------------------------------------------
# Batch 6 multi-league / rival tests
# ----------------------------------------------------------------------


def test_manager_refresh_supports_multiple_leagues_with_overlapping_rivals(
    sqlite_repository,
):
    """The same rival can belong to multiple leagues with different ranks."""

    class MultiLeagueSource(FakeFPLSource):
        def __init__(self):
            super().__init__()
            self.league_calls = []
            self.rival_pick_calls = []

        def fetch_classic_league_standings(self, league_id, page=1, event=None):
            self.league_calls.append((league_id, page, event))

            standings_by_league = {
                111: [
                    {"id": 3325156, "player_name": "Test Manager", "entry_name": "My Team", "rank": 1, "last_rank": 2, "total": 200},
                    {"id": 1001, "player_name": "Rival One", "entry_name": "Rival Team One", "rank": 2, "last_rank": 4, "total": 190},
                    {"id": 1002, "player_name": "Rival Two", "entry_name": "Rival Team Two", "rank": 3, "last_rank": 3, "total": 185},
                ],
                222: [
                    {"id": 3325156, "player_name": "Test Manager", "entry_name": "My Team", "rank": 10, "last_rank": 8, "total": 200},
                    {"id": 1001, "player_name": "Rival One", "entry_name": "Rival Team One", "rank": 5, "last_rank": 7, "total": 175},
                    {"id": 1003, "player_name": "Rival Three", "entry_name": "Rival Team Three", "rank": 2, "last_rank": 2, "total": 188},
                ],
            }
            return {
                "league": {
                    "id": league_id,
                    "name": f"League {league_id}",
                    "league_type": "classic",
                },
                "standings": {
                    "results": standings_by_league[league_id],
                    "has_next": False,
                },
            }

        def fetch_manager_picks(self, manager_id, gameweek):
            if manager_id not in (3325156,):
                self.rival_pick_calls.append(manager_id)
            return super().fetch_manager_picks(manager_id, gameweek)

    source = MultiLeagueSource()
    manager = FPLRefreshManager(
        source,
        repository=sqlite_repository,
        season_code="2026/27",
    )

    assert manager.refresh_global_data().status == "success"

    report = manager.refresh_manager_data(
        3325156,
        2,
        league_ids=[111, 222],
    )

    assert report.status == "success", report.error
    assert report.collections["leagues"]["records_written"] == 2
    assert report.collections["league_members"]["records_written"] == 6
    assert report.collections["league_standings"]["records_written"] == 6
    assert report.collections["rival_squad_snapshots"]["records_written"] == 8

    # Rival 1001 is present in both leagues, but its picks are fetched once.
    assert sorted(source.rival_pick_calls) == [1001, 1002, 1003]

    leagues = sqlite_repository.fetch_all(
        "SELECT * FROM leagues ORDER BY fpl_league_id"
    )
    assert [row["fpl_league_id"] for row in leagues] == [111, 222]

    rival_one = sqlite_repository.fetch_one(
        "SELECT id FROM managers WHERE fpl_manager_id = ?",
        (1001,),
    )
    assert rival_one is not None

    standings = sqlite_repository.fetch_all(
        """
        SELECT l.fpl_league_id, s.rank, s.total_points
        FROM league_standings s
        JOIN leagues l ON l.id = s.league_id
        WHERE s.manager_id = ?
        ORDER BY l.fpl_league_id
        """,
        (int(rival_one["id"]),),
    )

    assert [(row["fpl_league_id"], row["rank"], row["total_points"]) for row in standings] == [
        (111, 2, 190),
        (222, 5, 175),
    ]

    snapshot_counts = sqlite_repository.fetch_all(
        """
        SELECT l.fpl_league_id, COUNT(*) AS snapshot_count
        FROM rival_squad_snapshots r
        JOIN leagues l ON l.id = r.league_id
        WHERE r.manager_id = ?
        GROUP BY l.fpl_league_id
        ORDER BY l.fpl_league_id
        """,
        (int(rival_one["id"]),),
    )

    assert [
        (row["fpl_league_id"], row["snapshot_count"])
        for row in snapshot_counts
    ] == [(111, 2), (222, 2)]

    # Repeating the refresh must not create duplicate league state.
    second_report = manager.refresh_manager_data(
        3325156,
        2,
        league_ids=[111, 222],
    )
    assert second_report.status == "success", second_report.error

    assert sqlite_repository.fetch_one(
        "SELECT COUNT(*) AS count FROM leagues"
    )["count"] == 2
    assert sqlite_repository.fetch_one(
        "SELECT COUNT(*) AS count FROM league_members"
    )["count"] == 6
    assert sqlite_repository.fetch_one(
        "SELECT COUNT(*) AS count FROM league_standings"
    )["count"] == 6
    assert sqlite_repository.fetch_one(
        "SELECT COUNT(*) AS count FROM rival_squad_snapshots"
    )["count"] == 8

# ----------------------------------------------------------------------
# Batch 7 freshness-aware refresh tests
# ----------------------------------------------------------------------


def test_refresh_if_needed_skips_fresh_global_data(sqlite_repository):
    """A second global refresh check should use stored freshness."""

    source = FakeFPLSource()
    manager = FPLRefreshManager(
        source,
        repository=sqlite_repository,
        season_code="2026/27",
    )

    first = manager.refresh_if_needed()
    assert first.status == "success", first.error
    assert source.bootstrap_calls == 1
    assert source.fixture_calls == 1

    second = manager.refresh_if_needed()
    assert second.status == "skipped"
    assert source.bootstrap_calls == 1
    assert source.fixture_calls == 1

    bootstrap = sqlite_repository.get_dataset_freshness("bootstrap_static")
    fixtures = sqlite_repository.get_dataset_freshness("fixtures")

    assert bootstrap is not None
    assert fixtures is not None
    assert bootstrap["freshness_status"] == "FRESH"
    assert fixtures["freshness_status"] == "FRESH"


def test_refresh_if_needed_refreshes_stale_global_data(sqlite_repository):
    """A stale global dataset should trigger a new global refresh."""

    source = FakeFPLSource()
    manager = FPLRefreshManager(
        source,
        repository=sqlite_repository,
        season_code="2026/27",
    )

    assert manager.refresh_if_needed().status == "success"
    assert source.bootstrap_calls == 1

    sqlite_repository.upsert_dataset_freshness(
        dataset_name="bootstrap_static",
        last_successful_refresh_at="2020-01-01T00:00:00+00:00",
        freshness_status="STALE",
    )

    report = manager.refresh_if_needed()

    assert report.status == "success", report.error
    assert source.bootstrap_calls == 2
    assert source.fixture_calls == 2


def test_refresh_if_needed_skips_fresh_manager_state(sqlite_repository):
    """Manager refresh should also become freshness-aware."""

    source = FakeFPLSource()
    manager = FPLRefreshManager(
        source,
        repository=sqlite_repository,
        season_code="2026/27",
    )

    first = manager.refresh_if_needed(manager_id=3325156, gameweek=2)
    assert first.status == "success", first.error
    assert source.picks_calls == 1

    second = manager.refresh_if_needed(manager_id=3325156, gameweek=2)
    assert second.status == "skipped"
    assert source.picks_calls == 1

    freshness = sqlite_repository.get_dataset_freshness("manager_state:3325156")
    assert freshness is not None
    assert freshness["freshness_status"] == "FRESH"


def test_failed_global_refresh_does_not_mark_dataset_fresh(sqlite_repository):
    """A validation failure after ingestion starts must leave freshness stale."""

    class BrokenBootstrapSource(FakeFPLSource):
        def fetch_bootstrap_static(self):
            payload = super().fetch_bootstrap_static()
            payload["elements"] = {"invalid": True}
            return payload

    source = BrokenBootstrapSource()
    manager = FPLRefreshManager(
        source,
        repository=sqlite_repository,
        season_code="2026/27",
    )

    report = manager.refresh_if_needed()

    assert report.status == "failed"

    bootstrap = sqlite_repository.get_dataset_freshness("bootstrap_static")
    fixtures = sqlite_repository.get_dataset_freshness("fixtures")

    assert bootstrap is not None
    assert fixtures is not None
    assert bootstrap["freshness_status"] == "STALE"
    assert fixtures["freshness_status"] == "STALE"
    assert bootstrap["last_successful_ingestion_id"] is None
    assert fixtures["last_successful_ingestion_id"] is None
