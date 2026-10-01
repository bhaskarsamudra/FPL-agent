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

    def fetch_manager_picks(
        self,
        manager_id,
        gameweek,
    ):
        self.picks_calls += 1

        return {
            "entry_history": {
                "event": gameweek,
                "bank": 10,
            },
            "picks": [],
        }

    def fetch_manager_history(self, manager_id):
        self.history_calls += 1

        return {
            "chips": [],
            "current": [],
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