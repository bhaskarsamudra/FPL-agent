# IMPORTANT:
# Some numeric-looking fields returned by the FPL API are strings.
# We intentionally preserve those raw values in this layer.
# Individual modelling layers will convert them to numbers when
# they actually need to perform calculations.
#
# Player prices are an exception: FPL returns them as integers
# representing tenths of £1 million (for example, 61 = £6.1m).
"""
Player data utilities for the FPL agent.

This module converts the raw player information from
FPL's bootstrap-static endpoint into a cleaner player
universe that can be used by later strategy engines.
"""


def build_player_universe(bootstrap_data):
    """
    Build a structured list containing every FPL player.

    The function joins each player's team ID and position ID
    to the corresponding team and position records from FPL.

    Parameters:
        bootstrap_data:
            Official FPL data returned by get_bootstrap_data().

    Returns:
        A list containing one dictionary for every FPL player.
    """

    # --------------------------------------------------------
    # CHECK 1:
    # Make sure bootstrap data is a dictionary.
    # --------------------------------------------------------

    if not isinstance(bootstrap_data, dict):
        raise ValueError(
            "Bootstrap data must be a dictionary."
        )

    # --------------------------------------------------------
    # CHECK 2:
    # Make sure the required sections exist.
    # --------------------------------------------------------

    required_sections = [
        "elements",
        "teams",
        "element_types",
    ]

    for section in required_sections:
        if section not in bootstrap_data:
            raise ValueError(
                f"Bootstrap data is missing the '{section}' section."
            )

    # --------------------------------------------------------
    # Create a lookup table for teams.
    #
    # Instead of searching through all 20 teams every time
    # we process a player, we create:
    #
    # team ID → team information
    #
    # Example:
    # 1 → Arsenal
    # 2 → Aston Villa
    # etc.
    # --------------------------------------------------------

    teams_by_id = {
        team["id"]: team
        for team in bootstrap_data["teams"]
    }

    # --------------------------------------------------------
    # Create a lookup table for player positions.
    #
    # Example:
    # 1 → Goalkeeper
    # 2 → Defender
    # 3 → Midfielder
    # 4 → Forward
    # --------------------------------------------------------

    positions_by_id = {
        position["id"]: position
        for position in bootstrap_data["element_types"]
    }

    # --------------------------------------------------------
    # Create the final player universe.
    # --------------------------------------------------------

    players = []

    # Process every player in the official FPL player list.
    for player in bootstrap_data["elements"]:

        # Get the player's team using the team ID.
        team = teams_by_id.get(player["team"])

        # Get the player's position using the position ID.
        position = positions_by_id.get(player["element_type"])

        # If either lookup fails, the data is inconsistent.
        if team is None:
            raise ValueError(
                f"Team ID {player['team']} was not found "
                f"for player ID {player['id']}."
            )

        if position is None:
            raise ValueError(
                f"Position ID {player['element_type']} was not found "
                f"for player ID {player['id']}."
            )

        # ----------------------------------------------------
        # Create a cleaner player record.
        #
        # We keep the important fields we know we will need.
        # We will add more fields later as the player model
        # becomes more sophisticated.
        # ----------------------------------------------------

        player_record = {
            "id": player["id"],
            "name": (
                f"{player['first_name']} "
                f"{player['second_name']}"
            ),
            "web_name": player["web_name"],
            "team_id": player["team"],
            "team_name": team["name"],
            "team_short_name": team["short_name"],
            "position_id": player["element_type"],
            "position": position["singular_name"],
            # FPL stores player prices in tenths of £1 million.
            # For example, 61 means £6.1m.
            # We keep the original integer value to avoid floating-point
            # rounding issues. Conversion to £m can be done later when
            # displaying the value to the user.
            "price": player["now_cost"],
            "form": player["form"],
            "total_points": player["total_points"],
            "event_points": player["event_points"],
            "points_per_game": player["points_per_game"],
            "selected_by_percent": player["selected_by_percent"],
            "chance_of_playing_next_round": (
                player["chance_of_playing_next_round"]
            ),
            "chance_of_playing_this_round": (
                player["chance_of_playing_this_round"]
            ),
            "news": player["news"],
            "minutes": player["minutes"],
            "starts": player["starts"],
            "goals_scored": player["goals_scored"],
            "assists": player["assists"],
            "clean_sheets": player["clean_sheets"],
            "expected_goals": player["expected_goals"],
            "expected_assists": player["expected_assists"],
            "expected_goal_involvements": (
                player["expected_goal_involvements"]
            ),
            "expected_goals_conceded": (
                player["expected_goals_conceded"]
            ),
            "bonus": player["bonus"],
            "bps": player["bps"],
            "defensive_contribution": (
                player["defensive_contribution"]
            ),
            "ep_next": player["ep_next"],
            "ep_this": player["ep_this"],
            "transfers_in": player["transfers_in"],
            "transfers_out": player["transfers_out"],
            "transfers_in_event": player["transfers_in_event"],
            "transfers_out_event": player["transfers_out_event"],
            "price_change_projections": (
                player["price_change_projections"]
            ),
            "status": player["status"],
            "can_select": player["can_select"],
            "can_transact": player["can_transact"],
        }

        # Add this player to our complete player universe.
        players.append(player_record)

    # --------------------------------------------------------
    # Return all players.
    # --------------------------------------------------------

    return players