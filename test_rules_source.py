"""Tests for official-rules source contracts."""

import pytest

from rules_source import (
    RulesSourceDocument,
    RulesSourceError,
    validate_rules_document,
)


def test_valid_rules_document():
    document = RulesSourceDocument(
        source_name="Official FPL",
        season="2026/27",
        retrieved_at="2026-09-27T10:00:00+05:30",
        source_version="official-2026-27-v1",
        payload={"max_free_transfers": 5},
    )
    validate_rules_document(document)


def test_invalid_rules_document_is_rejected():
    document = RulesSourceDocument(
        source_name="",
        season="2026/27",
        retrieved_at="2026-09-27T10:00:00+05:30",
        source_version="v1",
        payload={"max_free_transfers": 5},
    )
    with pytest.raises(RulesSourceError):
        validate_rules_document(document)
