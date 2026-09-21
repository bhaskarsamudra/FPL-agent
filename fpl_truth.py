# ============================================================
# FPL TRUTH LAYER - STEP 1B
# ============================================================
# PURPOSE:
# This file will become the single place where our application
# gets verified information from the official FPL API.
#
# IMPORTANT:
# We are NOT calculating expected points or making FPL
# recommendations here.
#
# The Truth Layer's job is simply:
#
#       FPL API → verified/raw FPL data → our application
#
# Later, other modules such as the player model, rival engine
# and strategy engine will use this information.
# ============================================================


# STEP 1: Import the "requests" library.
#
# requests allows Python to communicate with websites and APIs.
# We will use it to send a request to the FPL API.
import requests


# STEP 2: Store the FPL API URL in one place.
#
# "bootstrap-static" is one of the main FPL endpoints.
# It contains information about the current FPL season,
# including players, teams, gameweeks and other basic data.
FPL_BOOTSTRAP_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"


# STEP 3: Create a function that retrieves the FPL bootstrap data.
#
# A function is a reusable block of code.
#
# Instead of writing the API request every time we need this
# information, we can simply call:
#
#     get_bootstrap_data()
#
# from another part of our application.
def get_bootstrap_data():

    # STEP 4: Ask the FPL API for the bootstrap data.
    #
    # timeout=10 means Python will stop waiting if the FPL
    # server does not respond within 10 seconds.
    response = requests.get(
        FPL_BOOTSTRAP_URL,
        timeout=10
    )


    # STEP 5: Check whether the FPL API request was successful.
    #
    # HTTP status code 200 means the server successfully
    # returned the requested information.
    #
    # If something went wrong, raise_for_status() will raise
    # an error instead of silently giving us bad data.
    response.raise_for_status()


    # STEP 6: Convert the API's JSON response into Python data.
    #
    # APIs normally send information in JSON format.
    # response.json() converts that JSON into Python dictionaries,
    # lists, numbers and text that our program can work with.
    data = response.json()


    # STEP 7: Return the data to the code that called this function.
    #
    # We don't analyse or modify the data here.
    # We simply return what the FPL API gave us.
    return data
