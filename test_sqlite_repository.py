"""
Tests for the SQLite repository foundation.

These tests verify that repository behaviour matches the approved
SQLite schema and repository contract.

The tests deliberately keep gameweek semantics separate from CRUD
lifecycle timestamps. Gameweeks are canonical football/FPL event
references and do not have created_at/updated_at columns.
"""

from pathlib import Path
from typing import Generator

import pytest

from repository import RepositoryError
from sqlite_db import initialize_database
from sqlite_repository import SQLiteRepository


@pytest.fixture
def repository(
    tmp_path: Path,
) -> Generator[SQLiteRepository, None, None]:
    """
    Create an isolated SQLite database for each test.

    The production database is never used by these tests.
    """

    database_path = tmp_path / "test_fpl.db"

    # Create the database schema using the existing schema foundation.
    initialize_database(database_path)

    repo = SQLiteRepository(database_path)

    yield repo

    repo.close()


# ----------------------------------------------------------------------
# Season tests
# ----------------------------------------------------------------------


def test_create_and_get_season(
    repository: SQLiteRepository,
):
    """A season can be created and retrieved by season code."""

    season_id = repository.create_season(
        season_code="2026-27",
        start_date="2026-08-01",
        status="ACTIVE",
        is_current=True,
    )

    season = repository.get_season("2026-27")

    assert season is not None
    assert season["id"] == season_id
    assert season["season_code"] == "2026-27"
    assert season["start_date"] == "2026-08-01"
    assert season["status"] == "ACTIVE"
    assert season["is_current"] == 1
    assert season["created_at"] is not None
    assert season["updated_at"] is not None


# ----------------------------------------------------------------------
# Gameweek tests
# ----------------------------------------------------------------------


def test_create_gameweek_requires_valid_season(
    repository: SQLiteRepository,
):
    """A gameweek cannot reference a season that does not exist."""

    with pytest.raises(RepositoryError):
        repository.create_gameweek(
            season_id=999999,
            gameweek=1,
            name="Gameweek 1",
        )


def test_create_gameweek_and_get_it(
    repository: SQLiteRepository,
):
    """
    A gameweek can be created and retrieved.

    Gameweeks intentionally do not expose created_at/updated_at.
    """

    season_id = repository.create_season(
        season_code="2026-27",
    )

    gameweek_id = repository.create_gameweek(
        season_id=season_id,
        gameweek=1,
        name="Gameweek 1",
        deadline_time="2026-08-14T17:30:00Z",
        finished=True,
        data_checked=True,
        is_current=False,
        is_next=True,
        is_previous=False,
    )

    gameweek = repository.get_gameweek(
        season_id=season_id,
        gameweek=1,
    )

    assert gameweek is not None
    assert gameweek["id"] == gameweek_id
    assert gameweek["gameweek"] == 1
    assert gameweek["season_id"] == season_id
    assert gameweek["name"] == "Gameweek 1"
    assert gameweek["deadline_time"] == "2026-08-14T17:30:00Z"
    assert gameweek["finished"] == 1
    assert gameweek["data_checked"] == 1
    assert gameweek["is_current"] == 0
    assert gameweek["is_next"] == 1
    assert gameweek["is_previous"] == 0


def test_gameweek_does_not_have_crud_timestamps(
    repository: SQLiteRepository,
):
    """The canonical gameweek entity has no CRUD lifecycle timestamps."""

    season_id = repository.create_season(
        season_code="2026-27",
    )

    repository.create_gameweek(
        season_id=season_id,
        gameweek=1,
        name="Gameweek 1",
    )

    gameweek = repository.get_gameweek(
        season_id=season_id,
        gameweek=1,
    )

    assert gameweek is not None
    assert "created_at" not in gameweek.keys()
    assert "updated_at" not in gameweek.keys()


def test_duplicate_gameweek_within_season_is_rejected(
    repository: SQLiteRepository,
):
    """Duplicate gameweeks within one season are rejected."""

    season_id = repository.create_season(
        season_code="2026-27",
    )

    repository.create_gameweek(
        season_id=season_id,
        gameweek=1,
        name="Gameweek 1",
    )

    with pytest.raises(RepositoryError):
        repository.create_gameweek(
            season_id=season_id,
            gameweek=1,
            name="Duplicate Gameweek 1",
        )


