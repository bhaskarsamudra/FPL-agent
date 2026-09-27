"""Tests for FPL incremental refresh orchestration."""

from data_store import JsonDataStore
from fpl_data_source import FPLDataSource
from refresh_manager import FPLRefreshManager


class FakeFPLSource(FPLDataSource):
    """Fake source so tests never call the live network."""

    def __init__(self):
        super().__init__(base_url="https://example.invalid")
        self.bootstrap_calls = 0
        self.fixture_calls = 0
        self.picks_calls = 0
        self.history_calls = 0

    def fetch_bootstrap_static(self):
        self.bootstrap_calls += 1
        return {
            "elements": [
                {"id": 1, "name": "Player A", "form": "5.0"},
                {"id": 2, "name": "Player B", "form": "4.0"},
            ]
        }

    def fetch_fixtures(self):
        self.fixture_calls += 1
        return [{"id": 101, "event": 6, "team_h": 1, "team_a": 2}]

    def fetch_manager_picks(self, manager_id, gameweek):
        self.picks_calls += 1
        return {"entry_history": {"event": gameweek, "bank": 10}, "picks": []}

    def fetch_manager_history(self, manager_id):
        self.history_calls += 1
        return {"chips": [], "current": []}


def test_global_refresh_stores_new_records(tmp_path):
    """The first refresh should insert player and fixture records."""
    source = FakeFPLSource()
    manager = FPLRefreshManager(source, JsonDataStore(tmp_path))
    report = manager.refresh_global_data()

    assert report.status == "success"
    assert report.collections["fpl_players"]["records_added"] == 2
    assert report.collections["fpl_fixtures"]["records_added"] == 1


def test_second_refresh_detects_unchanged_records(tmp_path):
    """Repeated identical data should be classified as unchanged."""
    source = FakeFPLSource()
    manager = FPLRefreshManager(source, JsonDataStore(tmp_path))

    manager.refresh_global_data()
    report = manager.refresh_global_data()

    assert report.collections["fpl_players"]["records_added"] == 0
    assert report.collections["fpl_players"]["records_updated"] == 0
    assert report.collections["fpl_players"]["records_unchanged"] == 2


def test_manager_refresh_is_user_scoped(tmp_path):
    """Manager data must live in manager-specific collections."""
    source = FakeFPLSource()
    store = JsonDataStore(tmp_path)
    manager = FPLRefreshManager(source, store)

    report = manager.refresh_manager_data(3325156, 6)

    assert report.status == "success"
    assert store.get_record("manager_3325156_picks", "6") is not None
    assert store.get_record("manager_3325156_history", "season_history") is not None
