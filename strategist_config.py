"""
strategist_config.py

Central configuration for the deterministic FPL strategy engine.

The configuration is intentionally kept separate from strategy logic so
parameters can later be calibrated without rewriting the engines.
"""

from __future__ import annotations

# Historical Prior V1: newest completed season first.
HISTORICAL_PRIOR_WEIGHTS = (0.60, 0.30, 0.10)

# Expected-goals baseline parameters.
DEFAULT_LEAGUE_AVERAGE_HOME_GOALS = 1.50
DEFAULT_LEAGUE_AVERAGE_AWAY_GOALS = 1.20
DEFAULT_XG_SHRINKAGE_K = 5.0

# Strategy horizon.
DEFAULT_STRATEGY_HORIZON_GWS = 3

# Transfer search limits. These are safety/performance controls, not
# strategic preferences.
MAX_TRANSFER_CANDIDATES = 250
MAX_TRANSFER_COMBINATIONS = 5000

# Strategy risk controls.
# These are intentionally configurable and should be validated later
# with historical back-testing before being treated as optimized values.
DEFAULT_DIFFERENTIAL_OWNERSHIP_THRESHOLD = 10.0
DEFAULT_MIN_EXPECTED_GAIN_FOR_TRANSFER = 0.25

# Current project model version.
STRATEGY_ENGINE_VERSION = "strategy_v1"
EXPECTED_POINTS_VERSION = "xp_baseline_v1"