# ----------------------------------------------------------------------
# Ingestion run tests
# ----------------------------------------------------------------------


def test_create_and_complete_ingestion_run(
    repository: SQLiteRepository,
):
    """An ingestion run can be created and completed."""

    ingestion_run_id = repository.create_ingestion_run(
        source_system="fpl_api",
        source_type="api",
        endpoint_or_file="bootstrap-static/",
        started_at="2026-10-01T10:00:00+00:00",
        source_retrieved_at="2026-10-01T10:00:01+00:00",
    )

    ingestion_run = repository.get_ingestion_run(
        ingestion_run_id,
    )

    assert ingestion_run is not None
    assert ingestion_run["source_system"] == "fpl_api"
    assert ingestion_run["source_type"] == "api"
    assert ingestion_run["endpoint_or_file"] == "bootstrap-static/"
    assert ingestion_run["status"] == "RUNNING"
    assert ingestion_run["source_retrieved_at"] == (
        "2026-10-01T10:00:01+00:00"
    )
    assert ingestion_run["created_at"] is not None

    affected_rows = repository.complete_ingestion_run(
        ingestion_run_id=ingestion_run_id,
        status="SUCCESS",
        completed_at="2026-10-01T10:00:02+00:00",
        records_received=100,
        records_written=98,
        records_rejected=2,
        validation_status="PASSED",
    )

    assert affected_rows == 1

    completed = repository.get_ingestion_run(
        ingestion_run_id,
    )

    assert completed is not None
    assert completed["status"] == "SUCCESS"
    assert completed["completed_at"] == (
        "2026-10-01T10:00:02+00:00"
    )
    assert completed["records_received"] == 100
    assert completed["records_written"] == 98
    assert completed["records_rejected"] == 2
    assert completed["validation_status"] == "PASSED"


def test_complete_missing_ingestion_run_affects_no_rows(
    repository: SQLiteRepository,
):
    """Completing a nonexistent ingestion run changes nothing."""

    affected_rows = repository.complete_ingestion_run(
        ingestion_run_id=999999,
        status="FAILED",
    )

    assert affected_rows == 0


# ----------------------------------------------------------------------
# Team tests
# ----------------------------------------------------------------------


def test_create_and_get_team(
    repository: SQLiteRepository,
):
    """A team can be created and retrieved by FPL team ID."""

    team_id = repository.create_team(
        fpl_team_id=1,
        name="Arsenal",
        short_name="ARS",
        code=3,
    )

    team = repository.get_team(1)

    assert team is not None
    assert team["id"] == team_id
    assert team["fpl_team_id"] == 1
    assert team["name"] == "Arsenal"
    assert team["short_name"] == "ARS"
    assert team["code"] == 3
    assert team["created_at"] is not None
    assert team["updated_at"] is not None


def test_upsert_team_preserves_stable_identity(
    repository: SQLiteRepository,
):
    """Team upsert updates details without changing internal identity."""

    first_id = repository.upsert_team(
        fpl_team_id=1,
        name="Arsenal",
        short_name="ARS",
        code=3,
    )

    second_id = repository.upsert_team(
        fpl_team_id=1,
        name="Arsenal FC",
        short_name="ARS",
        code=3,
    )

    assert second_id == first_id

    team = repository.get_team(1)

    assert team is not None
    assert team["id"] == first_id
    assert team["name"] == "Arsenal FC"


def test_create_and_get_latest_team_snapshot(
    repository: SQLiteRepository,
):
    """The latest team snapshot can be retrieved by season and team."""

    season_id = repository.create_season(
        season_code="2026-27",
    )

    team_id = repository.upsert_team(
        fpl_team_id=1,
        name="Arsenal",
        short_name="ARS",
        code=3,
    )

    first_snapshot_id = repository.create_team_snapshot(
        season_id=season_id,
        team_id=team_id,
        snapshot_at="2026-08-01T10:00:00+00:00",
        snapshot={
            "strength": 4,
            "strength_overall_home": 5,
            "strength_overall_away": 4,
            "strength_attack_home": 5,
            "strength_attack_away": 4,
            "strength_defence_home": 5,
            "strength_defence_away": 4,
        },
    )

    second_snapshot_id = repository.create_team_snapshot(
        season_id=season_id,
        team_id=team_id,
        snapshot_at="2026-08-10T10:00:00+00:00",
        snapshot={
            "strength": 5,
            "strength_overall_home": 5,
            "strength_overall_away": 5,
            "strength_attack_home": 5,
            "strength_attack_away": 5,
            "strength_defence_home": 5,
            "strength_defence_away": 5,
        },
    )

    assert first_snapshot_id != second_snapshot_id

    latest = repository.get_latest_team_snapshot(
        team_id=team_id,
        season_id=season_id,
    )

    assert latest is not None
    assert latest["id"] == second_snapshot_id
    assert latest["strength"] == 5


