"""
Shared pytest fixtures for the FPL Strategist project.

These fixtures provide the six-season historical Premier League
dataset to tests that expect either:

- historical_matches
- matches

The dataset is session-scoped so the historical CSV files are
loaded only once during a pytest run.
"""

import pytest
import pandas as pd

from historical_team_data import load_historical_team_matches


@pytest.fixture(scope="session")
def historical_matches() -> pd.DataFrame:
    """
    Load all six historical Premier League seasons once.

    The fixture is session-scoped because the same 2,280-match
    dataset is reused by multiple test modules.
    """
    return load_historical_team_matches()


@pytest.fixture(scope="session")
def matches(historical_matches: pd.DataFrame) -> pd.DataFrame:
    """
    Provide the same historical dataset under the generic
    'matches' fixture name.

    Some real-data historical team-state tests use this name.
    Reusing historical_matches avoids loading the CSV files twice.
    """
    return historical_matches
