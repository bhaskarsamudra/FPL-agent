"""
test_team_data.py

Tests the team_data module using live FPL data.

This test checks both:

1. Team results/performance
2. Player-level underlying attacking metrics
"""

from fpl_truth import get_bootstrap_data, get_fixtures
from fixture_data import build_fixture_data
from player_data import build_player_universe
from team_data import build_team_performance


# ---------------------------------------------------------
# STEP 1: DOWNLOAD FPL DATA
# ---------------------------------------------------------

print("Fetching FPL bootstrap data...")

bootstrap_data = get_bootstrap_data()

print("Fetching FPL fixtures...")

fixtures = get_fixtures()


# ---------------------------------------------------------
# STEP 2: BUILD STRUCTURED DATA
# ---------------------------------------------------------

print("Building player universe...")

player_universe = build_player_universe(bootstrap_data)

print("Building structured fixture data...")

structured_fixtures = build_fixture_data(
    fixtures,
    bootstrap_data
)


# ---------------------------------------------------------
# STEP 3: BUILD TEAM PERFORMANCE
# ---------------------------------------------------------

print("Building team performance...")

team_performance = build_team_performance(
    structured_fixtures,
    player_universe
)


# ---------------------------------------------------------
# STEP 4: BASIC VALIDATION
# ---------------------------------------------------------

print()
print("Number of teams:", len(team_performance))

assert len(team_performance) == 20, (
    "Expected 20 teams."
)


# ---------------------------------------------------------
# STEP 5: DISPLAY RESULTS
# ---------------------------------------------------------

print()
print(
    "Rank | Team | P | W | D | L | "
    "Pts | GF | GA | GD | PPG | "
    "xG | xA | xGI | xG/90"
)

print("-" * 120)


for team in team_performance.values():

    print(
        f"{team['rank']:>4} | "
        f"{team['team_name']:<16} | "
        f"{team['played']:>1} | "
        f"{team['wins']:>1} | "
        f"{team['draws']:>1} | "
        f"{team['losses']:>1} | "
        f"{team['points']:>3} | "
        f"{team['goals_for']:>2} | "
        f"{team['goals_against']:>2} | "
        f"{team['goal_difference']:>3} | "
        f"{team['points_per_match']:.2f} | "
        f"{team['underlying_xg']:.2f} | "
        f"{team['underlying_xa']:.2f} | "
        f"{team['underlying_xgi']:.2f} | "
        f"{team['underlying_xg_per_90']:.2f}"
    )


# ---------------------------------------------------------
# STEP 6: BASIC UNDERLYING-DATA CHECKS
# ---------------------------------------------------------

print()
print("Running validation checks...")

for team in team_performance.values():

    # Every team should have at least one player in the
    # FPL player universe.
    assert team["underlying_players_count"] > 0

    # Underlying metrics should never be negative.
    assert team["underlying_xg"] >= 0
    assert team["underlying_xa"] >= 0
    assert team["underlying_xgi"] >= 0

    # Minutes cannot be negative.
    assert team["underlying_minutes"] >= 0


print("All team_data tests passed.")