# ----------------------------------------------------------------------
# Player tests
# ----------------------------------------------------------------------


def test_create_and_get_player(
    repository: SQLiteRepository,
):
    """A player can be created and retrieved by FPL player ID."""

    player_id = repository.create_player(
        fpl_player_id=123,
        first_name="Test",
        second_name="Player",
        web_name="Player",
    )

    player = repository.get_player(123)

    assert player is not None
    assert player["id"] == player_id
    assert player["fpl_player_id"] == 123
    assert player["first_name"] == "Test"
    assert player["second_name"] == "Player"
    assert player["web_name"] == "Player"
    assert player["created_at"] is not None
    assert player["updated_at"] is not None


def test_upsert_player_preserves_stable_identity(
    repository: SQLiteRepository,
):
    """Player upsert updates identity fields without changing internal ID."""

    first_id = repository.upsert_player(
        fpl_player_id=123,
        first_name="Test",
        second_name="Player",
        web_name="Player",
    )

    second_id = repository.upsert_player(
        fpl_player_id=123,
        first_name="Updated",
        second_name="Player",
        web_name="Updated Player",
    )

    assert second_id == first_id

    player = repository.get_player(123)

    assert player is not None
    assert player["id"] == first_id
    assert player["first_name"] == "Updated"
    assert player["web_name"] == "Updated Player"


def test_create_and_get_latest_player_snapshot(
    repository: SQLiteRepository,
):
    """The latest player snapshot can be retrieved for a season."""

    season_id = repository.create_season(
        season_code="2026-27",
    )

    team_id = repository.upsert_team(
        fpl_team_id=1,
        name="Arsenal",
        short_name="ARS",
        code=3,
    )

    player_id = repository.upsert_player(
        fpl_player_id=123,
        first_name="Test",
        second_name="Player",
        web_name="Player",
    )

    first_snapshot_id = repository.create_player_snapshot(
        season_id=season_id,
        player_id=player_id,
        snapshot_at="2026-08-01T10:00:00+00:00",
        snapshot={
            "team_id": team_id,
            "position_id": 3,
            "position": "Midfielder",
            "price": 70,
            "form": 5.5,
            "total_points": 20,
            "event_points": 6,
            "minutes": 180,
            "starts": 2,
            "goals_scored": 1,
            "assists": 2,
            "clean_sheets": 1,
            "expected_goals": 0.8,
            "expected_assists": 0.7,
            "expected_goal_involvements": 1.5,
            "expected_goals_conceded": 1.2,
            "bonus": 3,
            "bps": 50,
            "defensive_contribution": 4,
            "status": "a",
            "can_select": 1,
            "can_transact": 1,
        },
    )

    second_snapshot_id = repository.create_player_snapshot(
        season_id=season_id,
        player_id=player_id,
        snapshot_at="2026-08-10T10:00:00+00:00",
        snapshot={
            "team_id": team_id,
            "position_id": 3,
            "position": "Midfielder",
            "price": 71,
            "form": 6.5,
            "total_points": 30,
        },
    )

    assert first_snapshot_id != second_snapshot_id

    latest = repository.get_latest_player_snapshot(
        player_id=player_id,
        season_id=season_id,
    )

    assert latest is not None
    assert latest["id"] == second_snapshot_id
    assert latest["price"] == 71
    assert latest["total_points"] == 30


# ----------------------------------------------------------------------
# Fixture tests
# ----------------------------------------------------------------------


