"""
Contracts shared by Layer 2 refresh components.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RefreshDecision:
    """Decision about whether a dataset needs refreshing."""

    dataset: str
    required: bool
    reason: str
    age_minutes: float | None
    ttl_minutes: int | None


@dataclass(frozen=True)
class RefreshResult:
    """Summary of one refresh operation."""

    dataset: str
    success: bool
    added: int
    updated: int
    unchanged: int
    fetched_records: int
    error: str | None = None


@dataclass(frozen=True)
class EndpointRecord:
    """One normalized record ready for the persistent store."""

    record_key: str
    payload: dict[str, Any]
