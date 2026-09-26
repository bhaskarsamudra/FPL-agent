"""
Real-data validation tests for historical_team_state.py.

Important design choice:
- The six historical Football-Data CSV files are loaded ONLY ONCE.
- The resulting 2,280-row DataFrame is passed to every test.
- This avoids downloading/loading the same data repeatedly.
- These are direct Python tests, not pytest fixtures.

Run with:

    python test_historical_team_state_real_data.py
"""

from datetime import timedelta

import pandas as pd

from historical_team_data import load_historical_team_matches
from historical_team_state import build_historical_team_state


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# The six complete historical Premier League seasons used by the project.
SEASONS = [
    "2020/21",
    "2021/22",
    "2022/23",
    "2023/24",
    "2024/25",
    "2025/26",
]


# ---------------------------------------------------------------------------
# Shared data loader
# ---------------------------------------------------------------------------

def load_real_historical_data() -> pd.DataFrame:
    """
    Load all six historical seasons once.

    This function is called ONCE by the main test runner.
    The resulting DataFrame is then reused by every test.
    """

    print("Loading six historical seasons once...")

    matches = load_historical_team_matches()

    # Confirm that all expected seasons are present.
    actual_seasons = sorted(matches["season"].unique().tolist())
    expected_seasons = sorted(SEASONS)

    assert actual_seasons == expected_seasons, (
        f"Unexpected seasons.\n"
        f"Expected: {expected_seasons}\n"
        f"Actual:   {actual_seasons}"
    )

    # Six seasons × 380 matches = 2,280 matches.
    assert len(matches) == 2280, (
        f"Expected 2,280 matches, got {len(matches)}"
    )

    print(f"Loaded {len(matches)} historical matches.")
    print()

    return matches


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_season_matches(
    matches: pd.DataFrame,
    season: str,
) -> pd.DataFrame:
    """
    Return only matches belonging to one season.
    """

    season_matches = matches[matches["season"] == season].copy()

    assert len(season_matches) == 380, (
        f"{season} should contain 380 matches, "
        f"but contains {len(season_matches)}"
    )

    return season_matches


def get_mid_season_cutoff(
    matches: pd.DataFrame,
    season: str,
) -> pd.Timestamp:
    """
    Return a cutoff timestamp roughly halfway through a season.

    The cutoff is deliberately placed between actual fixtures so that
    the state builder can be tested using a realistic point-in-time view.
    """

    season_matches = get_season_matches(matches, season)

    sorted_matches = season_matches.sort_values(
        "kickoff_datetime"
    ).reset_index(drop=True)

    middle_index = len(sorted_matches) // 2

    return pd.Timestamp(
        sorted_matches.loc[middle_index, "kickoff_datetime"]
    )


def get_target_match(
    matches: pd.DataFrame,
    season: str,
) -> pd.Series:
    """
    Return a fixture from the middle of a historical season.

    This is used to verify that the target fixture itself is not included
    in the pre-match team state.
    """

    season_matches = get_season_matches(matches, season)

    sorted_matches = season_matches.sort_values(
        "kickoff_datetime"
    ).reset_index(drop=True)

    middle_index = len(sorted_matches) // 2

    return sorted_matches.iloc[middle_index]


# ---------------------------------------------------------------------------
# Test 1
# ---------------------------------------------------------------------------

def test_all_seasons_have_380_matches(matches: pd.DataFrame) -> None:
    """
    Every complete historical Premier League season must contain
    exactly 380 matches.
    """

    for season in SEASONS:
        season_matches = matches[matches["season"] == season]

        assert len(season_matches) == 380, (
            f"{season}: expected 380 matches, "
            f"got {len(season_matches)}"
        )


# ---------------------------------------------------------------------------
# Test 2
# ---------------------------------------------------------------------------

def test_state_required_fields(matches: pd.DataFrame) -> None:
    """
    Verify that the historical team state contains the expected
    core fields.
    """

    season = "2025/26"

    cutoff = get_mid_season_cutoff(matches, season)

    state = build_historical_team_state(
        historical_matches=matches,
        season=season,
        cutoff_datetime=cutoff,
    )

    assert state, "Historical team state should not be empty."

    required_fields = [
        "team_name",
        "season",
        "as_of_datetime",
        "played",
        "wins",
        "draws",
        "losses",
        "points",
        "goals_for",
        "goals_against",
        "home_played",
        "away_played",
        "recent_5_played",
        "goal_difference",
        "points_per_match",
        "goals_per_match",
        "goals_conceded_per_match",
        "recent_5_points_per_match",
        "recent_5_goals_per_match",
        "recent_5_goals_conceded_per_match",
        "rank",
    ]

    for team_name, team_state in state.items():
        for field in required_fields:
            assert field in team_state, (
                f"{team_name}: missing required field '{field}'"
            )


