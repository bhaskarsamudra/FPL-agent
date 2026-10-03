"""Tests for versioned FPL rules and exceptional changes."""

from rules_source import RulesSourceDocument
from rules_store import RulesStore
from rules_versioning import check_for_change, install_rules_version


def document(max_free_transfers: int, version: str = "official") -> RulesSourceDocument:
    """Build a small synthetic authoritative rules document."""
    return RulesSourceDocument(
        source_name="Official FPL",
        season="2026/27",
        retrieved_at="2026-09-27T10:00:00+05:30",
        source_version=version,
        payload={"max_free_transfers": max_free_transfers},
    )


def test_first_rules_snapshot_is_a_change():
    """No active rules means the first snapshot must be installed."""
    store = RulesStore()

    result = check_for_change(store, document(5))

    assert result.changed is True
    assert result.active_version is None


def test_identical_rules_are_not_a_change():
    """Retrieving identical rules must not create a new logical version."""
    store = RulesStore()

    first = install_rules_version(
        store,
        document(5),
        "2026-08-01T00:00:00+00:00",
    )

    result = check_for_change(store, document(5))

    assert result.changed is False
    assert result.active_version == first.version


def test_identical_rules_return_existing_version():
    """
    Re-installing the same rules payload should return the existing active
    immutable version rather than creating a duplicate.
    """
    store = RulesStore()

    first = install_rules_version(
        store,
        document(5),
        "2026-08-01T00:00:00+00:00",
    )
    second = install_rules_version(
        store,
        document(5, version="same-rules-retrieved-again"),
        "2026-09-01T00:00:00+00:00",
    )

    assert second.version == first.version
    assert second.active is True
    assert len(store.list_versions("2026/27")) == 1


def test_exceptional_midseason_change_creates_new_version():
    """
    A genuinely changed rules payload creates a new active version while
    preserving the previous immutable version as historical data.
    """
    store = RulesStore()

    first = install_rules_version(
        store,
        document(5),
        "2026-08-01T00:00:00+00:00",
    )
    second = install_rules_version(
        store,
        document(6, version="exceptional-change"),
        "2026-11-15T00:00:00+00:00",
    )

    assert first.version != second.version
    assert second.active is True
    assert second.rules["max_free_transfers"] == 6

    # The original object remains immutable. Verify the closed validity period
    # on the historical version stored in the repository instead.
    stored_versions = store.list_versions("2026/27")
    historical = next(
        item for item in stored_versions if item.version == first.version
    )

    assert historical.valid_to == "2026-11-15T00:00:00+00:00"
    assert historical.active is False

    active = store.get_active("2026/27")
    assert active is not None
    assert active.version == second.version
    assert active.valid_to is None
