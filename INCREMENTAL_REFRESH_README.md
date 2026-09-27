# Incremental Refresh Layer — V1

This batch introduces the first concrete implementation of the
"refresh once, analyse many times" architecture.

## Files

- `data_store.py` — persistent local JSON store with change detection.
- `fpl_data_source.py` — standard-library FPL API adapter.
- `refresh_manager.py` — global and user-specific refresh orchestration.
- `test_data_store.py` — persistence/change-detection tests.
- `test_refresh_manager.py` — refresh orchestration tests.

## Current behaviour

Global data:
- FPL `bootstrap-static/`
- FPL `fixtures/`

User-specific data:
- manager picks for a selected gameweek
- manager season history

Stable IDs and payload hashes classify records as added, updated or unchanged.

## Deliberate V1 limitations

This is not yet the final cloud data layer.

Next steps:
1. Add source-specific freshness windows.
2. Add dependency-aware player `element-summary` refreshes.
3. Add news/injury source adapters.
4. Add immutable observation/history tables where required.
5. Add data-quality and NO-DATA gates.
6. Replace local JSON with the selected free cloud store.
7. Add authentication and strict multi-user isolation.

The Strategy Engine should not bypass this layer to call the FPL API directly.
