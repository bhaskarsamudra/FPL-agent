"""
Rules Engine interface for the FPL Strategist.

IMPORTANT:
    This module no longer treats season-specific rule values as the ultimate
    source of truth. Official rules are stored as versioned data by the rules
    ingestion layer.

The FALLBACK_2026_27_RULES object is a deterministic bootstrap fallback for
local development/tests. Production startup should install authoritative
rules before live recommendations are enabled.
"""

from dataclasses import dataclass
from typing import Literal

Position = Literal["GK", "DEF", "MID", "FWD"]


@dataclass(frozen=True)
class FPLRules:
    """Typed rule values consumed by deterministic strategy modules."""

    season: str
    squad_size: int
    max_players_per_club: int
    position_limits: dict[str, int]
    starting_xi_size: int
    min_defenders: int
    min_midfielders: int
    min_forwards: int
    starting_budget_millions: float
    max_free_transfers: int
    extra_transfer_cost: int
    chip_sets: int
    max_chips_per_gameweek: int
    first_half_last_gameweek: int
    second_half_first_gameweek: int
    captain_multiplier: int
    triple_captain_multiplier: int
    appearance_0_to_59: int
    appearance_60_plus: int
    goalkeeper_goal: int
    defender_goal: int
    midfielder_goal: int
    forward_goal: int
    assist: int
    goalkeeper_clean_sheet: int
    defender_clean_sheet: int
    midfielder_clean_sheet: int
    forward_clean_sheet: int
    goalkeeper_save_every: int
    goalkeeper_save_points: int
    penalty_save: int
    penalty_miss: int
    yellow_card: int
    red_card: int
    own_goal: int
    goals_conceded_every: int
    goals_conceded_points: int
    bonus_points: tuple[int, int, int]
    defender_dc_threshold: int
    midfielder_dc_threshold: int
    forward_dc_threshold: int
    defensive_contribution_points: int


FALLBACK_2026_27_RULES = FPLRules(
    season="2026/27",
    squad_size=15,
    max_players_per_club=3,
    position_limits={"GK": 2, "DEF": 5, "MID": 5, "FWD": 3},
    starting_xi_size=11,
    min_defenders=3,
    min_midfielders=2,
    min_forwards=1,
    starting_budget_millions=100.0,
    max_free_transfers=5,
    extra_transfer_cost=4,
    chip_sets=2,
    max_chips_per_gameweek=1,
    first_half_last_gameweek=19,
    second_half_first_gameweek=20,
    captain_multiplier=2,
    triple_captain_multiplier=3,
    appearance_0_to_59=1,
    appearance_60_plus=2,
    goalkeeper_goal=10,
    defender_goal=6,
    midfielder_goal=5,
    forward_goal=4,
    assist=3,
    goalkeeper_clean_sheet=4,
    defender_clean_sheet=4,
    midfielder_clean_sheet=1,
    forward_clean_sheet=0,
    goalkeeper_save_every=3,
    goalkeeper_save_points=1,
    penalty_save=5,
    penalty_miss=-2,
    yellow_card=-1,
    red_card=-3,
    own_goal=-2,
    goals_conceded_every=2,
    goals_conceded_points=-1,
    bonus_points=(3, 2, 1),
    defender_dc_threshold=10,
    midfielder_dc_threshold=12,
    forward_dc_threshold=12,
    defensive_contribution_points=2,
)


class RulesUnavailableError(RuntimeError):
    """Raised when live rules are required but no authoritative rules exist."""


class RulesEngine:
    """
    Provide typed access to the active rules.

    The fallback is permitted for development/tests only. A production caller
    should require an authoritative stored version before enabling strategy.
    """

    def __init__(
        self,
        rules: FPLRules = FALLBACK_2026_27_RULES,
        authoritative: bool = False,
    ) -> None:
        self._rules = rules
        self.authoritative = authoritative

    @property
    def rules(self) -> FPLRules:
        """Return the currently active typed rules."""
        return self._rules

    def require_authoritative(self) -> FPLRules:
        """Return rules only when they came from the authoritative source."""
        if not self.authoritative:
            raise RulesUnavailableError(
                "Authoritative FPL rules have not been installed for this season."
            )
        return self._rules

    def goal_points(self, position: Position) -> int:
        values = {
            "GK": self._rules.goalkeeper_goal,
            "DEF": self._rules.defender_goal,
            "MID": self._rules.midfielder_goal,
            "FWD": self._rules.forward_goal,
        }
        if position not in values:
            raise ValueError(f"Unknown FPL position: {position}")
        return values[position]

    def clean_sheet_points(self, position: Position) -> int:
        values = {
            "GK": self._rules.goalkeeper_clean_sheet,
            "DEF": self._rules.defender_clean_sheet,
            "MID": self._rules.midfielder_clean_sheet,
            "FWD": self._rules.forward_clean_sheet,
        }
        if position not in values:
            raise ValueError(f"Unknown FPL position: {position}")
        return values[position]

    def defensive_contribution_threshold(self, position: Position) -> int | None:
        values = {
            "GK": None,
            "DEF": self._rules.defender_dc_threshold,
            "MID": self._rules.midfielder_dc_threshold,
            "FWD": self._rules.forward_dc_threshold,
        }
        if position not in values:
            raise ValueError(f"Unknown FPL position: {position}")
        return values[position]

    def transfer_hit(self, transfers_used: int, free_transfers_available: int) -> int:
        if transfers_used < 0 or free_transfers_available < 0:
            raise ValueError("Transfer counts cannot be negative.")
        extra = max(0, transfers_used - free_transfers_available)
        return -extra * self._rules.extra_transfer_cost

    def captain_multiplier(self, chip: str | None = None) -> int:
        if chip is None:
            return self._rules.captain_multiplier
        if chip == "triple_captain":
            return self._rules.triple_captain_multiplier
        raise ValueError(f"Unsupported captain chip: {chip}")
