"""
Tests for the FPL fixture model.

This test connects the existing pipeline:

FPL API
   ↓
fixture_data.py
   ↓
team_data.py
   ↓
team_strength.py
   ↓
fixture_model.py

The purpose is to verify that the fixture model works with the
real current FPL data and produces transparent matchup records.
"""


from fixture_data import build_fixture_data
from fpl_truth import (
    get_bootstrap_data,
    get_fixtures,
)
from team_data import build_team_performance
from team_strength import build_team_strength
from fixture_model import build_fixture_model


def main():
    """
    Run the fixture-model validation.
    """

    # ------------------------------------------------------------
    # STEP 1:
    # Fetch the official FPL bootstrap data.
    # ------------------------------------------------------------

    bootstrap_data = get_bootstrap_data()

    # ------------------------------------------------------------
    # STEP 2:
    # Fetch the official FPL fixture data.
    # ------------------------------------------------------------

    fixtures = get_fixtures()

    # ------------------------------------------------------------
    # STEP 3:
    # Convert raw fixtures into our structured format.
    # ------------------------------------------------------------

    structured_fixtures = build_fixture_data(
        fixtures,
        bootstrap_data,
    )

    print(
        f"Structured fixtures: {len(structured_fixtures)}"
    )

    # ------------------------------------------------------------
    # STEP 4:
    # Build team-performance measurements.
    #
    # IMPORTANT:
    # team_data.py makes player_universe optional.
    #
    # For this fixture-model checkpoint we only need the
    # completed-match results, so we deliberately do not pass
    # player_universe yet.
    # ------------------------------------------------------------

    team_performance = build_team_performance(
        structured_fixtures
    )

    print(
        f"Teams with performance data: "
        f"{len(team_performance)}"
    )

    # ------------------------------------------------------------
    # STEP 5:
    # Convert team performance into transparent strength
    # indicators.
    # ------------------------------------------------------------

    team_strength = build_team_strength(
        team_performance
    )

    print(
        f"Teams with strength data: "
        f"{len(team_strength)}"
    )

    # ------------------------------------------------------------
    # STEP 6:
    # Build the fixture model.
    #
    # Only unfinished/upcoming fixtures are included.
    # ------------------------------------------------------------

    fixture_model = build_fixture_model(
        structured_fixtures,
        team_strength,
    )

    print(
        f"Upcoming fixture-model records: "
        f"{len(fixture_model)}"
    )

    # ------------------------------------------------------------
    # STEP 7:
    # Basic validation.
    # ------------------------------------------------------------

    assert len(fixture_model) > 0, (
        "Fixture model returned no upcoming fixtures."
    )

    # ------------------------------------------------------------
    # STEP 8:
    # Inspect the first five fixtures.
    #
    # We print the transparent components so we can manually
    # inspect whether the model is behaving sensibly.
    # ------------------------------------------------------------

    print("\nSample fixture-model output:\n")

    for record in fixture_model[:5]:

        print(
            f"GW{record['gameweek']} | "
            f"{record['home_team']} vs "
            f"{record['away_team']}"
        )

        print(
            "  Official FPL difficulty: "
            f"Home={record['official_fpl_home_difficulty']} "
            f"Away={record['official_fpl_away_difficulty']}"
        )

        print(
            "  Home attack matchup: "
            f"{record['home_matchup']['observed_attack_matchup']:.3f}"
        )

        print(
            "  Home defence matchup: "
            f"{record['home_matchup']['observed_defence_matchup']:.3f}"
        )

        print(
            "  Away attack matchup: "
            f"{record['away_matchup']['observed_attack_matchup']:.3f}"
        )

        print(
            "  Away defence matchup: "
            f"{record['away_matchup']['observed_defence_matchup']:.3f}"
        )

        print(
            "  Sample size: "
            f"Home={record['home_team_sample_size']} "
            f"Away={record['away_team_sample_size']}"
        )

        print()

    print(
        "Fixture model validation passed."
    )


if __name__ == "__main__":
    main()