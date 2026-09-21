"""
Validation functions for official FPL data.

This module checks that data received from the FPL API
looks structurally correct before other parts of our
FPL agent use it.
"""


def validate_manager_picks(
    data,
    expected_gameweek,
    bootstrap_data
):
    """
    Validate a manager's Gameweek picks.

    Parameters:
        data:
            Manager data returned by get_manager_picks().

        expected_gameweek:
            The Gameweek we asked FPL to retrieve.

        bootstrap_data:
            Main FPL data returned by get_bootstrap_data().

    Returns:
        True if all validation checks pass.

    Raises:
        ValueError if an important validation check fails.
    """

    # --------------------------------------------------------
    # CHECK 1:
    # Make sure the manager response is a dictionary.
    # --------------------------------------------------------

    if not isinstance(data, dict):
        raise ValueError(
            "Manager picks data must be a dictionary."
        )

    # --------------------------------------------------------
    # CHECK 2:
    # Make sure the "picks" section exists.
    # --------------------------------------------------------

    if "picks" not in data:
        raise ValueError(
            "Manager picks data is missing the 'picks' section."
        )

    # Get the manager's selected players.
    picks = data["picks"]

    # --------------------------------------------------------
    # CHECK 3:
    # A normal FPL squad contains exactly 15 players.
    # --------------------------------------------------------

    if len(picks) != 15:
        raise ValueError(
            f"Expected 15 manager picks, but received {len(picks)}."
        )

    # --------------------------------------------------------
    # CHECK 4:
    # Make sure the official FPL player list exists.
    # --------------------------------------------------------

    if not isinstance(bootstrap_data, dict):
        raise ValueError(
            "Bootstrap data must be a dictionary."
        )

    if "elements" not in bootstrap_data:
        raise ValueError(
            "Bootstrap data is missing the 'elements' section."
        )

    # --------------------------------------------------------
    # Create a set containing every valid FPL player ID.
    #
    # A set is useful here because it allows us to quickly
    # check whether a player ID exists.
    # --------------------------------------------------------

    valid_player_ids = {
        player["id"]
        for player in bootstrap_data["elements"]
    }

    # --------------------------------------------------------
    # CHECK 5:
    # Make sure no player appears more than once.
    #
    # We store every player ID we have already seen.
    # If we see the same ID again, the squad is invalid.
    # --------------------------------------------------------

    seen_player_ids = set()

    # --------------------------------------------------------
    # CHECK 6:
    # Validate every player in the manager's squad.
    # --------------------------------------------------------

    for player in picks:

        # Make sure this pick contains a player ID.
        if "element" not in player:
            raise ValueError(
                "A manager pick is missing the 'element' player ID."
            )

        # Read the official FPL player ID.
        player_id = player["element"]

        # Make sure the player ID is an integer.
        if not isinstance(player_id, int):
            raise ValueError(
                f"Player ID must be an integer, but received {player_id}."
            )

        # Player IDs must be positive.
        if player_id <= 0:
            raise ValueError(
                f"Player ID must be greater than 0, but received {player_id}."
            )

        # Make sure this player actually exists in the
        # official FPL player list.
        if player_id not in valid_player_ids:
            raise ValueError(
                f"Player ID {player_id} was not found "
                "in the official FPL player list."
            )

        # Check whether this player already appeared earlier.
        if player_id in seen_player_ids:
            raise ValueError(
                f"Player ID {player_id} appears more than once "
                "in the manager's picks."
            )

        # Remember this player ID so we can detect duplicates.
        seen_player_ids.add(player_id)

    # --------------------------------------------------------
    # CHECK 7:
    # Make sure the entry history section exists.
    # --------------------------------------------------------

    if "entry_history" not in data:
        raise ValueError(
            "Manager picks data is missing the 'entry_history' section."
        )

    # Get the Gameweek information returned by FPL.
    entry_history = data["entry_history"]

    # Make sure entry_history is a dictionary.
    if not isinstance(entry_history, dict):
        raise ValueError(
            "Manager entry history must be a dictionary."
        )

    # --------------------------------------------------------
    # CHECK 8:
    # Make sure FPL returned the Gameweek we requested.
    # --------------------------------------------------------

    returned_gameweek = entry_history.get("event")

    if returned_gameweek != expected_gameweek:
        raise ValueError(
            f"Expected Gameweek {expected_gameweek}, "
            f"but FPL returned Gameweek {returned_gameweek}."
        )

    # --------------------------------------------------------
    # If we reached this point, all validation checks passed.
    # --------------------------------------------------------

    return True