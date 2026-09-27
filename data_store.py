"""Persistent, source-agnostic data store for the FPL Strategist."""

from __future__ import annotations
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> str:
    """Serialize a value deterministically for change detection."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def record_hash(value: Any) -> str:
    """Create a deterministic hash for a payload."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class StoredRecord:
    """One verified observation stored by the application."""
    record_id: str
    payload: dict[str, Any]
    first_seen_at: str
    last_seen_at: str
    source: str
    payload_hash: str


class JsonDataStore:
    """
    Local V1 persistence layer.

    The interface is intentionally small so it can later be backed by a
    cloud database without changing the refresh/strategy contracts.
    """

    def __init__(self, root_dir: str | Path = "data_store") -> None:
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, collection: str) -> Path:
        return self.root_dir / f"{collection}.json"

    def _load(self, collection: str) -> dict[str, Any]:
        path = self._path(collection)
        if not path.exists():
            return {"records": {}, "refresh_metadata": {}}
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _save(self, collection: str, data: dict[str, Any]) -> None:
        path = self._path(collection)
        temporary_path = path.with_suffix(".tmp")
        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
        temporary_path.replace(path)

    def upsert_records(
        self,
        collection: str,
        records: list[dict[str, Any]],
        source: str,
        fetched_at: str | None = None,
    ) -> dict[str, int]:
        """Insert new records and classify changed/unchanged records."""
        fetched_at = fetched_at or utc_now_iso()
        data = self._load(collection)
        stored = data["records"]

        added = updated = unchanged = 0

        for record in records:
            record_id = str(record["record_id"])
            payload = dict(record["payload"])
            payload_hash = record_hash(payload)
            existing = stored.get(record_id)

            if existing is None:
                stored[record_id] = asdict(
                    StoredRecord(
                        record_id=record_id,
                        payload=payload,
                        first_seen_at=fetched_at,
                        last_seen_at=fetched_at,
                        source=source,
                        payload_hash=payload_hash,
                    )
                )
                added += 1
            elif existing["payload_hash"] != payload_hash:
                existing["payload"] = payload
                existing["payload_hash"] = payload_hash
                existing["last_seen_at"] = fetched_at
                existing["source"] = source
                updated += 1
            else:
                existing["last_seen_at"] = fetched_at
                unchanged += 1

        self._save(collection, data)
        return {
            "records_added": added,
            "records_updated": updated,
            "records_unchanged": unchanged,
        }

    def get_records(self, collection: str) -> list[StoredRecord]:
        """Return all records in a collection."""
        return [StoredRecord(**r) for r in self._load(collection)["records"].values()]

    def get_record(self, collection: str, record_id: str) -> StoredRecord | None:
        """Return one record by stable ID."""
        record = self._load(collection)["records"].get(str(record_id))
        return StoredRecord(**record) if record else None

    def save_refresh_metadata(self, source: str, metadata: dict[str, Any]) -> None:
        """Persist the latest refresh status for a source."""
        data = self._load("_refresh_metadata")
        data["refresh_metadata"][source] = metadata
        self._save("_refresh_metadata", data)

    def get_refresh_metadata(self, source: str) -> dict[str, Any] | None:
        """Return the latest refresh status for a source."""
        return self._load("_refresh_metadata")["refresh_metadata"].get(source)
