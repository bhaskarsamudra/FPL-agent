"""
recommendation_audit.py

Creates compact audit records for important strategy decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class RecommendationAudit:
    gameweek: int
    generated_at: str
    engine_version: str
    action: str
    source_status: str
    data_quality_status: str
    evidence: tuple[str, ...]
    model_inputs: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_audit_record(
    *,
    gameweek: int,
    generated_at: str,
    engine_version: str,
    action: str,
    source_status: str,
    data_quality_status: str,
    evidence: list[str] | tuple[str, ...],
    model_inputs: dict[str, Any],
) -> RecommendationAudit:
    """Build one auditable recommendation record."""

    return RecommendationAudit(
        gameweek=int(gameweek),
        generated_at=str(generated_at),
        engine_version=str(engine_version),
        action=str(action),
        source_status=str(source_status),
        data_quality_status=str(data_quality_status),
        evidence=tuple(str(item) for item in evidence),
        model_inputs=dict(model_inputs),
    )