def test_upsert_and_get_fixture(
    repository: SQLiteRepository,
):
    """A fixture can be inserted and updated by official FPL fixture ID."""

    season_id = repository.create_season(
        season_code="2026-27",
    )

    gameweek_id = repository.create_gameweek(
        season_id=season_id,
        gameweek=1,
        name="Gameweek 1",
    )

    home_team_id = repository.upsert_team(
        fpl_team_id=1,
        name="Arsenal",
        short_name="ARS",
        code=3,
    )

    away_team_id = repository.upsert_team(
        fpl_team_id=2,
        name="Aston Villa",
        short_name="AVL",
        code=7,
    )

    fixture_id = repository.upsert_fixture(
        season_id=season_id,
        fpl_fixture_id=1001,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        gameweek_id=gameweek_id,
        kickoff_time="2026-08-15T14:00:00Z",
        started=False,
        finished=False,
        home_difficulty=2,
        away_difficulty=4,
    )

    fixture = repository.get_fixture(1001)

    assert fixture is not None
    assert fixture["id"] == fixture_id
    assert fixture["fpl_fixture_id"] == 1001
    assert fixture["home_team_id"] == home_team_id
    assert fixture["away_team_id"] == away_team_id
    assert fixture["gameweek_id"] == gameweek_id

    updated_id = repository.upsert_fixture(
        season_id=season_id,
        fpl_fixture_id=1001,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        gameweek_id=gameweek_id,
        kickoff_time="2026-08-15T14:00:00Z",
        started=True,
        finished=True,
        home_score=2,
        away_score=1,
        home_difficulty=2,
        away_difficulty=4,
    )

    assert updated_id == fixture_id

    updated = repository.get_fixture(1001)

    assert updated is not None
    assert updated["started"] == 1
    assert updated["finished"] == 1
    assert updated["home_score"] == 2
    assert updated["away_score"] == 1


def test_get_fixtures_for_gameweek(
    repository: SQLiteRepository,
):
    """Fixtures can be retrieved as a gameweek collection."""

    season_id = repository.create_season(
        season_code="2026-27",
    )

    gameweek_id = repository.create_gameweek(
        season_id=season_id,
        gameweek=1,
        name="Gameweek 1",
    )

    arsenal_id = repository.upsert_team(
        fpl_team_id=1,
        name="Arsenal",
        short_name="ARS",
        code=3,
    )

    villa_id = repository.upsert_team(
        fpl_team_id=2,
        name="Aston Villa",
        short_name="AVL",
        code=7,
    )

    chelsea_id = repository.upsert_team(
        fpl_team_id=3,
        name="Chelsea",
        short_name="CHE",
        code=8,
    )

    repository.upsert_fixture(
        season_id=season_id,
        fpl_fixture_id=1001,
        home_team_id=arsenal_id,
        away_team_id=villa_id,
        gameweek_id=gameweek_id,
        kickoff_time="2026-08-15T14:00:00Z",
    )

    repository.upsert_fixture(
        season_id=season_id,
        fpl_fixture_id=1002,
        home_team_id=chelsea_id,
        away_team_id=arsenal_id,
        gameweek_id=gameweek_id,
        kickoff_time="2026-08-15T16:30:00Z",
    )

    fixtures = repository.get_fixtures_for_gameweek(
        season_id=season_id,
        gameweek_id=gameweek_id,
    )

    assert len(fixtures) == 2
    assert fixtures[0]["fpl_fixture_id"] == 1001
    assert fixtures[1]["fpl_fixture_id"] == 1002


# ----------------------------------------------------------------------
# Current player-gameweek statistics tests
# ----------------------------------------------------------------------


