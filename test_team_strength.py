"""
test_team_strength.py

This test builds the team-performance layer and then builds the
transparent team-strength layer.

The purpose is to inspect the actual GW1-GW5 data before we decide
how the eventual team-strength model should work.
"""

from fpl_truth import get_bootstrap_data, get_fixtures
from fixture_data import build_fixture_data
from player_data import build_player_universe
from team_data import build_team_performance
from team_strength import build_team_strength


def main() -> None:
    """
    Fetch current FPL data and test the team-strength layer.
    """

    print("Fetching FPL bootstrap data...")
    bootstrap_data = get_bootstrap_data()

    print("Fetching FPL fixtures...")
    fixtures = get_fixtures()

    print("Building player universe...")
    player_universe = build_player_universe(bootstrap_data)

    print("Building fixture data...")
    fixture_data = build_fixture_data(
        fixtures,
        bootstrap_data,
    )

    print("Building team performance...")
    team_performance = build_team_performance(
        fixture_data,
        player_universe,
    )

    print("Building team strength...")
    team_strength = build_team_strength(
        team_performance
    )

    # -------------------------------------------------------------
    # Basic validation
    # -------------------------------------------------------------

    assert len(team_strength) == 20, (
        "Expected 20 Premier League teams."
    )

    for team in team_strength.values():
        assert team["team_id"] is not None
        assert team["team_name"]
        assert team["played"] >= 0

        # Attack ratios should normally be non-negative.
        assert team["observed_attack_ratio"] >= 0
        assert team["underlying_attack_xg_ratio"] >= 0
        assert team["underlying_attack_xgi_ratio"] >= 0

        # Defence ratios should also be non-negative.
        assert team["observed_defence_ratio"] >= 0
        assert team["recent_defence_ratio"] >= 0

    # -------------------------------------------------------------
    # Display results
    # -------------------------------------------------------------

    print()
    print("Number of teams:", len(team_strength))
    print()

    print(
        "Team | "
        "P | "
        "ObsAtk | "
        "xG Atk | "
        "xGI Atk | "
        "RecentAtk | "
        "ObsDef | "
        "RecentDef | "
        "HomeAtk | "
        "AwayAtk | "
        "HomeDef | "
        "AwayDef"
    )

    print("-" * 150)

    for team in team_strength.values():
        print(
            f"{team['team_name']} | "
            f"{team['played']} | "
            f"{team['observed_attack_ratio']:.2f} | "
            f"{team['underlying_attack_xg_ratio']:.2f} | "
            f"{team['underlying_attack_xgi_ratio']:.2f} | "
            f"{team['recent_attack_ratio']:.2f} | "
            f"{team['observed_defence_ratio']:.2f} | "
            f"{team['recent_defence_ratio']:.2f} | "
            f"{team['home_attack_ratio']:.2f} | "
            f"{team['away_attack_ratio']:.2f} | "
            f"{team['home_defence_ratio']:.2f} | "
            f"{team['away_defence_ratio']:.2f}"
        )

    print()
    print("All team_strength tests passed.")

    # Run the test when this file is executed directly.
if __name__ == "__main__":
    main()

    