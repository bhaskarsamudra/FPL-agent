"""Tests for the incremental persistent data store."""

from data_store import JsonDataStore, record_hash


def test_record_hash_is_deterministic():
    """Equivalent dictionaries must produce the same hash."""
    assert record_hash({"b": 2, "a": 1}) == record_hash({"a": 1, "b": 2})


def test_upsert_classifies_added_updated_and_unchanged(tmp_path):
    """The store should distinguish new, changed and unchanged data."""
    store = JsonDataStore(tmp_path)

    assert store.upsert_records(
        "players", [{"record_id": "1", "payload": {"form": "5.0"}}],
        "test", "2026-09-27T10:00:00+00:00"
    ) == {"records_added": 1, "records_updated": 0, "records_unchanged": 0}

    assert store.upsert_records(
        "players", [{"record_id": "1", "payload": {"form": "5.0"}}],
        "test", "2026-09-27T11:00:00+00:00"
    ) == {"records_added": 0, "records_updated": 0, "records_unchanged": 1}

    assert store.upsert_records(
        "players", [{"record_id": "1", "payload": {"form": "6.0"}}],
        "test", "2026-09-27T12:00:00+00:00"
    ) == {"records_added": 0, "records_updated": 1, "records_unchanged": 0}

    record = store.get_record("players", "1")
    assert record is not None
    assert record.payload["form"] == "6.0"
    assert record.first_seen_at == "2026-09-27T10:00:00+00:00"
    assert record.last_seen_at == "2026-09-27T12:00:00+00:00"


def test_refresh_metadata_round_trip(tmp_path):
    """Refresh metadata must be persisted separately from records."""
    store = JsonDataStore(tmp_path)
    metadata = {"status": "success", "completed_at": "2026-09-27T12:00:00+00:00"}
    store.save_refresh_metadata("fpl_api", metadata)
    assert store.get_refresh_metadata("fpl_api") == metadata