def test_upsert_and_get_current_player_gameweek_stats(
    repository: SQLiteRepository,
):
    """Current player-fixture statistics can be inserted and updated."""

    season_id = repository.create_season(
        season_code="2026-27",
    )

    gameweek_id = repository.create_gameweek(
        season_id=season_id,
        gameweek=1,
        name="Gameweek 1",
    )

    home_team_id = repository.upsert_team(
        fpl_team_id=1,
        name="Arsenal",
        short_name="ARS",
        code=3,
    )

    away_team_id = repository.upsert_team(
        fpl_team_id=2,
        name="Aston Villa",
        short_name="AVL",
        code=7,
    )

    player_id = repository.upsert_player(
        fpl_player_id=123,
        first_name="Test",
        second_name="Player",
        web_name="Player",
    )

    fixture_id = repository.upsert_fixture(
        season_id=season_id,
        fpl_fixture_id=1001,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        gameweek_id=gameweek_id,
        kickoff_time="2026-08-15T14:00:00Z",
    )

    stats_id = repository.upsert_current_player_gameweek_stats(
        season_id=season_id,
        player_id=player_id,
        fixture_id=fixture_id,
        gameweek_id=gameweek_id,
        stats={
            "opponent_team_id": away_team_id,
            "was_home": 1,
            "kickoff_time": "2026-08-15T14:00:00Z",
            "minutes": 90,
            "starts": 1,
            "total_points": 10,
            "goals_scored": 1,
            "assists": 1,
            "clean_sheets": 1,
            "goals_conceded": 0,
            "bonus": 3,
            "bps": 40,
            "expected_goals": 0.8,
            "expected_assists": 0.4,
            "value": 70,
            "selected": 100000,
        },
    )

    stats = repository.get_current_player_gameweek_stats(
        season_id=season_id,
        player_id=player_id,
        fixture_id=fixture_id,
    )

    assert stats is not None
    assert stats["id"] == stats_id
    assert stats["gameweek_id"] == gameweek_id
    assert stats["minutes"] == 90
    assert stats["total_points"] == 10
    assert stats["goals_scored"] == 1

    updated_id = repository.upsert_current_player_gameweek_stats(
        season_id=season_id,
        player_id=player_id,
        fixture_id=fixture_id,
        gameweek_id=gameweek_id,
        stats={
            "opponent_team_id": away_team_id,
            "was_home": 1,
            "kickoff_time": "2026-08-15T14:00:00Z",
            "minutes": 90,
            "starts": 1,
            "total_points": 12,
            "goals_scored": 1,
            "assists": 2,
            "clean_sheets": 1,
            "goals_conceded": 0,
            "bonus": 3,
            "bps": 45,
            "expected_goals": 0.9,
            "expected_assists": 0.5,
            "value": 70,
            "selected": 110000,
        },
    )

    assert updated_id == stats_id

    updated = repository.get_current_player_gameweek_stats(
        season_id=season_id,
        player_id=player_id,
        fixture_id=fixture_id,
    )

    assert updated is not None
    assert updated["total_points"] == 12
    assert updated["assists"] == 2
    assert updated["bps"] == 45


# ----------------------------------------------------------------------
# Foreign-key and uniqueness tests
# ----------------------------------------------------------------------


def test_team_snapshot_requires_valid_team(
    repository: SQLiteRepository,
):
    """A team snapshot cannot reference a nonexistent team."""

    season_id = repository.create_season(
        season_code="2026-27",
    )

    with pytest.raises(RepositoryError):
        repository.create_team_snapshot(
            season_id=season_id,
            team_id=999999,
            snapshot_at="2026-08-01T10:00:00+00:00",
            snapshot={"strength": 5},
        )


def test_player_snapshot_requires_valid_player(
    repository: SQLiteRepository,
):
    """A player snapshot cannot reference a nonexistent player."""

    season_id = repository.create_season(
        season_code="2026-27",
    )

    with pytest.raises(RepositoryError):
        repository.create_player_snapshot(
            season_id=season_id,
            player_id=999999,
            snapshot_at="2026-08-01T10:00:00+00:00",
            snapshot={"price": 70},
        )


def test_duplicate_player_snapshot_at_same_time_is_rejected(
    repository: SQLiteRepository,
):
    """The player snapshot uniqueness constraint is enforced."""

    season_id = repository.create_season(
        season_code="2026-27",
    )

    player_id = repository.upsert_player(
        fpl_player_id=123,
        first_name="Test",
        second_name="Player",
        web_name="Player",
    )

    snapshot_at = "2026-08-01T10:00:00+00:00"

    repository.create_player_snapshot(
        season_id=season_id,
        player_id=player_id,
        snapshot_at=snapshot_at,
        snapshot={"price": 70},
    )

    with pytest.raises(RepositoryError):
        repository.create_player_snapshot(
            season_id=season_id,
            player_id=player_id,
            snapshot_at=snapshot_at,
            snapshot={"price": 71},
        )


