# ============================================================
# FPL TRUTH LAYER
# ============================================================
#
# PURPOSE:
# This file is the single place where our application retrieves
# verified information from the official FPL API.
#
# IMPORTANT:
# The Truth Layer does NOT:
# - calculate expected points
# - recommend transfers
# - choose captains
# - analyse rivals
# - make strategic decisions
#
# Its job is:
#
#       FPL API → verified FPL data → our application
#
# Other modules will later use this data to perform analysis.
# ============================================================


# ============================================================
# 1. IMPORTS
# ============================================================

# "requests" allows Python to communicate with the FPL API.
import requests


# ============================================================
# 2. API CONFIGURATION
# ============================================================

# Base URL for the official FPL API.
#
# Keeping this in one place means we don't have to repeat the
# full API address throughout the file.
FPL_API_BASE_URL = "https://fantasy.premierleague.com/api"


# ============================================================
# 3. GENERIC API REQUEST HELPER
# ============================================================
#
# Most of our Truth Layer functions need to do the same thing:
#
# 1. Build an API URL.
# 2. Send a GET request.
# 3. Check for an error.
# 4. Convert the response from JSON into Python data.
#
# Instead of repeating those four steps in every function,
# we keep them in one reusable helper function.
def _get_api_data(endpoint):

    # Build the complete API URL.
    #
    # Example:
    # endpoint = "bootstrap-static/"
    #
    # becomes:
    # https://fantasy.premierleague.com/api/bootstrap-static/
    url = f"{FPL_API_BASE_URL}/{endpoint}"

    # Send a GET request to the FPL API.
    #
    # timeout=10 means Python will stop waiting if the
    # FPL server does not respond within 10 seconds.
    response = requests.get(
        url,
        timeout=10
    )

    # Check whether the request was successful.
    #
    # If the FPL API returns an error, this will raise an
    # exception instead of allowing bad data to continue.
    response.raise_for_status()

    # Convert the API's JSON response into normal Python data.
    data = response.json()

    # Return the data to the function that requested it.
    return data


# ============================================================
# 4. FPL BOOTSTRAP DATA
# ============================================================

# Get the main FPL dataset.
#
# This contains information about:
# - players
# - teams
# - Gameweeks
# - positions
# - chips
# - FPL settings
# - player statistics
# - price information
def get_bootstrap_data():

    # Ask the generic API helper for the bootstrap data.
    return _get_api_data("bootstrap-static/")


# ============================================================
# 5. CURRENT GAMEWEEK
# ============================================================

# Find the Gameweek that FPL currently marks as active.
def get_current_gameweek():

    # Get the latest bootstrap data from the FPL API.
    data = get_bootstrap_data()

    # Look through every Gameweek in the "events" list.
    for event in data["events"]:

        # FPL marks the current Gameweek with:
        # "is_current": True
        if event["is_current"]:

            # Return the Gameweek number.
            return event["id"]

    # If no Gameweek is marked as current, something is wrong
    # with the data returned by FPL.
    raise ValueError("Could not find the current FPL Gameweek.")


# ============================================================
# 6. MANAGER PICKS
# ============================================================

# Get a manager's selected team for a specific Gameweek.
#
# The response contains:
# - the manager's 15 picks
# - captain and vice-captain
# - bench order
# - active chip
# - Gameweek points
# - transfers
# - other Gameweek information
def get_manager_picks(team_id, gameweek):

    # Build the endpoint for the manager's Gameweek picks.
    endpoint = f"entry/{team_id}/event/{gameweek}/picks/"

    # Retrieve and return the FPL data.
    return _get_api_data(endpoint)


# ============================================================
# 7. MANAGER SEASON HISTORY
# ============================================================

# Get a manager's complete FPL season history.
#
# The response contains:
# - current-season Gameweek history
# - previous-season history
# - chip usage
def get_manager_history(team_id):

    # Build the endpoint for the manager's history.
    endpoint = f"entry/{team_id}/history/"

    # Retrieve and return the FPL data.
    return _get_api_data(endpoint)


# ============================================================
# 8. MANAGER DETAILS
# ============================================================

# Get a manager's basic FPL entry information.
#
# This can include:
# - manager name
# - team name
# - overall points
# - overall rank
# - favourite team
# - other manager-level information
def get_manager_details(team_id):

    # Build the endpoint for the manager's FPL entry.
    endpoint = f"entry/{team_id}/"

    # Retrieve and return the FPL data.
    return _get_api_data(endpoint)