"""
Rules versioning and change detection.

Ordinary seasonal rule changes create a new immutable version. A new version can
also be activated if an exceptional mid-season rule change is detected.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any

from rules_source import RulesSourceDocument, validate_rules_document
from rules_store import RulesStore, StoredRulesVersion


@dataclass(frozen=True)
class RulesChangeResult:
    """Result of comparing incoming rules with the active snapshot."""

    changed: bool
    active_version: str | None
    incoming_fingerprint: str


def fingerprint_rules(payload: dict[str, Any]) -> str:
    """Create a stable fingerprint for a rules payload."""
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(serialized.encode("utf-8")).hexdigest()


def check_for_change(
    store: RulesStore,
    document: RulesSourceDocument,
) -> RulesChangeResult:
    """Compare an incoming authoritative rules document with active rules."""
    validate_rules_document(document)

    incoming_fingerprint = fingerprint_rules(document.payload)
    active = store.get_active(document.season)

    if active is None:
        return RulesChangeResult(
            changed=True,
            active_version=None,
            incoming_fingerprint=incoming_fingerprint,
        )

    active_fingerprint = fingerprint_rules(active.rules)

    return RulesChangeResult(
        changed=active_fingerprint != incoming_fingerprint,
        active_version=active.version,
        incoming_fingerprint=incoming_fingerprint,
    )


def install_rules_version(
    store: RulesStore,
    document: RulesSourceDocument,
    valid_from: str,
) -> StoredRulesVersion:
    """
    Store and activate a new immutable rules version.

    Version identifiers are derived from the rules fingerprint, making repeated
    retrieval of identical rules idempotent at the logical version level.
    """
    validate_rules_document(document)

    version = f"{document.season}-{fingerprint_rules(document.payload)[:12]}"
    current = store.get_active(document.season)

    if current is not None and fingerprint_rules(current.rules) == fingerprint_rules(document.payload):
        return current

    if current is not None:
        closed = StoredRulesVersion(
            season=current.season,
            version=current.version,
            valid_from=current.valid_from,
            valid_to=valid_from,
            source_name=current.source_name,
            retrieved_at=current.retrieved_at,
            rules=current.rules,
            active=False,
        )
        # Replace the previous active snapshot while preserving history.
        existing = store.list_versions(document.season)
        store._versions = [item for item in store._versions if item.version != current.version]
        store.save_version(closed)

    new_version = StoredRulesVersion(
        season=document.season,
        version=version,
        valid_from=valid_from,
        valid_to=None,
        source_name=document.source_name,
        retrieved_at=document.retrieved_at,
        rules=document.payload,
        active=False,
    )
    store.save_version(new_version)
    store.activate_version(document.season, version)
    return store.get_active(document.season)
