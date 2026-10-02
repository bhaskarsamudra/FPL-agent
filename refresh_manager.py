"""
Refresh orchestration for the FPL Strategist.

Layering:

    FPL API
        ↓
    FPLDataSource
        ↓
    FPLRefreshManager
        ↓
    Repository
        ↓
    SQLiteRepository

The refresh manager is responsible for:
- retrieving official FPL data
- normalising it into project-domain records
- sending those records to the repository

The repository remains responsible for persistence.

The old JsonDataStore path is retained temporarily so existing
Layer 2 tests and legacy callers continue to work while SQLite
becomes the new canonical persistence path.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from data_store import JsonDataStore
from fpl_data_source import FPLDataSource
from repository import Repository


# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------

# The current project season.

# IMPORTANT:
# The FPL bootstrap endpoint does not provide a simple "season_code"
# field that we can directly persist as "2026/27".
#
# Therefore the current season is supplied explicitly here for now.
# Later this should move to application configuration rather than
# being hard-coded in this module.
DEFAULT_SEASON_CODE = "2026/27"


# ----------------------------------------------------------------------
# Refresh result
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class RefreshReport:
    """Summary of one refresh operation."""

    source: str
    started_at: str
    completed_at: str
    status: str
    collections: dict[str, dict[str, int]]
    error: str | None = None


# ----------------------------------------------------------------------
# General helpers
# ----------------------------------------------------------------------


def _timestamp() -> str:
    """Return an auditable UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


def _value(
    record: dict[str, Any],
    key: str,
    default: Any = None,
) -> Any:
    """
    Safely retrieve a value from an FPL record.

    Keeping this helper here makes the normalisation code easier to read.
    """

    return record.get(key, default)


def _as_float(value: Any) -> float | None:
    """
    Convert an FPL numeric value to float.

    FPL sometimes returns numeric-looking values as strings.

    Empty values become None rather than being converted to zero.
    """

    if value is None or value == "":
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    """Convert a value to int when possible."""

    if value is None or value == "":
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ----------------------------------------------------------------------
# Legacy JSON normalisation
# ----------------------------------------------------------------------


