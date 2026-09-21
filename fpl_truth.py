# ============================================================
# FPL TRUTH LAYER - STEP 1D
# ============================================================
# PURPOSE:
# This file is the single place where our application
# gets verified information from the official FPL API.
#
# IMPORTANT:
# We are NOT calculating expected points or making FPL
# recommendations here.
#
# The Truth Layer's job is simply:
#
# FPL API → verified/raw FPL data → our application
#
# Later, other modules such as the player model, rival engine
# and strategy engine will use this information.
# ============================================================


# STEP 1: Import the "requests" library.
#
# requests allows Python to communicate with websites and APIs.
import requests


# STEP 2: Store the FPL API URL in one place.
#
# "bootstrap-static" is one of the main FPL endpoints.
# It contains information about the current FPL season,
# including players, teams, gameweeks and other basic data.
FPL_BOOTSTRAP_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"


# STEP 3: Create a function that retrieves the FPL bootstrap data.
#
# Instead of writing the API request every time we need this
# information, we can simply call get_bootstrap_data().
def get_bootstrap_data():

    # Ask the FPL API for the bootstrap data.
    #
    # timeout=10 means Python will stop waiting if the FPL
    # server does not respond within 10 seconds.
    response = requests.get(
        FPL_BOOTSTRAP_URL,
        timeout=10
    )

    # Check whether the FPL API request was successful.
    #
    # If something went wrong, this will raise an error
    # instead of allowing bad data to continue.
    response.raise_for_status()

    # Convert the API's JSON response into Python data.
    data = response.json()

    # Return the data to the code that called this function.
    return data


# STEP 4: Create a function that finds the current Gameweek.
#
# This function uses the official FPL API to determine
# which Gameweek is currently active.
def get_current_gameweek():

    # Get the latest verified data from the FPL API.
    data = get_bootstrap_data()

    # Look through every Gameweek in the "events" list.
    for event in data["events"]:

        # The FPL API marks the current Gameweek with
        # "is_current": True.
        if event["is_current"]:

            # Return the Gameweek number.
            return event["id"]

    # If no Gameweek is marked as current, something is wrong
    # with the data we received.
    raise ValueError("Could not find the current FPL Gameweek.")
# ============================================================
# STEP 1E:
# Get a manager's selected team for a specific Gameweek.
# ============================================================
#
# This function retrieves the 15 players selected by a manager
# for a particular Gameweek.
#
# IMPORTANT:
# We pass the team_id and gameweek into the function.
# We do NOT hardcode any manager's ID here.
#
# This makes the Truth Layer reusable for:
# - our own team
# - mini-league rivals
# - future users of the application
def get_manager_picks(team_id, gameweek):

    # Build the URL for the manager's Gameweek picks.
    #
    # Example:
    # team_id = 3325156
    # gameweek = 5
    #
    # The resulting URL will point to that manager's
    # Gameweek 5 team.
    url = (
        f"https://fantasy.premierleague.com/api/"
        f"entry/{team_id}/event/{gameweek}/picks/"
    )

    # Ask the FPL API for the manager's Gameweek data.
    response = requests.get(
        url,
        timeout=10
    )

    # Make sure the API request was successful.
    response.raise_for_status()

    # Convert the JSON response into normal Python data.
    data = response.json()

    # Return the complete response without changing it.
    return data
# ============================================================
# STEP 1F:
# Get a manager's season history.
# ============================================================
#
# This function retrieves the manager's Gameweek-by-Gameweek
# history for the current FPL season.
#
# IMPORTANT:
# We pass the team_id into the function.
# We do NOT hardcode a manager's ID here.
#
# This allows the same function to work for:
# - our own team
# - mini-league rivals
# - future users
def get_manager_history(team_id):

    # Build the URL for the manager's season history.
    #
    # Example:
    # team_id = 3325156
    #
    # The resulting URL points to that manager's
    # complete season history.
    url = (
        f"https://fantasy.premierleague.com/api/"
        f"entry/{team_id}/history/"
    )

    # Ask the FPL API for the manager's history.
    response = requests.get(
        url,
        timeout=10
    )

    # Make sure the API request was successful.
    response.raise_for_status()

    # Convert the JSON response into normal Python data.
    data = response.json()

    # Return the complete response without changing it.
    return data