def test_current_player_gameweek_stats_require_valid_fixture(
    repository: SQLiteRepository,
):
    """Current player-GW stats cannot reference a nonexistent fixture."""

    season_id = repository.create_season(
        season_code="2026-27",
    )

    player_id = repository.upsert_player(
        fpl_player_id=123,
        first_name="Test",
        second_name="Player",
        web_name="Player",
    )

    with pytest.raises(RepositoryError):
        repository.upsert_current_player_gameweek_stats(
            season_id=season_id,
            player_id=player_id,
            fixture_id=999999,
            stats={
                "minutes": 90,
                "total_points": 10,
            },
        )


# ----------------------------------------------------------------------
# Transaction tests
# ----------------------------------------------------------------------


def test_transaction_rolls_back_on_error(
    repository: SQLiteRepository,
):
    """A failed transaction rolls back all writes made inside it."""

    with pytest.raises(RuntimeError):
        with repository.transaction():
            repository.create_season(
                season_code="2026-27-test",
            )

            repository.upsert_team(
                fpl_team_id=1,
                name="Arsenal",
                short_name="ARS",
                code=3,
            )

            raise RuntimeError("intentional test failure")

    assert repository.get_season("2026-27-test") is None
    assert repository.get_team(1) is None


def test_transaction_commits_successfully(
    repository: SQLiteRepository,
):
    """A successful transaction commits all writes made inside it."""

    with repository.transaction():
        season_id = repository.create_season(
            season_code="2026-27-transaction",
        )

        team_id = repository.upsert_team(
            fpl_team_id=1,
            name="Arsenal",
            short_name="ARS",
            code=3,
        )

        repository.create_team_snapshot(
            season_id=season_id,
            team_id=team_id,
            snapshot_at="2026-08-01T10:00:00+00:00",
            snapshot={"strength": 5},
        )

    assert repository.get_season(
        "2026-27-transaction",
    ) is not None

    assert repository.get_team(1) is not None


def test_repository_create_methods_work_inside_transaction(
    repository: SQLiteRepository,
):
    """
    Domain-style repository methods participate in the surrounding
    transaction rather than committing independently.
    """

    with repository.transaction():
        season_id = repository.create_season(
            season_code="2026-27-domain-transaction",
        )

        gameweek_id = repository.create_gameweek(
            season_id=season_id,
            gameweek=1,
            name="Gameweek 1",
            deadline_time="2026-08-14T17:30:00Z",
        )

        team_id = repository.upsert_team(
            fpl_team_id=1,
            name="Arsenal",
            short_name="ARS",
            code=3,
        )

        fixture_id = repository.upsert_fixture(
            season_id=season_id,
            fpl_fixture_id=1001,
            home_team_id=team_id,
            away_team_id=team_id,
            gameweek_id=gameweek_id,
        )

    assert repository.get_gameweek(
        season_id=season_id,
        gameweek=1,
    ) is not None

    assert repository.get_fixture(1001) is not None
    assert fixture_id > 0


def test_nested_transaction_is_rejected(
    repository: SQLiteRepository,
):
    """Nested repository transactions are intentionally unsupported."""

    with pytest.raises(RepositoryError):
        with repository.transaction():
            with repository.transaction():
                pass


# ----------------------------------------------------------------------
# Constraint/error tests
# ----------------------------------------------------------------------


def test_duplicate_fpl_team_id_is_rejected(
    repository: SQLiteRepository,
):
    """The database UNIQUE constraint protects FPL team identity."""

    repository.create_team(
        fpl_team_id=1,
        name="Arsenal",
        short_name="ARS",
        code=3,
    )

    with pytest.raises(RepositoryError):
        repository.create_team(
            fpl_team_id=1,
            name="Duplicate Arsenal",
            short_name="ARS",
            code=3,
        )


def test_duplicate_fpl_player_id_is_rejected(
    repository: SQLiteRepository,
):
    """The database UNIQUE constraint protects FPL player identity."""

    repository.create_player(
        fpl_player_id=123,
        first_name="Test",
        second_name="Player",
        web_name="Player",
    )

    with pytest.raises(RepositoryError):
        repository.create_player(
            fpl_player_id=123,
            first_name="Duplicate",
            second_name="Player",
            web_name="Player",
        )