# ---------------------------------------------------------------------------
# Test 3
# ---------------------------------------------------------------------------

def test_overall_results_reconcile(matches: pd.DataFrame) -> None:
    """
    Verify that wins + draws + losses = played
    and that points reconcile with the match results.
    """

    for season in SEASONS:
        cutoff = get_mid_season_cutoff(matches, season)

        state = build_historical_team_state(
            historical_matches=matches,
            season=season,
            cutoff_datetime=cutoff,
        )

        for team_name, team_state in state.items():

            played = team_state["played"]
            wins = team_state["wins"]
            draws = team_state["draws"]
            losses = team_state["losses"]
            points = team_state["points"]

            assert wins + draws + losses == played, (
                f"{season} {team_name}: "
                f"wins + draws + losses does not equal played"
            )

            expected_points = (wins * 3) + draws

            assert points == expected_points, (
                f"{season} {team_name}: "
                f"expected {expected_points} points, got {points}"
            )


# ---------------------------------------------------------------------------
# Test 4
# ---------------------------------------------------------------------------

def test_home_away_totals_reconcile(matches: pd.DataFrame) -> None:
    """
    Verify that home and away match totals add up to overall totals.
    """

    for season in SEASONS:
        cutoff = get_mid_season_cutoff(matches, season)

        state = build_historical_team_state(
            historical_matches=matches,
            season=season,
            cutoff_datetime=cutoff,
        )

        for team_name, team_state in state.items():

            assert (
                team_state["home_played"]
                + team_state["away_played"]
                == team_state["played"]
            ), (
                f"{season} {team_name}: "
                f"home_played + away_played != played"
            )

            assert (
                team_state["home_goals_for"]
                + team_state["away_goals_for"]
                == team_state["goals_for"]
            ), (
                f"{season} {team_name}: "
                f"home_goals_for + away_goals_for != goals_for"
            )

            assert (
                team_state["home_goals_against"]
                + team_state["away_goals_against"]
                == team_state["goals_against"]
            ), (
                f"{season} {team_name}: "
                f"home_goals_against + away_goals_against "
                f"!= goals_against"
            )


# ---------------------------------------------------------------------------
# Test 5
# ---------------------------------------------------------------------------

def test_derived_metrics_are_correct(matches: pd.DataFrame) -> None:
    """
    Verify the basic derived metrics calculated by historical_team_state.py.
    """

    for season in SEASONS:
        cutoff = get_mid_season_cutoff(matches, season)

        state = build_historical_team_state(
            historical_matches=matches,
            season=season,
            cutoff_datetime=cutoff,
        )

        for team_name, team_state in state.items():

            played = team_state["played"]

            if played > 0:

                expected_goal_difference = (
                    team_state["goals_for"]
                    - team_state["goals_against"]
                )

                expected_points_per_match = (
                    team_state["points"] / played
                )

                expected_goals_per_match = (
                    team_state["goals_for"] / played
                )

                expected_goals_conceded_per_match = (
                    team_state["goals_against"] / played
                )

                assert (
                    team_state["goal_difference"]
                    == expected_goal_difference
                )

                assert abs(
                    team_state["points_per_match"]
                    - expected_points_per_match
                ) < 1e-9

                assert abs(
                    team_state["goals_per_match"]
                    - expected_goals_per_match
                ) < 1e-9

                assert abs(
                    team_state["goals_conceded_per_match"]
                    - expected_goals_conceded_per_match
                ) < 1e-9


# ---------------------------------------------------------------------------
# Test 6
# ---------------------------------------------------------------------------

def test_recent_five_never_exceeds_five(matches: pd.DataFrame) -> None:
    """
    Recent-form statistics must never contain more than five matches.
    """

    for season in SEASONS:
        cutoff = get_mid_season_cutoff(matches, season)

        state = build_historical_team_state(
            historical_matches=matches,
            season=season,
            cutoff_datetime=cutoff,
        )

        for team_name, team_state in state.items():

            assert 0 <= team_state["recent_5_played"] <= 5, (
                f"{season} {team_name}: "
                f"invalid recent_5_played value"
            )

            assert (
                team_state["recent_5_wins"]
                + team_state["recent_5_draws"]
                + team_state["recent_5_losses"]
                == team_state["recent_5_played"]
            ), (
                f"{season} {team_name}: "
                f"recent five results do not reconcile"
            )


# ---------------------------------------------------------------------------
# Test 7
# ---------------------------------------------------------------------------

