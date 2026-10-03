"""
test_historical_team_state.py

Tests the point-in-time historical team state builder.

The most important test here is leakage prevention:

    A team's state at a historical cutoff must NOT include
    the match being predicted or any match after it.
"""

from datetime import datetime

import pandas as pd

from historical_team_state import (
    build_historical_team_state,
)


# ============================================================
# TEST DATA
# ============================================================

def create_test_matches() -> pd.DataFrame:
    """
    Create a very small artificial season.

    We deliberately know the correct answer so that we can
    verify the historical state calculations.

    Timeline:

        GW1:
        Arsenal 2 - 0 Chelsea

        GW2:
        Liverpool 1 - 1 Arsenal

        GW3:
        Chelsea 3 - 1 Liverpool

        GW4:
        Arsenal 0 - 2 Liverpool

    We will calculate team state immediately BEFORE GW3.

    Therefore only GW1 and GW2 may be included.

    GW3 and GW4 must NOT influence the result.
    """

    return pd.DataFrame(
        [
            {
                "match_id": 1,
                "season": "2023/24",
                "match_date": "2023-08-12",
                "kickoff_datetime": datetime(
                    2023,
                    8,
                    12,
                    15,
                    0,
                ),
                "home_team": "Arsenal",
                "away_team": "Chelsea",
                "home_goals": 2,
                "away_goals": 0,
            },
            {
                "match_id": 2,
                "season": "2023/24",
                "match_date": "2023-08-19",
                "kickoff_datetime": datetime(
                    2023,
                    8,
                    19,
                    15,
                    0,
                ),
                "home_team": "Liverpool",
                "away_team": "Arsenal",
                "home_goals": 1,
                "away_goals": 1,
            },
            {
                "match_id": 3,
                "season": "2023/24",
                "match_date": "2023-08-26",
                "kickoff_datetime": datetime(
                    2023,
                    8,
                    26,
                    15,
                    0,
                ),
                "home_team": "Chelsea",
                "away_team": "Liverpool",
                "home_goals": 3,
                "away_goals": 1,
            },
            {
                "match_id": 4,
                "season": "2023/24",
                "match_date": "2023-09-02",
                "kickoff_datetime": datetime(
                    2023,
                    9,
                    2,
                    15,
                    0,
                ),
                "home_team": "Arsenal",
                "away_team": "Liverpool",
                "home_goals": 0,
                "away_goals": 2,
            },
        ]
    )


# ============================================================
# BASIC STATE TEST
# ============================================================

def test_point_in_time_state() -> None:
    """
    Verify that only matches before the cutoff are included.

    Cutoff:
        2023-08-26 15:00

    Therefore:

        Match 1 -> included
        Match 2 -> included
        Match 3 -> excluded
        Match 4 -> excluded
    """

    matches = create_test_matches()

    cutoff = datetime(
        2023,
        8,
        26,
        15,
        0,
    )

    state = build_historical_team_state(
        historical_matches=matches,
        season="2023/24",
        cutoff_datetime=cutoff,
    )

    # --------------------------------------------------------
    # Arsenal
    #
    # Match 1:
    #   Arsenal 2-0 Chelsea
    #   Win = 3 points
    #
    # Match 2:
    #   Liverpool 1-1 Arsenal
    #   Draw = 1 point
    #
    # Total:
    #   Played = 2
    #   Wins = 1
    #   Draws = 1
    #   Losses = 0
    #   Points = 4
    #   Goals for = 3
    #   Goals against = 1
    # --------------------------------------------------------

    arsenal = state["Arsenal"]

    assert arsenal["played"] == 2

    assert arsenal["wins"] == 1
    assert arsenal["draws"] == 1
    assert arsenal["losses"] == 0

    assert arsenal["points"] == 4

    assert arsenal["goals_for"] == 3
    assert arsenal["goals_against"] == 1

    assert arsenal["goal_difference"] == 2

    assert arsenal["points_per_match"] == 2.0

    assert arsenal["goals_per_match"] == 1.5

    assert arsenal["goals_conceded_per_match"] == 0.5

    # --------------------------------------------------------
    # Verify point-in-time metadata.
    # --------------------------------------------------------

    assert arsenal["season"] == "2023/24"

    assert arsenal["as_of_datetime"] == pd.Timestamp(
        cutoff
    )

    # --------------------------------------------------------
    # Arsenal home record
    #
    # Match 1 was at home:
    #
    #   Played = 1
    #   Win = 1
    #   Points = 3
    #   Goals = 2
    #   Conceded = 0
    # --------------------------------------------------------

    assert arsenal["home_played"] == 1
    assert arsenal["home_wins"] == 1
    assert arsenal["home_draws"] == 0
    assert arsenal["home_losses"] == 0

    assert arsenal["home_points"] == 3

    assert arsenal["home_goals_for"] == 2
    assert arsenal["home_goals_against"] == 0

    # --------------------------------------------------------
    # Arsenal away record
    #
    # Match 2 was away:
    #
    #   Played = 1
    #   Draw = 1
    #   Points = 1
    #   Goals = 1
    #   Conceded = 1
    # --------------------------------------------------------

    assert arsenal["away_played"] == 1
    assert arsenal["away_wins"] == 0
    assert arsenal["away_draws"] == 1
    assert arsenal["away_losses"] == 0

    assert arsenal["away_points"] == 1

    assert arsenal["away_goals_for"] == 1
    assert arsenal["away_goals_against"] == 1

    # --------------------------------------------------------
    # Recent form
    #
    # Arsenal has only two matches available at this point.
    #
    # Therefore recent-5 contains exactly those two matches.
    # --------------------------------------------------------

    assert arsenal["recent_5_played"] == 2
    assert arsenal["recent_5_wins"] == 1
    assert arsenal["recent_5_draws"] == 1
    assert arsenal["recent_5_losses"] == 0

    assert arsenal["recent_5_points"] == 4

    assert arsenal["recent_5_goals_for"] == 3
    assert arsenal["recent_5_goals_against"] == 1