# ----------------------------------------------------------------------
# Batch 5 manager/user persistence tests
# ----------------------------------------------------------------------


def test_upsert_user_and_manager(repository: SQLiteRepository):
    """Users and managers should be stable upserts."""

    user_id = repository.upsert_user("3325156", "Test Manager")
    same_user_id = repository.upsert_user("3325156", "Updated Manager")

    assert same_user_id == user_id

    manager_id = repository.upsert_manager(
        user_id=user_id,
        fpl_manager_id=3325156,
        manager_name="Test Manager",
        team_name="Test Team",
    )
    same_manager_id = repository.upsert_manager(
        user_id=user_id,
        fpl_manager_id=3325156,
        manager_name="Updated Manager",
        team_name="Updated Team",
    )

    assert same_manager_id == manager_id

    manager = repository.fetch_one(
        "SELECT * FROM managers WHERE id = ?",
        (manager_id,),
    )
    assert manager["manager_name"] == "Updated Manager"
    assert manager["team_name"] == "Updated Team"


def test_manager_gameweek_state_upsert(repository: SQLiteRepository):
    """Manager Gameweek state should update rather than duplicate."""

    season_id = repository.create_season("2026/27")
    gameweek_id = repository.create_gameweek(season_id, 2, "Gameweek 2")
    user_id = repository.upsert_user("3325156", "Test Manager")
    manager_id = repository.upsert_manager(user_id, 3325156)

    state_id = repository.upsert_manager_gameweek_state(
        manager_id=manager_id,
        season_id=season_id,
        gameweek_id=gameweek_id,
        points=41,
        total_points=317,
        overall_rank=100,
        rank=500,
        bank=1.0,
        team_value=100.5,
    )
    same_id = repository.upsert_manager_gameweek_state(
        manager_id=manager_id,
        season_id=season_id,
        gameweek_id=gameweek_id,
        points=55,
        total_points=331,
        overall_rank=90,
        rank=400,
        bank=2.0,
        team_value=100.6,
    )

    assert same_id == state_id
    row = repository.fetch_one(
        "SELECT * FROM manager_gameweek_state WHERE id = ?",
        (state_id,),
    )
    assert row["points"] == 55
    assert row["total_points"] == 331
    assert row["bank"] == 2.0


def test_manager_pick_and_chip_persistence(repository: SQLiteRepository):
    """Manager picks and chips should persist with their FKs."""

    season_id = repository.create_season("2026/27")
    gameweek_id = repository.create_gameweek(season_id, 2, "Gameweek 2")
    user_id = repository.upsert_user("3325156")
    manager_id = repository.upsert_manager(user_id, 3325156)
    player_id = repository.upsert_player(1, "Player", "A", "PlayerA")

    pick_id = repository.upsert_manager_pick(
        manager_id=manager_id,
        season_id=season_id,
        gameweek_id=gameweek_id,
        player_id=player_id,
        position=1,
        multiplier=2,
        is_captain=True,
        purchase_price=7.0,
    )
    same_pick_id = repository.upsert_manager_pick(
        manager_id=manager_id,
        season_id=season_id,
        gameweek_id=gameweek_id,
        player_id=player_id,
        position=1,
        multiplier=1,
        is_captain=False,
        purchase_price=7.1,
    )

    chip_id = repository.upsert_manager_chip(
        manager_id=manager_id,
        season_id=season_id,
        chip_type="wildcard",
        gameweek_id=gameweek_id,
    )

    assert same_pick_id == pick_id
    assert chip_id > 0

    pick = repository.fetch_one(
        "SELECT * FROM manager_picks WHERE id = ?",
        (pick_id,),
    )
    assert pick["multiplier"] == 1
    assert pick["is_captain"] == 0

    chip = repository.fetch_one(
        "SELECT * FROM manager_chips WHERE id = ?",
        (chip_id,),
    )
    assert chip["chip_type"] == "wildcard"


