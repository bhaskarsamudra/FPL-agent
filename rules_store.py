"""
Versioned storage contract for official FPL rules.

This V1 uses an in-memory implementation for testing. The interface is designed
so the production implementation can use the project's persistent cloud store.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StoredRulesVersion:
    """One immutable rules snapshot."""

    season: str
    version: str
    valid_from: str
    valid_to: str | None
    source_name: str
    retrieved_at: str
    rules: dict[str, Any]
    active: bool


class RulesStore:
    """Small versioned rules repository used by the Rules Engine."""

    def __init__(self) -> None:
        self._versions: list[StoredRulesVersion] = []

    def save_version(self, version: StoredRulesVersion) -> None:
        """Store a rules snapshot without mutating previously stored versions."""
        self._versions.append(version)

    def activate_version(self, season: str, version: str) -> None:
        """Mark exactly one version active for a season."""
        updated: list[StoredRulesVersion] = []

        found = False
        for item in self._versions:
            if item.season == season:
                is_target = item.version == version
                found = found or is_target
                updated.append(
                    StoredRulesVersion(
                        season=item.season,
                        version=item.version,
                        valid_from=item.valid_from,
                        valid_to=item.valid_to,
                        source_name=item.source_name,
                        retrieved_at=item.retrieved_at,
                        rules=item.rules,
                        active=is_target,
                    )
                )
            else:
                updated.append(item)

        if not found:
            raise KeyError(f"Rules version '{version}' not found for {season}.")

        self._versions = updated

    def get_active(self, season: str) -> StoredRulesVersion | None:
        """Return the active rules snapshot for a season, if one exists."""
        for item in reversed(self._versions):
            if item.season == season and item.active:
                return item
        return None

    def list_versions(self, season: str) -> list[StoredRulesVersion]:
        """Return all versions for a season in insertion order."""
        return [item for item in self._versions if item.season == season]
