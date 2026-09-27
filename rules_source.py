"""
Authoritative FPL rules source adapter.

V1 keeps the source adapter deliberately small. The adapter fetches or receives
official rules material; it does not make strategic decisions.

The production cloud implementation can replace the fetch method with the
chosen official-source retrieval mechanism without changing the Rules Engine.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RulesSourceDocument:
    """One retrieved official rules document."""

    source_name: str
    season: str
    retrieved_at: str
    source_version: str
    payload: dict[str, Any]


class RulesSourceError(RuntimeError):
    """Raised when authoritative rules cannot be retrieved or validated."""


def validate_rules_document(document: RulesSourceDocument) -> None:
    """Validate the minimum metadata required before storing a rules version."""
    if not document.source_name.strip():
        raise RulesSourceError("Rules source name is required.")
    if not document.season.strip():
        raise RulesSourceError("Rules season is required.")
    if not document.retrieved_at.strip():
        raise RulesSourceError("Rules retrieval timestamp is required.")
    if not document.source_version.strip():
        raise RulesSourceError("Rules source version is required.")
    if not isinstance(document.payload, dict) or not document.payload:
        raise RulesSourceError("Rules payload must be a non-empty dictionary.")