def test_manager_transfer_persistence(repository: SQLiteRepository):
    """Manager transfers should persist as immutable event records."""

    season_id = repository.create_season("2026/27")
    gameweek_id = repository.create_gameweek(season_id, 2, "Gameweek 2")
    user_id = repository.upsert_user("3325156")
    manager_id = repository.upsert_manager(user_id, 3325156)
    player_in = repository.upsert_player(1)
    player_out = repository.upsert_player(2)

    transfer_id = repository.create_manager_transfer(
        manager_id=manager_id,
        season_id=season_id,
        gameweek_id=gameweek_id,
        transfer_timestamp="2026-08-28T10:00:00Z",
        player_in_id=player_in,
        player_out_id=player_out,
        cost=4,
        external_transfer_id="transfer-1",
    )

    transfer = repository.fetch_one(
        "SELECT * FROM manager_transfers WHERE id = ?",
        (transfer_id,),
    )
    assert transfer["player_in_id"] == player_in
    assert transfer["player_out_id"] == player_out
    assert transfer["cost"] == 4

# ----------------------------------------------------------------------
# Batch 7 dataset freshness tests
# ----------------------------------------------------------------------


def test_dataset_freshness_can_be_created_and_retrieved(
    repository: SQLiteRepository,
):
    """Dataset freshness metadata can be persisted and retrieved."""

    ingestion_id = repository.create_ingestion_run(
        source_system="fpl_api",
        source_type="API",
        endpoint_or_file="bootstrap-static/",
        started_at="2026-10-02T10:00:00+00:00",
        source_retrieved_at="2026-10-02T10:00:00+00:00",
        status="SUCCESS",
    )

    freshness_id = repository.upsert_dataset_freshness(
        dataset_name="bootstrap_static",
        last_successful_ingestion_id=ingestion_id,
        last_attempted_ingestion_id=ingestion_id,
        last_successful_refresh_at="2026-10-02T10:00:00+00:00",
        last_attempted_refresh_at="2026-10-02T10:00:00+00:00",
        freshness_threshold_seconds=21600,
        freshness_status="FRESH",
    )

    row = repository.get_dataset_freshness("bootstrap_static")

    assert row is not None
    assert row["id"] == freshness_id
    assert row["last_successful_ingestion_id"] == ingestion_id
    assert row["last_attempted_ingestion_id"] == ingestion_id
    assert row["freshness_threshold_seconds"] == 21600
    assert row["freshness_status"] == "FRESH"


def test_dataset_freshness_update_preserves_previous_success(
    repository: SQLiteRepository,
):
    """A failed/new attempt must not erase the last successful refresh."""

    first_ingestion_id = repository.create_ingestion_run(
        source_system="fpl_api",
        source_type="API",
        endpoint_or_file="fixtures/",
        started_at="2026-10-02T10:00:00+00:00",
        source_retrieved_at="2026-10-02T10:00:00+00:00",
        status="SUCCESS",
    )
    second_ingestion_id = repository.create_ingestion_run(
        source_system="fpl_api",
        source_type="API",
        endpoint_or_file="fixtures/",
        started_at="2026-10-02T11:00:00+00:00",
        source_retrieved_at="2026-10-02T11:00:00+00:00",
        status="FAILED",
    )

    repository.upsert_dataset_freshness(
        dataset_name="fixtures",
        last_successful_ingestion_id=first_ingestion_id,
        last_attempted_ingestion_id=first_ingestion_id,
        last_successful_refresh_at="2026-10-02T10:00:00+00:00",
        last_attempted_refresh_at="2026-10-02T10:00:00+00:00",
        freshness_threshold_seconds=21600,
        freshness_status="FRESH",
    )

    repository.upsert_dataset_freshness(
        dataset_name="fixtures",
        last_attempted_ingestion_id=second_ingestion_id,
        last_attempted_refresh_at="2026-10-02T11:00:00+00:00",
        freshness_status="STALE",
    )

    row = repository.get_dataset_freshness("fixtures")

    assert row is not None
    assert row["last_successful_ingestion_id"] == first_ingestion_id
    assert row["last_successful_refresh_at"] == "2026-10-02T10:00:00+00:00"
    assert row["last_attempted_ingestion_id"] == second_ingestion_id
    assert row["last_attempted_refresh_at"] == "2026-10-02T11:00:00+00:00"
    assert row["freshness_status"] == "STALE"