def test_recent_five_derived_metrics_are_correct(
    matches: pd.DataFrame,
) -> None:
    """
    Verify that recent-five derived metrics are calculated correctly.
    """

    for season in SEASONS:
        cutoff = get_mid_season_cutoff(matches, season)

        state = build_historical_team_state(
            historical_matches=matches,
            season=season,
            cutoff_datetime=cutoff,
        )

        for team_name, team_state in state.items():

            recent_played = team_state["recent_5_played"]

            if recent_played > 0:

                expected_points_per_match = (
                    team_state["recent_5_points"]
                    / recent_played
                )

                expected_goals_per_match = (
                    team_state["recent_5_goals_for"]
                    / recent_played
                )

                expected_goals_conceded_per_match = (
                    team_state["recent_5_goals_against"]
                    / recent_played
                )

                assert abs(
                    team_state["recent_5_points_per_match"]
                    - expected_points_per_match
                ) < 1e-9

                assert abs(
                    team_state["recent_5_goals_per_match"]
                    - expected_goals_per_match
                ) < 1e-9

                assert abs(
                    team_state["recent_5_goals_conceded_per_match"]
                    - expected_goals_conceded_per_match
                ) < 1e-9


# ---------------------------------------------------------------------------
# Test 8
# ---------------------------------------------------------------------------

def test_state_contains_only_requested_season(
    matches: pd.DataFrame,
) -> None:
    """
    Verify that requesting one season never accidentally incorporates
    matches from another season.
    """

    season = "2024/25"

    cutoff = get_mid_season_cutoff(matches, season)

    state = build_historical_team_state(
        historical_matches=matches,
        season=season,
        cutoff_datetime=cutoff,
    )

    for team_name, team_state in state.items():
        assert team_state["season"] == season, (
            f"{team_name}: state contains incorrect season "
            f"{team_state['season']}"
        )


# ---------------------------------------------------------------------------
# Test 9
# ---------------------------------------------------------------------------

def test_cutoff_is_preserved(matches: pd.DataFrame) -> None:
    """
    Verify that the exact cutoff timestamp is stored in every team state.
    """

    season = "2023/24"

    cutoff = get_mid_season_cutoff(matches, season)

    state = build_historical_team_state(
        historical_matches=matches,
        season=season,
        cutoff_datetime=cutoff,
    )

    for team_name, team_state in state.items():
        assert pd.Timestamp(team_state["as_of_datetime"]) == cutoff, (
            f"{team_name}: cutoff timestamp was not preserved"
        )


# ---------------------------------------------------------------------------
# Test 10
# ---------------------------------------------------------------------------

def test_target_match_is_excluded(matches: pd.DataFrame) -> None:
    """
    Verify the critical anti-lookahead rule:

    A match occurring exactly at the cutoff timestamp must NOT be
    included in the team state.
    """

    season = "2022/23"

    target_match = get_target_match(matches, season)

    cutoff = pd.Timestamp(target_match["kickoff_datetime"])

    state = build_historical_team_state(
        historical_matches=matches,
        season=season,
        cutoff_datetime=cutoff,
    )

    home_team = target_match["home_team"]
    away_team = target_match["away_team"]

    home_state = state[home_team]
    away_state = state[away_team]

    # Count matches strictly before the target kickoff.
    eligible_matches = matches[
        (matches["season"] == season)
        & (matches["kickoff_datetime"] < cutoff)
    ]

    expected_home_played = (
        (
            eligible_matches["home_team"] == home_team
        ).sum()
        + (
            eligible_matches["away_team"] == home_team
        ).sum()
    )

    expected_away_played = (
        (
            eligible_matches["home_team"] == away_team
        ).sum()
        + (
            eligible_matches["away_team"] == away_team
        ).sum()
    )

    assert home_state["played"] == expected_home_played, (
        f"{home_team}: target match appears to have been included"
    )

    assert away_state["played"] == expected_away_played, (
        f"{away_team}: target match appears to have been included"
    )


# ---------------------------------------------------------------------------
# Test 11
# ---------------------------------------------------------------------------

def test_future_matches_do_not_change_earlier_state(
    matches: pd.DataFrame,
) -> None:
    """
    Verify that adding a future match to the dataset cannot change
    a historical state calculated before that match.

    A synthetic future match is appended to the DataFrame. The state
    before the original cutoff must remain identical.
    """

    season = "2021/22"

    target_match = get_target_match(matches, season)

    cutoff = pd.Timestamp(target_match["kickoff_datetime"])

    original_state = build_historical_team_state(
        historical_matches=matches,
        season=season,
        cutoff_datetime=cutoff,
    )

    # Create a copy of an existing match but move it into the future.
    future_match = target_match.copy()

    future_match["match_id"] = "SYNTHETIC_FUTURE_MATCH"

    future_match["kickoff_datetime"] = (
        cutoff + timedelta(days=30)
    )

    # Append the synthetic future match.
    expanded_matches = pd.concat(
        [
            matches,
            pd.DataFrame([future_match]),
        ],
        ignore_index=True,
    )

    expanded_state = build_historical_team_state(
        historical_matches=expanded_matches,
        season=season,
        cutoff_datetime=cutoff,
    )

    assert original_state == expanded_state, (
        "Adding a future match changed the historical state. "
        "This indicates possible lookahead leakage."
    )