def _normalise_bootstrap_players(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Convert bootstrap player records into stable JSON store records.

    This is retained only for backward compatibility with the existing
    JSON persistence path.
    """

    return [
        {
            "record_id": str(player["id"]),
            "payload": player,
        }
        for player in payload.get("elements", [])
        if "id" in player
    ]


def _normalise_fixtures(
    fixtures: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Convert fixture records into stable JSON store records.

    This is retained only for backward compatibility with the existing
    JSON persistence path.
    """

    return [
        {
            "record_id": str(fixture["id"]),
            "payload": fixture,
        }
        for fixture in fixtures
        if "id" in fixture
    ]


# ----------------------------------------------------------------------
# SQLite/domain normalisation
# ----------------------------------------------------------------------


def _build_team_record(
    team: dict[str, Any],
) -> dict[str, Any]:
    """Build the canonical team record used by the repository."""

    return {
        "fpl_team_id": team["id"],
        "name": team["name"],
        "short_name": team.get("short_name"),
        "code": team.get("code"),
    }


def _build_team_snapshot(
    team: dict[str, Any],
    season_id: int,
    snapshot_at: str,
    ingestion_run_id: int,
    team_id: int,
) -> dict[str, Any]:
    """Build one canonical team snapshot."""

    return {
        "season_id": season_id,
        "team_id": team_id,
        "snapshot_at": snapshot_at,
        "ingestion_run_id": ingestion_run_id,
        "strength": team.get("strength"),
        "strength_overall_home": team.get("strength_overall_home"),
        "strength_overall_away": team.get("strength_overall_away"),
        "strength_attack_home": team.get("strength_attack_home"),
        "strength_attack_away": team.get("strength_attack_away"),
        "strength_defence_home": team.get("strength_defence_home"),
        "strength_defence_away": team.get("strength_defence_away"),
    }


def _build_player_record(
    player: dict[str, Any],
) -> dict[str, Any]:
    """Build the canonical player master record."""

    return {
        "fpl_player_id": player["id"],
        "first_name": player.get("first_name", ""),
        "second_name": player.get("second_name", ""),
        "web_name": player.get("web_name"),
    }


def _build_player_snapshot(
    player: dict[str, Any],
    season_id: int,
    snapshot_at: str,
    ingestion_run_id: int,
    team_id: int,
    position_name: str | None,
) -> dict[str, Any]:
    """
    Build the canonical current-season player snapshot.

    The snapshot stores the fields approved in the SQLite schema.
    """

    return {
        "season_id": season_id,
        "player_id": None,
        "snapshot_at": snapshot_at,
        "ingestion_run_id": ingestion_run_id,
        "team_id": team_id,
        "position_id": player.get("element_type"),
        "position": position_name,
        "price": _as_float(player.get("now_cost")),
        "form": _as_float(player.get("form")),
        "total_points": player.get("total_points"),
        "event_points": player.get("event_points"),
        "points_per_game": _as_float(player.get("points_per_game")),
        "selected_by_percent": _as_float(
            player.get("selected_by_percent")
        ),
        "minutes": player.get("minutes"),
        "starts": player.get("starts"),
        "goals_scored": player.get("goals_scored"),
        "assists": player.get("assists"),
        "clean_sheets": player.get("clean_sheets"),
        "expected_goals": _as_float(player.get("expected_goals")),
        "expected_assists": _as_float(
            player.get("expected_assists")
        ),
        "expected_goal_involvements": _as_float(
            player.get("expected_goal_involvements")
        ),
        "expected_goals_conceded": _as_float(
            player.get("expected_goals_conceded")
        ),
        "bonus": player.get("bonus"),
        "bps": player.get("bps"),
        "defensive_contribution": player.get(
            "defensive_contribution"
        ),
        "influence": _as_float(player.get("influence")),
        "creativity": _as_float(player.get("creativity")),
        "threat": _as_float(player.get("threat")),
        "ict_index": _as_float(player.get("ict_index")),
        "status": player.get("status"),
        "chance_of_playing_this_round": player.get(
            "chance_of_playing_this_round"
        ),
        "chance_of_playing_next_round": player.get(
            "chance_of_playing_next_round"
        ),
        "news": player.get("news"),
        "news_added": player.get("news_added"),
        "transfers_in": player.get("transfers_in"),
        "transfers_out": player.get("transfers_out"),
        "transfers_in_event": player.get("transfers_in_event"),
        "transfers_out_event": player.get("transfers_out_event"),
        "can_select": player.get("can_select"),
        "can_transact": player.get("can_transact"),
    }


def _fixture_stats_by_player(
    fixture: dict[str, Any],
) -> dict[int, dict[str, Any]]:
    """
    Convert FPL's fixture-level stats structure into:

        player_id -> statistic name -> value

    FPL provides statistics grouped by statistic name and then
    separates home and away players.

    Example:

        goals_scored:
            h: [{element: 10, value: 1}]
            a: [{element: 20, value: 0}]
    """

    stats_by_player: dict[int, dict[str, Any]] = {}

    for statistic in fixture.get("stats", []):
        identifier = statistic.get("identifier")

        if not identifier:
            continue

        for side in ("h", "a"):
            for player_stat in statistic.get(side, []):
                player_id = player_stat.get("element")

                if player_id is None:
                    continue

                stats_by_player.setdefault(
                    int(player_id),
                    {},
                )[identifier] = player_stat.get("value")

    return stats_by_player


def _build_player_gameweek_stat_records(
    fixture: dict[str, Any],
    season_id: int,
    gameweek_id: int,
    fixture_id: int,
    home_team_id: int,
    away_team_id: int,
    ingestion_run_id: int,
) -> list[dict[str, Any]]:
    """
    Build canonical current-player-gameweek records from one fixture.

    Important:
    Only players appearing in FPL's fixture stats are persisted here.

    Players with no recorded fixture statistics are not invented.
    This follows the project rule:

        NO DATA = NO ANSWER
    """

    stats_by_player = _fixture_stats_by_player(fixture)

    records: list[dict[str, Any]] = []

    for player_id, stats in stats_by_player.items():

        # Determine whether this player belongs to the home or away side.
        # FPL's fixture stats structure gives us that information.
        #
        # We infer the side by looking at the original fixture stats
        # membership rather than inventing team information.
        was_home: bool | None = None

        for statistic in fixture.get("stats", []):
            for player_stat in statistic.get("h", []):
                if player_stat.get("element") == player_id:
                    was_home = True
                    break

            if was_home is True:
                break

            for player_stat in statistic.get("a", []):
                if player_stat.get("element") == player_id:
                    was_home = False
                    break

            if was_home is not None:
                break

        if was_home is None:
            continue

        opponent_team_id = (
            away_team_id
            if was_home
            else home_team_id
        )

        records.append(
            {
                "season_id": season_id,
                "gameweek_id": gameweek_id,
                "player_id": player_id,
                "fixture_id": fixture_id,
                "opponent_team_id": opponent_team_id,
                "was_home": int(was_home),
                "kickoff_time": fixture.get("kickoff_time"),
                "minutes": stats.get("minutes", 0),
                "starts": stats.get("starts", 0),
                "total_points": stats.get("total_points", 0),
                "goals_scored": stats.get("goals_scored", 0),
                "assists": stats.get("assists", 0),
                "clean_sheets": stats.get("clean_sheets", 0),
                "goals_conceded": stats.get("goals_conceded", 0),
                "own_goals": stats.get("own_goals", 0),
                "penalties_saved": stats.get(
                    "penalties_saved",
                    0,
                ),
                "penalties_missed": stats.get(
                    "penalties_missed",
                    0,
                ),
                "saves": stats.get("saves", 0),
                "bonus": stats.get("bonus", 0),
                "bps": stats.get("bps", 0),
                "yellow_cards": stats.get(
                    "yellow_cards",
                    0,
                ),
                "red_cards": stats.get(
                    "red_cards",
                    0,
                ),
                "expected_goals": _as_float(
                    stats.get("expected_goals")
                ),
                "expected_assists": _as_float(
                    stats.get("expected_assists")
                ),
                "expected_goal_involvements": _as_float(
                    stats.get("expected_goal_involvements")
                ),
                "expected_goals_conceded": _as_float(
                    stats.get("expected_goals_conceded")
                ),
                "influence": _as_float(
                    stats.get("influence")
                ),
                "creativity": _as_float(
                    stats.get("creativity")
                ),
                "threat": _as_float(
                    stats.get("threat")
                ),
                "ict_index": _as_float(
                    stats.get("ict_index")
                ),
                "clearances_blocks_interceptions": stats.get(
                    "clearances_blocks_interceptions",
                    0,
                ),
                "recoveries": stats.get(
                    "recoveries",
                    0,
                ),
                "tackles": stats.get(
                    "tackles",
                    0,
                ),
                "defensive_contribution": stats.get(
                    "defensive_contribution",
                    0,
                ),
                "value": stats.get("value"),
                "selected": stats.get("selected"),
                "transfers_balance": stats.get(
                    "transfers_balance"
                ),
                "transfers_in": stats.get("transfers_in"),
                "transfers_out": stats.get("transfers_out"),
                "ingestion_run_id": ingestion_run_id,
            }
        )

    return records


# ----------------------------------------------------------------------
# Refresh manager
# ----------------------------------------------------------------------


class FPLRefreshManager:
    """
    Refresh FPL data and persist it for later analysis.

    Two persistence modes currently exist:

    1. Legacy JSON mode
       FPLRefreshManager(source, json_store)

    2. SQLite mode
       FPLRefreshManager(
           source,
           repository=sqlite_repository,
           season_code="2026/27",
       )

    SQLite is the new canonical persistence path.
    JSON remains temporarily for backward compatibility.
    """

    SOURCE_NAME = "fpl_api"

    def __init__(
        self,
        data_source: FPLDataSource,
        store: JsonDataStore | None = None,
        repository: Repository | None = None,
        season_code: str = DEFAULT_SEASON_CODE,
    ) -> None:
        self.data_source = data_source
        self.store = store
        self.repository = repository
        self.season_code = season_code

        if self.store is None and self.repository is None:
            raise ValueError(
                "Either a JsonDataStore or a Repository must be supplied."
            )

    # ------------------------------------------------------------------
    # SQLite global refresh
    # ------------------------------------------------------------------

    def _refresh_global_data_sqlite(self) -> RefreshReport:
        """Refresh global FPL data into the repository."""

        started_at = _timestamp()

        ingestion_run_id: int | None = None

        try:
            # ----------------------------------------------------------
            # Fetch official source data first.
            # ----------------------------------------------------------

            bootstrap = self.data_source.fetch_bootstrap_static()
            bootstrap_retrieved_at = _timestamp()

            fixtures = self.data_source.fetch_fixtures()
            fixtures_retrieved_at = _timestamp()

            source_retrieved_at = max(
                bootstrap_retrieved_at,
                fixtures_retrieved_at,
            )

            # ----------------------------------------------------------
            # Create one auditable ingestion run for the complete
            # global refresh.
            # ----------------------------------------------------------

            ingestion_run_id = self.repository.create_ingestion_run(
                source_system=self.SOURCE_NAME,
                source_type="API",
                endpoint_or_file=(
                    "bootstrap-static/;fixtures/"
                ),
                started_at=started_at,
                source_retrieved_at=source_retrieved_at,
                status="RUNNING",
            )

            # ----------------------------------------------------------
            # Basic source validation.
            # ----------------------------------------------------------

            elements = bootstrap.get("elements", [])
            teams = bootstrap.get("teams", [])
            events = bootstrap.get("events", [])
            element_types = bootstrap.get("element_types", [])

            if not isinstance(elements, list):
                raise ValueError(
                    "FPL bootstrap 'elements' is not a list."
                )

            if not isinstance(teams, list):
                raise ValueError(
                    "FPL bootstrap 'teams' is not a list."
                )

            if not isinstance(events, list):
                raise ValueError(
                    "FPL bootstrap 'events' is not a list."
                )

            if not isinstance(element_types, list):
                raise ValueError(
                    "FPL bootstrap 'element_types' is not a list."
                )

            if not isinstance(fixtures, list):
                raise ValueError(
                    "FPL fixtures payload is not a list."
                )

            # ----------------------------------------------------------
            # Create/get season.
            #
            # Season dates are intentionally left null here because
            # bootstrap-static does not provide a canonical season
            # start/end pair in the project contract.
            # ----------------------------------------------------------

            season = self.repository.get_season(
                self.season_code
            )

            if season is None:
                season_id = self.repository.create_season(
                    season_code=self.season_code,
                    status="ACTIVE",
                    is_current=True,
                )
            else:
                season_id = int(season["id"])

            # ----------------------------------------------------------
            # Build lookup tables.
            # ----------------------------------------------------------

            position_names = {
                int(position["id"]): position.get(
                    "singular_name"
                )
                for position in element_types
                if "id" in position
            }

            team_db_ids: dict[int, int] = {}
            player_db_ids: dict[int, int] = {}
            gameweek_db_ids: dict[int, int] = {}

            counts = {
                "seasons": 1,
                "gameweeks": 0,
                "teams": 0,
                "team_snapshots": 0,
                "players": 0,
                "player_snapshots": 0,
                "fixtures": 0,
                "player_gameweek_stats": 0,
            }

            # ----------------------------------------------------------
            # Persist gameweeks.
            #
            # Batch 3 intentionally creates missing gameweeks only.
            # Dynamic gameweek flag updates will be handled in the
            # dedicated gameweek refresh enhancement after this batch.
            # ----------------------------------------------------------

            for event in events:
                if "id" not in event:
                    continue

                gameweek_number = int(event["id"])

                existing_gameweek = self.repository.get_gameweek(
                    season_id,
                    gameweek_number,
                )

                if existing_gameweek is None:
                    gameweek_db_ids[
                        gameweek_number
                    ] = self.repository.create_gameweek(
                        season_id=season_id,
                        gameweek=gameweek_number,
                        name=event.get("name"),
                        deadline_time=event.get(
                            "deadline_time"
                        ),
                        finished=bool(
                            event.get("finished", False)
                        ),
                    )
                    counts["gameweeks"] += 1
                else:
                    gameweek_db_ids[
                        gameweek_number
                    ] = int(existing_gameweek["id"])

            # ----------------------------------------------------------
            # Persist teams and team snapshots.
            # ----------------------------------------------------------

            for team in teams:
                if "id" not in team:
                    continue

                fpl_team_id = int(team["id"])

                team_record = _build_team_record(team)

                # Repository methods use explicit arguments rather than
                # accepting the complete domain mapping.
                team_id = self.repository.upsert_team(
                    fpl_team_id=team_record["fpl_team_id"],
                    name=team_record["name"],
                    short_name=team_record.get("short_name"),
                    code=team_record.get("code"),
                )

                team_db_ids[fpl_team_id] = team_id
                counts["teams"] += 1

                team_snapshot = _build_team_snapshot(
                    team=team,
                    season_id=season_id,
                    snapshot_at=source_retrieved_at,
                    ingestion_run_id=ingestion_run_id,
                    team_id=team_id,
                )

                self.repository.create_team_snapshot(
                    season_id=season_id,
                    team_id=team_id,
                    snapshot_at=source_retrieved_at,
                    snapshot=team_snapshot,
                    ingestion_run_id=ingestion_run_id,
                )

                counts["team_snapshots"] += 1

            # ----------------------------------------------------------
            # Persist players and player snapshots.
            # ----------------------------------------------------------

            for player in elements:
                if "id" not in player:
                    continue

                fpl_player_id = int(player["id"])

                player_record = _build_player_record(player)

                player_id = self.repository.upsert_player(
                    fpl_player_id=player_record["fpl_player_id"],
                    first_name=player_record.get("first_name"),
                    second_name=player_record.get("second_name"),
                    web_name=player_record.get("web_name"),
                )

                player_db_ids[fpl_player_id] = player_id
                counts["players"] += 1

                team_id = team_db_ids.get(
                    int(player["team"])
                )

                if team_id is None:
                    raise ValueError(
                        f"Player {fpl_player_id} references "
                        f"unknown FPL team {player['team']}."
                    )

                snapshot = _build_player_snapshot(
                    player=player,
                    season_id=season_id,
                    snapshot_at=source_retrieved_at,
                    ingestion_run_id=ingestion_run_id,
                    team_id=team_id,
                    position_name=position_names.get(
                        int(player["element_type"])
                    ),
                )

                # The player ID belongs to the player master table,
                # not the team. Set it explicitly after building the
                # snapshot structure.
                snapshot["player_id"] = player_id

                self.repository.create_player_snapshot(
                    season_id=season_id,
                    player_id=player_id,
                    snapshot_at=source_retrieved_at,
                    snapshot=snapshot,
                    ingestion_run_id=ingestion_run_id,
                )

                counts["player_snapshots"] += 1

            # ----------------------------------------------------------
            # Persist fixtures and player-GW statistics.
            # ----------------------------------------------------------

            for fixture in fixtures:

                fixture_id = fixture.get("id")
                gameweek_number = fixture.get("event")
                home_fpl_team_id = fixture.get("team_h")
                away_fpl_team_id = fixture.get("team_a")

                if (
                    fixture_id is None
                    or gameweek_number is None
                    or home_fpl_team_id is None
                    or away_fpl_team_id is None
                ):
                    continue

                gameweek_id = gameweek_db_ids.get(
                    int(gameweek_number)
                )

                home_team_id = team_db_ids.get(
                    int(home_fpl_team_id)
                )
                away_team_id = team_db_ids.get(
                    int(away_fpl_team_id)
                )

                if gameweek_id is None:
                    raise ValueError(
                        f"Fixture {fixture_id} references "
                        f"unknown gameweek {gameweek_number}."
                    )

                if home_team_id is None:
                    raise ValueError(
                        f"Fixture {fixture_id} references "
                        f"unknown home team "
                        f"{home_fpl_team_id}."
                    )

                if away_team_id is None:
                    raise ValueError(
                        f"Fixture {fixture_id} references "
                        f"unknown away team "
                        f"{away_fpl_team_id}."
                    )

                fixture_record = {
                    "fpl_fixture_id": int(fixture_id),
                    "season_id": season_id,
                    "gameweek_id": gameweek_id,
                    "home_team_id": home_team_id,
                    "away_team_id": away_team_id,
                    "kickoff_time": fixture.get(
                        "kickoff_time"
                    ),
                    "started": fixture.get("started"),
                    "finished": fixture.get("finished"),
                    "home_score": fixture.get(
                        "team_h_score"
                    ),
                    "away_score": fixture.get(
                        "team_a_score"
                    ),
                    "home_difficulty": fixture.get(
                        "team_h_difficulty"
                    ),
                    "away_difficulty": fixture.get(
                        "team_a_difficulty"
                    ),
                }

                fixture_db_id = self.repository.upsert_fixture(
                    season_id=season_id,
                    fpl_fixture_id=fixture_record["fpl_fixture_id"],
                    home_team_id=fixture_record["home_team_id"],
                    away_team_id=fixture_record["away_team_id"],
                    gameweek_id=fixture_record.get("gameweek_id"),
                    kickoff_time=fixture_record.get("kickoff_time"),
                    started=bool(fixture_record.get("started", False)),
                    finished=bool(fixture_record.get("finished", False)),
                    home_score=fixture_record.get("home_score"),
                    away_score=fixture_record.get("away_score"),
                    home_difficulty=fixture_record.get("home_difficulty"),
                    away_difficulty=fixture_record.get("away_difficulty"),
                )

                counts["fixtures"] += 1

                # ------------------------------------------------------
                # Convert fixture stats into canonical player-GW rows.
                # ------------------------------------------------------

                stat_records = (
                    _build_player_gameweek_stat_records(
                        fixture=fixture,
                        season_id=season_id,
                        gameweek_id=gameweek_id,
                        fixture_id=fixture_db_id,
                        home_team_id=home_team_id,
                        away_team_id=away_team_id,
                        ingestion_run_id=ingestion_run_id,
                    )
                )

                for stat_record in stat_records:

                    fpl_player_id = int(
                        stat_record["player_id"]
                    )

                    # Fixture stats should reference a player known
                    # by bootstrap-static.
                    if (
                        fpl_player_id
                        not in player_db_ids
                    ):
                        raise ValueError(
                            f"Fixture {fixture_id} contains "
                            f"unknown player {fpl_player_id}."
                        )

                    stat_record["player_id"] = (
                        player_db_ids[fpl_player_id]
                    )

                    self.repository.upsert_current_player_gameweek_stats(
                        season_id=season_id,
                        player_id=stat_record["player_id"],
                        fixture_id=stat_record["fixture_id"],
                        stats=stat_record,
                        gameweek_id=stat_record.get("gameweek_id"),
                        ingestion_run_id=ingestion_run_id,
                    )

                    counts["player_gameweek_stats"] += 1

            # ----------------------------------------------------------
            # Complete ingestion run.
            # ----------------------------------------------------------

            records_received = (
                len(elements)
                + len(teams)
                + len(events)
                + len(fixtures)
            )

            records_written = (
                counts["teams"]
                + counts["team_snapshots"]
                + counts["players"]
                + counts["player_snapshots"]
                + counts["fixtures"]
                + counts["player_gameweek_stats"]
            )

            self.repository.complete_ingestion_run(
                ingestion_run_id=ingestion_run_id,
                completed_at=_timestamp(),
                status="SUCCESS",
                records_received=records_received,
                records_written=records_written,
                records_rejected=0,
                validation_status="PASSED",
                error_message=None,
            )

            completed_at = _timestamp()

            return RefreshReport(
                source=self.SOURCE_NAME,
                started_at=started_at,
                completed_at=completed_at,
                status="success",
                collections={
                    key: {
                        "records_written": value,
                    }
                    for key, value in counts.items()
                },
            )

        except Exception as exc:

            # ----------------------------------------------------------
            # Mark the ingestion run as failed if it was created.
            # ----------------------------------------------------------

            if ingestion_run_id is not None:
                try:
                    self.repository.complete_ingestion_run(
                        ingestion_run_id=ingestion_run_id,
                        completed_at=_timestamp(),
                        status="FAILED",
                        records_received=0,
                        records_written=0,
                        records_rejected=0,
                        validation_status="FAILED",
                        error_message=str(exc),
                    )
                except Exception:
                    # Do not hide the original refresh error because
                    # failure recording itself failed.
                    pass

            return RefreshReport(
                source=self.SOURCE_NAME,
                started_at=started_at,
                completed_at=_timestamp(),
                status="failed",
                collections={},
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Public global refresh
    # ------------------------------------------------------------------

    def refresh_global_data(self) -> RefreshReport:
        """
        Refresh bootstrap and fixture data.

        If a Repository was supplied, SQLite/domain persistence is used.

        Otherwise the legacy JsonDataStore path is used.
        """

        if self.repository is not None:
            return self._refresh_global_data_sqlite()

        # --------------------------------------------------------------
        # Legacy JSON path.
        # --------------------------------------------------------------

        started_at = _timestamp()

        try:
            bootstrap = self.data_source.fetch_bootstrap_static()
            fixtures = self.data_source.fetch_fixtures()

            player_stats = self.store.upsert_records(
                "fpl_players",
                _normalise_bootstrap_players(bootstrap),
                self.SOURCE_NAME,
            )

            fixture_stats = self.store.upsert_records(
                "fpl_fixtures",
                _normalise_fixtures(fixtures),
                self.SOURCE_NAME,
            )

            report = RefreshReport(
                self.SOURCE_NAME,
                started_at,
                _timestamp(),
                "success",
                {
                    "fpl_players": player_stats,
                    "fpl_fixtures": fixture_stats,
                },
            )

            self.store.save_refresh_metadata(
                self.SOURCE_NAME,
                {
                    "status": report.status,
                    "started_at": report.started_at,
                    "completed_at": report.completed_at,
                    "collections": report.collections,
                },
            )

            return report

        except Exception as exc:

            report = RefreshReport(
                self.SOURCE_NAME,
                started_at,
                _timestamp(),
                "failed",
                {},
                str(exc),
            )

            self.store.save_refresh_metadata(
                self.SOURCE_NAME,
                {
                    "status": report.status,
                    "started_at": report.started_at,
                    "completed_at": report.completed_at,
                    "error": report.error,
                },
            )

            return report

    # ------------------------------------------------------------------
    # League / rival refresh helpers
    # ------------------------------------------------------------------

    def _refresh_leagues_sqlite(
        self,
        manager_id: int,
        gameweek: int,
        league_ids: list[int],
        season_id: int,
        gameweek_id: int,
        primary_manager_db_id: int,
        primary_manager_picks: dict[str, Any],
    ) -> dict[str, int]:
        """
        Refresh one manager's configured leagues for one Gameweek.

        League membership, standings and rival squads are deliberately
        stored with the league ID in their uniqueness keys. Therefore the
        same FPL manager can appear in multiple leagues with different
        standings while remaining one manager entity in the database.

        Manager picks are cached by FPL manager ID during this refresh so
        an overlapping rival appearing in multiple leagues is fetched only
        once from the FPL API.
        """

        unique_league_ids = list(dict.fromkeys(int(value) for value in league_ids))
        if not unique_league_ids:
            return {
                "leagues": 0,
                "league_members": 0,
                "league_standings": 0,
                "rival_squad_snapshots": 0,
            }

        started_at = _timestamp()
        ingestion_run_id = self.repository.create_ingestion_run(
            source_system=self.SOURCE_NAME,
            source_type="API",
            endpoint_or_file=";".join(
                f"leagues-classic/{league_id}/standings/"
                for league_id in unique_league_ids
            ),
            started_at=started_at,
            source_retrieved_at=started_at,
            status="RUNNING",
        )

        counts = {
            "leagues": 0,
            "league_members": 0,
            "league_standings": 0,
            "rival_squad_snapshots": 0,
        }

        # One in-memory cache covers all leagues in this refresh.
        picks_cache: dict[int, dict[str, Any]] = {
            int(manager_id): primary_manager_picks
        }

        try:
            for league_id in unique_league_ids:
                # ------------------------------------------------------
                # Retrieve every standings page for this league.
                # ------------------------------------------------------
                page = 1
                standings_rows: list[dict[str, Any]] = []
                league_meta: dict[str, Any] = {}

                while True:
                    payload = self.data_source.fetch_classic_league_standings(
                        league_id,
                        page=page,
                        event=gameweek,
                    )
                    if page == 1:
                        league_meta = payload.get("league", {})

                    page_rows = payload.get("standings", {}).get("results", [])
                    if not isinstance(page_rows, list):
                        raise ValueError(
                            f"League {league_id} standings results are not a list."
                        )
                    standings_rows.extend(page_rows)

                    if not payload.get("standings", {}).get("has_next", False):
                        break
                    page += 1

                league_db_id = self.repository.upsert_league(
                    fpl_league_id=league_id,
                    season_id=season_id,
                    name=league_meta.get("name"),
                    league_type=league_meta.get("league_type") or "classic",
                )
                counts["leagues"] += 1

                # ------------------------------------------------------
                # Persist membership and league-specific standings.
                # ------------------------------------------------------
                for standing in standings_rows:
                    fpl_rival_id = _as_int(standing.get("id"))
                    if fpl_rival_id is None:
                        raise ValueError(
                            f"League {league_id} contains a standing without a manager ID."
                        )

                    if fpl_rival_id == manager_id:
                        rival_db_id = primary_manager_db_id
                    else:
                        # A manager in a league needs a manager entity even
                        # if that manager is not one of the application's
                        # configured users. Reusing the FPL ID keeps the
                        # manager unique across all leagues.
                        user_id = self.repository.upsert_user(
                            external_user_key=str(fpl_rival_id),
                            display_name=standing.get("player_name"),
                        )
                        rival_db_id = self.repository.upsert_manager(
                            user_id=user_id,
                            fpl_manager_id=fpl_rival_id,
                            manager_name=standing.get("player_name"),
                            team_name=standing.get("entry_name"),
                        )

                    self.repository.upsert_league_member(
                        league_id=league_db_id,
                        manager_id=rival_db_id,
                    )
                    counts["league_members"] += 1

                    rank = _as_int(standing.get("rank"))
                    last_rank = _as_int(standing.get("last_rank"))
                    rank_change = None
                    if rank is not None and last_rank is not None:
                        rank_change = last_rank - rank

                    self.repository.upsert_league_standing(
                        league_id=league_db_id,
                        manager_id=rival_db_id,
                        season_id=season_id,
                        gameweek_id=gameweek_id,
                        rank=rank,
                        total_points=_as_int(standing.get("total")),
                        last_rank=last_rank,
                        rank_change=rank_change,
                        ingestion_run_id=ingestion_run_id,
                    )
                    counts["league_standings"] += 1

                # ------------------------------------------------------
                # Persist squad snapshots for rivals only.
                # ------------------------------------------------------
                for standing in standings_rows:
                    fpl_rival_id = _as_int(standing.get("id"))
                    if fpl_rival_id is None or fpl_rival_id == manager_id:
                        continue

                    if fpl_rival_id not in picks_cache:
                        picks_cache[fpl_rival_id] = self.data_source.fetch_manager_picks(
                            fpl_rival_id,
                            gameweek,
                        )

                    rival_picks = picks_cache[fpl_rival_id]
                    for pick in rival_picks.get("picks", []):
                        fpl_player_id = _as_int(pick.get("element"))
                        if fpl_player_id is None:
                            raise ValueError(
                                f"Manager {fpl_rival_id} has a pick without a player ID."
                            )

                        player = self.repository.fetch_one(
                            "SELECT id FROM players WHERE fpl_player_id = ?",
                            (fpl_player_id,),
                        )
                        if player is None:
                            raise ValueError(
                                f"Player {fpl_player_id} from rival manager {fpl_rival_id} "
                                "is not present in SQLite. Run the global refresh first."
                            )

                        # Find the internal manager ID already created above.
                        rival_user_id = self.repository.upsert_user(
                            external_user_key=str(fpl_rival_id),
                            display_name=standing.get("player_name"),
                        )
                        rival_db_id = self.repository.upsert_manager(
                            user_id=rival_user_id,
                            fpl_manager_id=fpl_rival_id,
                            manager_name=standing.get("player_name"),
                            team_name=standing.get("entry_name"),
                        )

                        self.repository.upsert_rival_squad_snapshot(
                            league_id=league_db_id,
                            manager_id=rival_db_id,
                            season_id=season_id,
                            gameweek_id=gameweek_id,
                            player_id=int(player["id"]),
                            position=_as_int(pick.get("position")),
                            is_captain=bool(pick.get("is_captain")),
                            is_vice_captain=bool(pick.get("is_vice_captain")),
                            multiplier=_as_int(pick.get("multiplier")),
                            ingestion_run_id=ingestion_run_id,
                        )
                        counts["rival_squad_snapshots"] += 1

            self.repository.complete_ingestion_run(
                ingestion_run_id=ingestion_run_id,
                status="SUCCESS",
                completed_at=_timestamp(),
                records_received=(
                    counts["league_standings"]
                    + counts["rival_squad_snapshots"]
                ),
                records_written=sum(counts.values()),
                records_rejected=0,
                validation_status="PASS",
            )
            return counts

        except Exception as exc:
            self.repository.complete_ingestion_run(
                ingestion_run_id=ingestion_run_id,
                status="FAILED",
                completed_at=_timestamp(),
                records_received=0,
                records_written=0,
                records_rejected=0,
                validation_status="FAIL",
                error_message=str(exc),
            )
            raise

    # ------------------------------------------------------------------
    # Existing manager refresh
    # ------------------------------------------------------------------

    def refresh_manager_data(
        self,
        manager_id: int,
        gameweek: int,
        league_ids: list[int] | None = None,
    ) -> RefreshReport:
        """
        Refresh one manager's official state and, optionally, leagues.

        ``league_ids`` is intentionally a list so one manager can belong to
        any number of configured leagues. There is no hard-coded league ID.
        """

        if self.store is None and self.repository is None:
            raise ValueError(
                "Manager refresh requires a JsonDataStore or Repository."
            )

        started_at = _timestamp()
        ingestion_run_id: int | None = None

        try:
            picks = self.data_source.fetch_manager_picks(manager_id, gameweek)
            manager_data = self.data_source.fetch_manager_entry(manager_id)
            history = self.data_source.fetch_manager_history(manager_id)
            transfers = self.data_source.fetch_manager_transfers(manager_id)

            if self.repository is None:
                picks_stats = self.store.upsert_records(
                    f"manager_{manager_id}_picks",
                    [{"record_id": str(gameweek), "payload": picks}],
                    self.SOURCE_NAME,
                )
                history_stats = self.store.upsert_records(
                    f"manager_{manager_id}_history",
                    [{"record_id": "season_history", "payload": history}],
                    self.SOURCE_NAME,
                )
                return RefreshReport(
                    self.SOURCE_NAME, started_at, _timestamp(), "success",
                    {"manager_picks": picks_stats, "manager_history": history_stats},
                )

            source_timestamp = _timestamp()
            season = self.repository.get_season(self.season_code)
            if season is None:
                raise ValueError(
                    f"Season {self.season_code} is not present in SQLite. "
                    "Run the global refresh before manager refresh."
                )
            season_id = int(season["id"])

            gameweek_row = self.repository.get_gameweek(season_id, gameweek)
            if gameweek_row is None:
                raise ValueError(
                    f"Gameweek {gameweek} is not present in SQLite. "
                    "Run the global refresh before manager refresh."
                )
            gameweek_id = int(gameweek_row["id"])

            ingestion_run_id = self.repository.create_ingestion_run(
                source_system=self.SOURCE_NAME,
                source_type="API",
                endpoint_or_file=(
                    f"entry/{manager_id}/;entry/{manager_id}/event/{gameweek}/picks/;"
                    f"entry/{manager_id}/history/;entry/{manager_id}/transfers/"
                ),
                started_at=started_at,
                source_retrieved_at=source_timestamp,
                status="RUNNING",
            )

            user_id = self.repository.upsert_user(
                external_user_key=str(manager_id),
                display_name=(
                    f"{manager_data.get('player_first_name', '')} "
                    f"{manager_data.get('player_last_name', '')}"
                ).strip() or None,
            )
            manager_db_id = self.repository.upsert_manager(
                user_id=user_id,
                fpl_manager_id=manager_id,
                manager_name=(
                    f"{manager_data.get('player_first_name', '')} "
                    f"{manager_data.get('player_last_name', '')}"
                ).strip() or None,
                team_name=manager_data.get("name"),
            )

            entry_history = picks.get("entry_history", {})
            self.repository.upsert_manager_gameweek_state(
                manager_id=manager_db_id,
                season_id=season_id,
                gameweek_id=gameweek_id,
                points=_as_int(entry_history.get("points")),
                total_points=_as_int(entry_history.get("total_points")),
                overall_rank=_as_int(manager_data.get("summary_overall_rank")),
                rank=_as_int(entry_history.get("rank")),
                bank=(
                    _as_int(entry_history.get("bank")) / 10.0
                    if entry_history.get("bank") is not None else None
                ),
                team_value=(
                    _as_int(entry_history.get("value")) / 10.0
                    if entry_history.get("value") is not None else None
                ),
                event_transfers=_as_int(entry_history.get("event_transfers")),
                event_transfers_cost=_as_int(entry_history.get("event_transfers_cost")),
                points_on_bench=_as_int(entry_history.get("points_on_bench")),
                source_timestamp=source_timestamp,
                ingestion_run_id=ingestion_run_id,
            )

            pick_count = 0
            for pick in picks.get("picks", []):
                fpl_player_id = _as_int(pick.get("element"))
                if fpl_player_id is None:
                    raise ValueError("Manager pick is missing element/player ID.")
                player = self.repository.fetch_one(
                    "SELECT id FROM players WHERE fpl_player_id = ?",
                    (fpl_player_id,),
                )
                if player is None:
                    raise ValueError(
                        f"Player {fpl_player_id} from manager picks is not present in SQLite. "
                        "Run the global refresh first."
                    )
                self.repository.upsert_manager_pick(
                    manager_id=manager_db_id,
                    season_id=season_id,
                    gameweek_id=gameweek_id,
                    player_id=int(player["id"]),
                    position=_as_int(pick.get("position")),
                    multiplier=_as_int(pick.get("multiplier")),
                    is_captain=bool(pick.get("is_captain")),
                    is_vice_captain=bool(pick.get("is_vice_captain")),
                    purchase_price=(
                        _as_int(pick.get("purchase_price")) / 10.0
                        if pick.get("purchase_price") is not None else None
                    ),
                    ingestion_run_id=ingestion_run_id,
                )
                pick_count += 1

            transfer_count = 0
            for transfer in transfers.get("transfers", []):
                event = _as_int(transfer.get("event"))
                if event is None:
                    raise ValueError("Manager transfer is missing its Gameweek event.")
                transfer_gameweek = self.repository.get_gameweek(season_id, event)
                if transfer_gameweek is None:
                    raise ValueError(
                        f"Transfer references Gameweek {event}, which is not present in SQLite."
                    )
                player_in = self.repository.fetch_one(
                    "SELECT id FROM players WHERE fpl_player_id = ?",
                    (_as_int(transfer.get("element_in")),),
                )
                player_out = self.repository.fetch_one(
                    "SELECT id FROM players WHERE fpl_player_id = ?",
                    (_as_int(transfer.get("element_out")),),
                )
                if player_in is None or player_out is None:
                    raise ValueError(
                        "Manager transfer references a player missing from SQLite. "
                        "Run the global refresh first."
                    )
                self.repository.create_manager_transfer(
                    manager_id=manager_db_id,
                    season_id=season_id,
                    gameweek_id=int(transfer_gameweek["id"]),
                    transfer_timestamp=transfer.get("time"),
                    player_in_id=int(player_in["id"]),
                    player_out_id=int(player_out["id"]),
                    cost=_as_int(transfer.get("cost")),
                    external_transfer_id=(
                        str(transfer["id"]) if transfer.get("id") is not None else None
                    ),
                    ingestion_run_id=ingestion_run_id,
                )
                transfer_count += 1

            chip_count = 0
            for chip in history.get("chips", []):
                chip_type = chip.get("name")
                if not chip_type:
                    continue
                chip_event = _as_int(chip.get("event"))
                chip_gameweek_id = None
                if chip_event is not None:
                    chip_gameweek = self.repository.get_gameweek(season_id, chip_event)
                    if chip_gameweek is None:
                        raise ValueError(
                            f"Chip references Gameweek {chip_event}, which is not present in SQLite."
                        )
                    chip_gameweek_id = int(chip_gameweek["id"])
                self.repository.upsert_manager_chip(
                    manager_id=manager_db_id,
                    season_id=season_id,
                    chip_type=str(chip_type),
                    gameweek_id=chip_gameweek_id,
                )
                chip_count += 1

            league_counts = {
                "leagues": 0,
                "league_members": 0,
                "league_standings": 0,
                "rival_squad_snapshots": 0,
            }
            if league_ids:
                league_counts = self._refresh_leagues_sqlite(
                    manager_id=manager_id,
                    gameweek=gameweek,
                    league_ids=league_ids,
                    season_id=season_id,
                    gameweek_id=gameweek_id,
                    primary_manager_db_id=manager_db_id,
                    primary_manager_picks=picks,
                )

            self.repository.complete_ingestion_run(
                ingestion_run_id=ingestion_run_id,
                status="SUCCESS",
                completed_at=_timestamp(),
                records_received=(
                    1 + len(picks.get("picks", [])) +
                    len(transfers.get("transfers", [])) +
                    len(history.get("chips", []))
                ),
                records_written=1 + pick_count + transfer_count + chip_count,
                records_rejected=0,
                validation_status="PASS",
            )

            collections = {
                "manager": {"records_written": 1},
                "manager_picks": {"records_written": pick_count},
                "manager_transfers": {"records_written": transfer_count},
                "manager_chips": {"records_written": chip_count},
            }
            collections.update({
                key: {"records_written": value}
                for key, value in league_counts.items()
                if value
            })

            return RefreshReport(
                self.SOURCE_NAME, started_at, _timestamp(), "success", collections,
            )

        except Exception as exc:
            if ingestion_run_id is not None and self.repository is not None:
                try:
                    self.repository.complete_ingestion_run(
                        ingestion_run_id=ingestion_run_id,
                        status="FAILED",
                        completed_at=_timestamp(),
                        records_received=0,
                        records_written=0,
                        records_rejected=0,
                        validation_status="FAIL",
                        error_message=str(exc),
                    )
                except Exception:
                    pass
            return RefreshReport(
                self.SOURCE_NAME, started_at, _timestamp(), "failed", {}, str(exc)
            )

    # ------------------------------------------------------------------
    # Existing refresh entry point
    # ------------------------------------------------------------------

    def refresh_if_needed(
        self,
        manager_id: int | None = None,
        gameweek: int | None = None,
        league_ids: list[int] | None = None,
    ) -> RefreshReport:
        """
        Run the current explicit refresh policy.

        Freshness windows and dependency-aware scheduling remain
        intentionally separate from this persistence integration.
        """

        if manager_id is not None and gameweek is not None:
            return self.refresh_manager_data(
                manager_id,
                gameweek,
                league_ids=league_ids,
            )

        return self.refresh_global_data()