"""
Fixture data utilities for the FPL agent.

This module converts the raw fixture information from the
official FPL API into cleaner fixture records.

It focuses on match-level information:
- Gameweek
- Teams
- Home/away
- Scores
- Fixture difficulty
- Kickoff time
- Match status
- Player-level fixture statistics

Player-history analysis will be handled by a separate module later.
"""


def build_fixture_data(fixtures, bootstrap_data):
    """
    Build a structured list of FPL fixtures.

    Parameters:
        fixtures:
            Raw fixture data returned by get_fixtures().

        bootstrap_data:
            Official FPL bootstrap data returned by
            get_bootstrap_data().

    Returns:
        A list containing one structured dictionary per fixture.

    Raises:
        ValueError if required data is missing or inconsistent.
    """

    # --------------------------------------------------------
    # CHECK 1:
    # Make sure fixtures is a list.
    # --------------------------------------------------------

    if not isinstance(fixtures, list):
        raise ValueError(
            "Fixture data must be a list."
        )

    # --------------------------------------------------------
    # CHECK 2:
    # Make sure bootstrap data is a dictionary.
    # --------------------------------------------------------

    if not isinstance(bootstrap_data, dict):
        raise ValueError(
            "Bootstrap data must be a dictionary."
        )

    # --------------------------------------------------------
    # CHECK 3:
    # Make sure the team information exists.
    # --------------------------------------------------------

    if "teams" not in bootstrap_data:
        raise ValueError(
            "Bootstrap data is missing the 'teams' section."
        )

    # --------------------------------------------------------
    # Create a lookup table:
    #
    # team ID → team information
    #
    # This allows us to quickly convert:
    #
    # team_h = 1
    #
    # into:
    #
    # Arsenal
    # --------------------------------------------------------

    teams_by_id = {
        team["id"]: team
        for team in bootstrap_data["teams"]
    }

    # --------------------------------------------------------
    # Create the final structured fixture list.
    # --------------------------------------------------------

    structured_fixtures = []

    # Process every fixture returned by FPL.
    for fixture in fixtures:

        # ----------------------------------------------------
        # Get the home and away team IDs.
        # ----------------------------------------------------

        home_team_id = fixture["team_h"]
        away_team_id = fixture["team_a"]

        # ----------------------------------------------------
        # Make sure both teams exist in our official team list.
        # ----------------------------------------------------

        if home_team_id not in teams_by_id:
            raise ValueError(
                f"Home team ID {home_team_id} was not found "
                "in the official FPL team list."
            )

        if away_team_id not in teams_by_id:
            raise ValueError(
                f"Away team ID {away_team_id} was not found "
                "in the official FPL team list."
            )

        # Get the actual team records.
        home_team = teams_by_id[home_team_id]
        away_team = teams_by_id[away_team_id]

        # ----------------------------------------------------
        # Create a clean fixture record.
        #
        # We deliberately preserve the original "stats"
        # section because it contains useful player-level
        # information from completed fixtures.
        #
        # A separate player-history module will process those
        # statistics later.
        # ----------------------------------------------------

        structured_fixture = {
            "fixture_id": fixture["id"],
            "gameweek": fixture["event"],
            "kickoff_time": fixture["kickoff_time"],
            "finished": fixture["finished"],
            "finished_provisional": (
                fixture["finished_provisional"]
            ),
            "started": fixture["started"],
            "minutes": fixture["minutes"],
            "home_team_id": home_team_id,
            "home_team": home_team["name"],
            "home_team_short_name": home_team["short_name"],
            "away_team_id": away_team_id,
            "away_team": away_team["name"],
            "away_team_short_name": away_team["short_name"],
            "home_score": fixture["team_h_score"],
            "away_score": fixture["team_a_score"],
            "home_difficulty": fixture["team_h_difficulty"],
            "away_difficulty": fixture["team_a_difficulty"],
            "stats": fixture["stats"],
        }

        # Add the structured fixture to our result list.
        structured_fixtures.append(structured_fixture)

    # --------------------------------------------------------
    # Return all structured fixtures.
    # --------------------------------------------------------

    return structured_fixtures