# ---------------------------------------------------------------------------
# Test 12
# ---------------------------------------------------------------------------

def test_league_ranks_are_unique(matches: pd.DataFrame) -> None:
    """
    Verify that every team with a rank has a unique rank value.
    """

    for season in SEASONS:
        cutoff = get_mid_season_cutoff(matches, season)

        state = build_historical_team_state(
            historical_matches=matches,
            season=season,
            cutoff_datetime=cutoff,
        )

        ranks = [
            team_state["rank"]
            for team_state in state.values()
            if team_state["rank"] is not None
        ]

        assert len(ranks) == len(set(ranks)), (
            f"{season}: duplicate league ranks detected"
        )


# ---------------------------------------------------------------------------
# Test 13
# ---------------------------------------------------------------------------

def test_no_negative_cumulative_values(
    matches: pd.DataFrame,
) -> None:
    """
    Cumulative match counts, results and goals must never be negative.
    """

    non_negative_fields = [
        "played",
        "wins",
        "draws",
        "losses",
        "points",
        "goals_for",
        "goals_against",
        "home_played",
        "home_wins",
        "home_draws",
        "home_losses",
        "home_points",
        "home_goals_for",
        "home_goals_against",
        "away_played",
        "away_wins",
        "away_draws",
        "away_losses",
        "away_points",
        "away_goals_for",
        "away_goals_against",
        "recent_5_played",
        "recent_5_wins",
        "recent_5_draws",
        "recent_5_losses",
        "recent_5_points",
        "recent_5_goals_for",
        "recent_5_goals_against",
    ]

    for season in SEASONS:
        cutoff = get_mid_season_cutoff(matches, season)

        state = build_historical_team_state(
            historical_matches=matches,
            season=season,
            cutoff_datetime=cutoff,
        )

        for team_name, team_state in state.items():

            for field in non_negative_fields:
                value = team_state[field]

                assert value >= 0, (
                    f"{season} {team_name}: "
                    f"{field} is negative: {value}"
                )


# ---------------------------------------------------------------------------
# Test 14
# ---------------------------------------------------------------------------

def test_all_six_seasons_can_build_state(
    matches: pd.DataFrame,
) -> None:
    """
    Verify that historical team state can be successfully generated
    for every one of the six historical seasons.
    """

    for season in SEASONS:

        cutoff = get_mid_season_cutoff(matches, season)

        state = build_historical_team_state(
            historical_matches=matches,
            season=season,
            cutoff_datetime=cutoff,
        )

        assert state, (
            f"{season}: historical team state is empty"
        )

        # A Premier League season should contain 20 teams.
        assert len(state) == 20, (
            f"{season}: expected 20 teams, got {len(state)}"
        )


# ---------------------------------------------------------------------------
# Main test runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    # -----------------------------------------------------------------------
    # IMPORTANT:
    # Load the six historical CSV files exactly ONCE.
    # Every test below receives this same DataFrame.
    # -----------------------------------------------------------------------

    matches = load_real_historical_data()

    print("Running real-data historical team state tests...")
    print()

    test_all_seasons_have_380_matches(matches)
    print("PASS: all seasons have 380 matches")

    test_state_required_fields(matches)
    print("PASS: state required fields")

    test_overall_results_reconcile(matches)
    print("PASS: overall results reconcile")

    test_home_away_totals_reconcile(matches)
    print("PASS: home/away totals reconcile")

    test_derived_metrics_are_correct(matches)
    print("PASS: derived metrics are correct")

    test_recent_five_never_exceeds_five(matches)
    print("PASS: recent five never exceeds five")

    test_recent_five_derived_metrics_are_correct(matches)
    print("PASS: recent five derived metrics")

    test_state_contains_only_requested_season(matches)
    print("PASS: state contains only requested season")

    test_cutoff_is_preserved(matches)
    print("PASS: cutoff is preserved")

    test_target_match_is_excluded(matches)
    print("PASS: target match is excluded")

    test_future_matches_do_not_change_earlier_state(matches)
    print("PASS: future matches do not change earlier state")

    test_league_ranks_are_unique(matches)
    print("PASS: league ranks are unique")

    test_no_negative_cumulative_values(matches)
    print("PASS: no negative cumulative values")

    test_all_six_seasons_can_build_state(matches)
    print("PASS: all six seasons can build state")

    print()
    print("All real-data historical team state tests passed.")