# ============================================================
# LEAKAGE TEST
# ============================================================

def test_future_matches_are_excluded() -> None:
    """
    Explicitly prove that future results cannot affect the
    historical state.

    The Chelsea and Liverpool results from GW3/GW4 are very
    different from what they would have looked like if those
    matches had been incorrectly included.
    """

    matches = create_test_matches()

    cutoff = datetime(
        2023,
        8,
        26,
        15,
        0,
    )

    state = build_historical_team_state(
        historical_matches=matches,
        season="2023/24",
        cutoff_datetime=cutoff,
    )

    # --------------------------------------------------------
    # Chelsea has played only one match before the cutoff:
    #
    # Arsenal 2-0 Chelsea
    #
    # Therefore:
    #
    #   Played = 1
    #   Losses = 1
    #   Points = 0
    #   Goals for = 0
    #   Goals against = 2
    # --------------------------------------------------------

    chelsea = state["Chelsea"]

    assert chelsea["played"] == 1
    assert chelsea["wins"] == 0
    assert chelsea["draws"] == 0
    assert chelsea["losses"] == 1

    assert chelsea["points"] == 0

    assert chelsea["goals_for"] == 0
    assert chelsea["goals_against"] == 2

    # --------------------------------------------------------
    # Liverpool has played only one match before the cutoff:
    #
    # Liverpool 1-1 Arsenal
    #
    # The GW3 result:
    #
    # Chelsea 3-1 Liverpool
    #
    # MUST NOT be included.
    # --------------------------------------------------------

    liverpool = state["Liverpool"]

    assert liverpool["played"] == 1
    assert liverpool["wins"] == 0
    assert liverpool["draws"] == 1
    assert liverpool["losses"] == 0

    assert liverpool["points"] == 1

    assert liverpool["goals_for"] == 1
    assert liverpool["goals_against"] == 1


# ============================================================
# EXACT-CUTOFF TEST
# ============================================================

def test_match_at_cutoff_is_excluded() -> None:
    """
    Verify that a match occurring exactly at the cutoff is
    excluded.

    This is important because the prediction for a fixture
    must use information available BEFORE kickoff.
    """

    matches = create_test_matches()

    # Match 3 kicks off exactly at this time.

    cutoff = datetime(
        2023,
        8,
        26,
        15,
        0,
    )

    state = build_historical_team_state(
        historical_matches=matches,
        season="2023/24",
        cutoff_datetime=cutoff,
    )

    # Chelsea's GW3 match must not be included.

    chelsea = state["Chelsea"]

    assert chelsea["played"] == 1

    # Liverpool's GW3 match must also be excluded.

    liverpool = state["Liverpool"]

    assert liverpool["played"] == 1


# ============================================================
# RANKING TEST
# ============================================================

def test_point_in_time_rank() -> None:
    """
    Verify that league ranking is calculated from the
    point-in-time results only.

    At the cutoff:

        Arsenal    4 points
        Liverpool  1 point
        Chelsea    0 points

    Therefore:

        Arsenal    rank 1
        Liverpool  rank 2
        Chelsea    rank 3
    """

    matches = create_test_matches()

    cutoff = datetime(
        2023,
        8,
        26,
        15,
        0,
    )

    state = build_historical_team_state(
        historical_matches=matches,
        season="2023/24",
        cutoff_datetime=cutoff,
    )

    assert state["Arsenal"]["rank"] == 1
    assert state["Liverpool"]["rank"] == 2
    assert state["Chelsea"]["rank"] == 3


# ============================================================
# EMPTY STATE TEST
# ============================================================

def test_empty_state_before_first_match() -> None:
    """
    Verify that the function can handle a cutoff before any
    matches have been played.

    In this case the result should contain no teams because
    the current implementation discovers teams from matches
    that have already occurred.
    """

    matches = create_test_matches()

    cutoff = datetime(
        2023,
        8,
        1,
        12,
        0,
    )

    state = build_historical_team_state(
        historical_matches=matches,
        season="2023/24",
        cutoff_datetime=cutoff,
    )

    assert state == {}


# ============================================================
# TEST RUNNER
# ============================================================

if __name__ == "__main__":
    """
    Allow the test file to be executed directly:

        python test_historical_team_state.py

    Each test is called explicitly so that the file also works
    without requiring pytest to be installed.
    """

    test_point_in_time_state()
    test_future_matches_are_excluded()
    test_match_at_cutoff_is_excluded()
    test_point_in_time_rank()
    test_empty_state_before_first_match()

    print(
        "All historical team state tests passed."
    )