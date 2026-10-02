"""Tests for FPL API endpoint adapter contracts."""

from fpl_data_source import FPLDataSource


def test_manager_and_league_endpoints(monkeypatch):
    """Manager and league endpoint paths should map to stable contracts."""
    source = FPLDataSource(base_url="https://example.invalid")
    calls = []

    def fake_fetch_json(endpoint):
        calls.append(endpoint)
        return {"ok": True}

    monkeypatch.setattr(source, "fetch_json", fake_fetch_json)

    assert source.fetch_manager_entry(3325156)["ok"] is True
    assert source.fetch_manager_picks(3325156, 6)["ok"] is True
    assert source.fetch_manager_history(3325156)["ok"] is True
    assert source.fetch_classic_league_standings(987870)["ok"] is True

    assert calls == [
        "entry/3325156/",
        "entry/3325156/event/6/picks/",
        "entry/3325156/history/",
        "leagues-classic/987870/standings/?page_standings=1",
    ]


def test_manager_transfers_accepts_list_payload(monkeypatch):
    """The transfers endpoint returns a list and is wrapped by the adapter."""
    source = FPLDataSource(base_url="https://example.invalid")

    monkeypatch.setattr(
        source,
        "_fetch_payload",
        lambda endpoint: [
            {
                "element_in": 1,
                "element_out": 2,
                "event": 6,
                "entry_cost": -4,
                "time": "2026-09-30T12:00:00Z",
            }
        ],
    )

    result = source.fetch_manager_transfers(3325156)

    assert len(result["transfers"]) == 1
    assert result["transfers"][0]["entry_cost"] == -4
