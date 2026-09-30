"""
Tests for the SQLite repository foundation.

These tests verify that repository behaviour matches the approved
SQLite schema and repository contract.

The tests deliberately keep gameweek semantics separate from CRUD
lifecycle timestamps. Gameweeks are canonical football/FPL event
references and do not have created_at/updated_at columns.
"""

from pathlib import Path

import pytest

from repository import RepositoryError
from sqlite_db import initialize_database
from sqlite_repository import SQLiteRepository


@pytest.fixture
def repository(tmp_path: Path) -> SQLiteRepository:
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

    # Seasons are lifecycle-managed entities, so their timestamps
    # belong in the repository contract.
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
    """
    The gameweek schema intentionally has no created_at/updated_at.

    Temporal information for football events is represented through
    event/deadline fields and the broader ingestion/snapshot model.
    """

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

    # These columns should not exist in the canonical gameweek entity.
    assert "created_at" not in gameweek.keys()
    assert "updated_at" not in gameweek.keys()


def test_duplicate_gameweek_within_season_is_rejected(
    repository: SQLiteRepository,
):
    """
    The database UNIQUE constraint prevents duplicate gameweeks within
    the same season.
    """

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

    # Teams are lifecycle-managed entities.
    assert team["created_at"] is not None
    assert team["updated_at"] is not None


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

    # Players are lifecycle-managed entities.
    assert player["created_at"] is not None
    assert player["updated_at"] is not None


# ----------------------------------------------------------------------
# Transaction tests
# ----------------------------------------------------------------------


def test_transaction_rolls_back_on_error(
    repository: SQLiteRepository,
):
    """
    A failed transaction rolls back all writes made inside it.
    """

    with pytest.raises(RuntimeError):
        with repository.transaction():
            repository.create_season(
                season_code="2026-27-test",
            )

            raise RuntimeError("intentional test failure")

    season = repository.get_season("2026-27-test")

    assert season is None


def test_transaction_commits_successfully(
    repository: SQLiteRepository,
):
    """
    A successful transaction commits all writes made inside it.
    """

    with repository.transaction():
        repository.create_season(
            season_code="2026-27-transaction",
        )

    season = repository.get_season(
        "2026-27-transaction",
    )

    assert season is not None
    assert season["season_code"] == "2026-27-transaction"


def test_repository_create_methods_work_inside_transaction(
    repository: SQLiteRepository,
):
    """
    Domain-style repository methods must participate in the surrounding
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

    season = repository.get_season(
        "2026-27-domain-transaction",
    )

    gameweek = repository.get_gameweek(
        season_id=season_id,
        gameweek=1,
    )

    assert season is not None
    assert gameweek is not None
    assert gameweek["id"] == gameweek_id


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