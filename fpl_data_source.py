"""FPL API source adapter. It retrieves data but makes no strategy decisions."""

from __future__ import annotations
import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from typing import Any

FPL_BASE_URL = "https://fantasy.premierleague.com/api"


@dataclass(frozen=True)
class FPLFetchResult:
    """Result metadata for one FPL endpoint request."""
    endpoint: str
    fetched_at: str
    payload: dict[str, Any]


class FPLAPIError(RuntimeError):
    """Raised when an FPL API request fails or returns invalid data."""


class FPLDataSource:
    """Small standard-library FPL API client."""

    def __init__(self, base_url: str = FPL_BASE_URL, timeout_seconds: int = 15) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _fetch_payload(self, endpoint: str) -> Any:
        """Fetch and parse one JSON endpoint without assuming its top-level type."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        request = Request(url, headers={"User-Agent": "FPL-Strategist/1.0"})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise FPLAPIError(f"FPL API request failed: {url}") from exc

    def fetch_json(self, endpoint: str) -> dict[str, Any]:
        """Fetch and parse a dictionary-shaped JSON endpoint."""
        payload = self._fetch_payload(endpoint)
        if not isinstance(payload, dict):
            raise FPLAPIError(
                f"Unexpected non-object FPL payload: {self.base_url}/{endpoint.lstrip('/')}"
            )
        return payload

    def fetch_bootstrap_static(self) -> dict[str, Any]:
        """Fetch player, team, gameweek and related global FPL data."""
        return self.fetch_json("bootstrap-static/")

    def fetch_fixtures(self) -> list[dict[str, Any]]:
        """Fetch the current FPL fixture dataset."""
        payload = self.fetch_json("fixtures/")
        if not isinstance(payload, list):
            raise FPLAPIError("FPL fixtures endpoint returned a non-list payload.")
        return payload

    def fetch_manager_entry(self, manager_id: int) -> dict[str, Any]:
        """Fetch one manager's official entry profile."""
        return self.fetch_json(f"entry/{manager_id}/")

    def fetch_manager_picks(self, manager_id: int, gameweek: int) -> dict[str, Any]:
        """Fetch a manager's picks and GW history."""
        return self.fetch_json(f"entry/{manager_id}/event/{gameweek}/picks/")

    def fetch_manager_transfers(self, manager_id: int) -> dict[str, Any]:
        """Fetch one manager's official transfer history."""
        payload = self._fetch_payload(f"entry/{manager_id}/transfers/")
        if not isinstance(payload, list):
            raise FPLAPIError("FPL transfers endpoint returned a non-list payload.")
        return {"transfers": payload}

    def fetch_manager_history(self, manager_id: int) -> dict[str, Any]:
        """Fetch a manager's season history and chips."""
        return self.fetch_json(f"entry/{manager_id}/history/")

    def fetch_classic_league_standings(
        self,
        league_id: int,
        page: int = 1,
        event: int | None = None,
    ) -> dict[str, Any]:
        """Fetch one page of a classic league standings endpoint.

        ``event`` is optional so existing callers continue to retrieve the
        latest standings. When supplied, the FPL API returns standings for
        that Gameweek snapshot.
        """
        endpoint = (
            f"leagues-classic/{league_id}/standings/?page_standings={page}"
        )
        if event is not None:
            endpoint += f"&event={event}"
        return self.fetch_json(endpoint)

    def fetch_element_summary(self, player_id: int) -> dict[str, Any]:
        """Fetch one player's history and upcoming fixtures."""
        return self.fetch_json(f"element-summary/{player_id}/")
