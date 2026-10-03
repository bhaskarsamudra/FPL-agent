"""
Validation tests for the internal fixture model.

This test verifies that:

1. Upcoming fixtures are returned.
2. Every fixture has both home and away matchup records.
3. Matchup values are finite numbers.
4. Sample sizes are present and valid.
5. Small-sample warnings are present.
6. Underlying xG/xGI fields are available.
7. Relative underlying xG/xGI matchup fields are available.
8. Official FPL difficulty is preserved.
9. The model does not produce NaN or infinite values.
"""

import math

from fixture_data import build_fixture_data
from fixture_model import build_fixture_model
from fpl_truth import get_bootstrap_data, get_fixtures
from team_data import build_team_performance
from team_strength import build_team_strength


def assert_finite(value, field_name):
    """
    Confirm that a value is a finite number.

    This catches both NaN and positive/negative infinity.
    """

    assert isinstance(value, (int, float)), (
        f"{field_name} must be numeric, "
        f"got {type(value).__name__}"
    )

    assert math.isfinite(value), (
        f"{field_name} must be finite, got {value}"
    )


# ------------------------------------------------------------
# 1. Load verified FPL data
# ------------------------------------------------------------

bootstrap_data = get_bootstrap_data()
fixtures = get_fixtures()

print(f"Raw fixtures: {len(fixtures)}")


# ------------------------------------------------------------
# 2. Build the structured fixture layer
# ------------------------------------------------------------

structured_fixtures = build_fixture_data(
    fixtures,
    bootstrap_data,
)

print(f"Structured fixtures: {len(structured_fixtures)}")


# ------------------------------------------------------------
# 3. Build team performance and team strength
# ------------------------------------------------------------

team_performance = build_team_performance(
    structured_fixtures
)

team_strength = build_team_strength(
    team_performance
)

print(
    f"Teams with performance data: "
    f"{len(team_performance)}"
)

print(
    f"Teams with strength data: "
    f"{len(team_strength)}"
)


# ------------------------------------------------------------
# 4. Build the internal fixture model
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
# 5. Basic validation
# ------------------------------------------------------------

assert fixture_model, (
    "Fixture model should contain upcoming fixtures."
)


# ------------------------------------------------------------
# 6. Validate every fixture
# ------------------------------------------------------------

for fixture in fixture_model:

    # --------------------------------------------------------
    # Basic fixture identity
    # --------------------------------------------------------

    assert fixture["fixture_id"] is not None
    assert fixture["gameweek"] is not None

    assert fixture["home_team_id"] is not None
    assert fixture["away_team_id"] is not None

    assert fixture["home_team_id"] != fixture["away_team_id"]


    # --------------------------------------------------------
    # Both matchup records must exist
    # --------------------------------------------------------

    home_matchup = fixture["home_matchup"]
    away_matchup = fixture["away_matchup"]

    assert isinstance(home_matchup, dict)
    assert isinstance(away_matchup, dict)


    # --------------------------------------------------------
    # Required matchup fields
    #
    # These names must match the actual fixture_model.py
    # contract.
    # --------------------------------------------------------

    required_matchup_fields = [
        "observed_attack_matchup",
        "observed_defence_matchup",
        "underlying_xg_attack_strength",
        "underlying_xgi_attack_strength",
        "relative_xg_attack_matchup",
        "relative_xgi_attack_matchup",
    ]

    for field in required_matchup_fields:

        assert field in home_matchup, (
            f"Missing home matchup field: {field}"
        )

        assert field in away_matchup, (
            f"Missing away matchup field: {field}"
        )


    # --------------------------------------------------------
    # Matchup values must be finite
    # --------------------------------------------------------

    numeric_matchup_fields = [
        "observed_attack_matchup",
        "observed_defence_matchup",
        "underlying_xg_attack_strength",
        "underlying_xgi_attack_strength",
        "relative_xg_attack_matchup",
        "relative_xgi_attack_matchup",
    ]

    for field in numeric_matchup_fields:

        assert_finite(
            home_matchup[field],
            f"home_matchup.{field}",
        )

        assert_finite(
            away_matchup[field],
            f"away_matchup.{field}",
        )


    # --------------------------------------------------------
    # Sample sizes must be valid
    #
    # Sample size is stored at fixture level in the current
    # fixture-model contract.
    # --------------------------------------------------------

    assert isinstance(
        fixture["home_team_sample_size"],
        int,
    )

    assert isinstance(
        fixture["away_team_sample_size"],
        int,
    )

    assert fixture["home_team_sample_size"] >= 0
    assert fixture["away_team_sample_size"] >= 0


    # --------------------------------------------------------
    # Small-sample warning must be boolean
    # --------------------------------------------------------

    assert isinstance(
        fixture["small_sample_warning"],
        bool,
    )


    # --------------------------------------------------------
    # Official FPL difficulty must be preserved
    #
    # These values are retained as a benchmark/reference.
    # They are NOT used by the internal fixture calculations.
    # --------------------------------------------------------

    assert (
        fixture["official_fpl_home_difficulty"]
        is not None
    )

    assert (
        fixture["official_fpl_away_difficulty"]
        is not None
    )

    assert isinstance(
        fixture["official_fpl_home_difficulty"],
        int,
    )

    assert isinstance(
        fixture["official_fpl_away_difficulty"],
        int,
    )


# ------------------------------------------------------------
# 7. Print a small sample for manual inspection
# ------------------------------------------------------------

print("\nSample fixture-model output:\n")

for fixture in fixture_model[:5]:

    home = fixture["home_matchup"]
    away = fixture["away_matchup"]

    print(
        f"GW{fixture['gameweek']} | "
        f"{fixture['home_team']} vs "
        f"{fixture['away_team']}"
    )

    print(
        "  Official FPL difficulty: "
        f"Home={fixture['official_fpl_home_difficulty']} "
        f"Away={fixture['official_fpl_away_difficulty']}"
    )

    print(
        "  Home attack matchup: "
        f"{home['observed_attack_matchup']:.3f}"
    )

    print(
        "  Home defence matchup: "
        f"{home['observed_defence_matchup']:.3f}"
    )

    print(
        "  Away attack matchup: "
        f"{away['observed_attack_matchup']:.3f}"
    )

    print(
        "  Away defence matchup: "
        f"{away['observed_defence_matchup']:.3f}"
    )

    print(
        "  Underlying xG attack strength: "
        f"Home={home['underlying_xg_attack_strength']:.3f} "
        f"Away={away['underlying_xg_attack_strength']:.3f}"
    )

    print(
        "  Underlying xGI attack strength: "
        f"Home={home['underlying_xgi_attack_strength']:.3f} "
        f"Away={away['underlying_xgi_attack_strength']:.3f}"
    )

    print(
        "  Relative xG attack matchup: "
        f"Home={home['relative_xg_attack_matchup']:.3f} "
        f"Away={away['relative_xg_attack_matchup']:.3f}"
    )

    print(
        "  Relative xGI attack matchup: "
        f"Home={home['relative_xgi_attack_matchup']:.3f} "
        f"Away={away['relative_xgi_attack_matchup']:.3f}"
    )

    print(
        "  Sample size: "
        f"Home={fixture['home_team_sample_size']} "
        f"Away={fixture['away_team_sample_size']}"
    )

    print(
        "  Small-sample warning: "
        f"{fixture['small_sample_warning']}"
    )

    print()


print("Fixture model validation passed.")