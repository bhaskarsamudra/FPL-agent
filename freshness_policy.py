"""
Dataset freshness policies.

A freshness policy answers:
    "Is stored data fresh enough for this operation?"

It does not perform API calls and does not contain FPL scoring rules.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FreshnessPolicy:
    """Refresh policy for one dataset."""

    dataset: str
    ttl_minutes: int
    near_deadline_ttl_minutes: int
    immutable: bool = False

    def ttl_for_context(self, near_deadline: bool = False) -> int | None:
        if self.immutable:
            return None
        return (
            self.near_deadline_ttl_minutes
            if near_deadline
            else self.ttl_minutes
        )


POLICIES = {
    "bootstrap_static": FreshnessPolicy("bootstrap_static", 360, 60),
    "fixtures": FreshnessPolicy("fixtures", 360, 60),
    "player_summary": FreshnessPolicy("player_summary", 360, 30),
    "manager_state": FreshnessPolicy("manager_state", 360, 30),
    "league_state": FreshnessPolicy("league_state", 360, 30),
    "availability_news": FreshnessPolicy("availability_news", 180, 15),
    "historical_match_data": FreshnessPolicy(
        "historical_match_data", 0, 0, immutable=True
    ),
    "season_rules": FreshnessPolicy(
        "season_rules",
        ttl_minutes=525600,              # approximately one year
        near_deadline_ttl_minutes=525600,
    ),
}


def get_policy(dataset: str) -> FreshnessPolicy:
    """Return the configured policy for a dataset."""
    try:
        return POLICIES[dataset]
    except KeyError as exc:
        raise KeyError(f"No freshness policy configured for '{dataset}'.") from exc


def is_fresh(
    age_minutes: float | None,
    dataset: str,
    near_deadline: bool = False,
) -> bool:
    """Determine whether stored data is fresh enough."""
    if age_minutes is None:
        return False

    policy = get_policy(dataset)

    if policy.immutable:
        return True

    ttl = policy.ttl_for_context(near_deadline)
    return age_minutes <= ttl
