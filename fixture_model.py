"""
Fixture model for the FPL agent.

This module combines:

1. Structured fixture data from fixture_data.py
2. Transparent team-strength indicators from team_strength.py

The purpose of this module is to describe the quality of an
upcoming fixture from both the attacking and defensive perspectives.

IMPORTANT:

This is an early measurement layer.

It is NOT yet the final expected-goals model.
It is NOT yet the expected-points model.
It is NOT yet the transfer/strategy engine.

We deliberately do NOT create one opaque "fixture score".

Instead, we expose the individual matchup components so that they
can be inspected, validated and eventually tested against historical
results.

The official FPL fixture difficulty rating is retained as a
benchmark/reference only. It is NOT used to calculate our internal
matchup signals.
"""

from typing import Any


# ============================================================
# CONSTANTS
# ============================================================

# A small number of completed matches means that a team's
# observed home/away statistics can be extremely noisy.
#
# We do not hide this uncertainty. We expose the sample size
# in every fixture-model record.
MINIMUM_SAMPLE_WARNING = 5


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _safe_float(value: Any, default: float = 0.0) -> float:
    """
    Safely convert a value to float.

    FPL data can contain integers, floats, strings, None or
    missing values.

    Invalid values return the supplied default.
    """

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_ratio(
    numerator: float,
    denominator: float,
    default: float = 1.0,
) -> float:
    """
    Safely calculate numerator / denominator.

    If the denominator is zero or negative, return the default.

    A ratio of:

        1.00 = equal to reference
        >1.00 = above reference
        <1.00 = below reference

    This helper prevents division-by-zero from creating misleading
    infinite fixture signals.
    """

    if denominator <= 0:
        return default

    return numerator / denominator


def _get_team_strength(
    team_strength: dict[int, dict[str, Any]],
    team_id: int,
) -> dict[str, Any]:
    """
    Retrieve one team's strength record.

    Missing team-strength data is treated as a data-quality failure.

    We do NOT silently create a fixture recommendation when an
    essential input is missing.
    """

    if team_id not in team_strength:
        raise ValueError(
            f"Team ID {team_id} was not found in team-strength data."
        )

    return team_strength[team_id]


def _get_venue_metrics(
    team_strength_record: dict[str, Any],
    venue: str,
) -> dict[str, float]:
    """
    Extract the appropriate home/away observed metrics.

    For a home fixture we use:

        home attack
        home defence

    For an away fixture we use:

        away attack
        away defence
    """

    if venue == "home":

        return {
            "attack_ratio": _safe_float(
                team_strength_record.get("home_attack_ratio")
            ),
            "defence_ratio": _safe_float(
                team_strength_record.get("home_defence_ratio")
            ),
        }

    if venue == "away":

        return {
            "attack_ratio": _safe_float(
                team_strength_record.get("away_attack_ratio")
            ),
            "defence_ratio": _safe_float(
                team_strength_record.get("away_defence_ratio")
            ),
        }

    raise ValueError(
        "Venue must be either 'home' or 'away'."
    )


def _build_matchup_for_team(
    team_strength_record: dict[str, Any],
    opponent_strength_record: dict[str, Any],
    venue: str,
) -> dict[str, Any]:
    """
    Build transparent matchup measurements for one team.

    The output contains separate attacking and defensive signals.

    ATTACKING MATCHUP

        Team attacking strength
        ------------------------
        Opponent defensive strength

    DEFENSIVE MATCHUP

        Team defensive strength
        -----------------------
        Opponent attacking strength

    We also retain the raw components so that future modelling
    can decide how these signals should be combined.

    No final weighted fixture score is created here.
    """

    # ------------------------------------------------------------
    # Determine which home/away metrics should be used.
    # ------------------------------------------------------------

    team_venue_metrics = _get_venue_metrics(
        team_strength_record,
        venue,
    )

    # The opponent plays at the opposite venue.
    opponent_venue = (
        "away"
        if venue == "home"
        else "home"
    )

    opponent_venue_metrics = _get_venue_metrics(
        opponent_strength_record,
        opponent_venue,
    )

    # ------------------------------------------------------------
    # OBSERVED ATTACKING MATCHUP
    #
    # Higher means the team's observed attacking profile is
    # stronger relative to the opponent's defensive profile.
    # ------------------------------------------------------------

    observed_attack_matchup = _safe_ratio(
        team_venue_metrics["attack_ratio"],
        opponent_venue_metrics["defence_ratio"],
    )

    # ------------------------------------------------------------
    # OBSERVED DEFENSIVE MATCHUP
    #
    # Higher means the team's defensive profile is stronger
    # relative to the opponent's attacking profile.
    # ------------------------------------------------------------

    observed_defence_matchup = _safe_ratio(
        team_venue_metrics["defence_ratio"],
        opponent_venue_metrics["attack_ratio"],
    )

    # ------------------------------------------------------------
    # UNDERLYING ATTACKING DATA
    #
    # team_strength.py provides underlying xG/xGI rates.
    #
    # These are not currently split into home/away xG metrics,
    # so we keep them as overall underlying attacking indicators.
    #
    # Importantly, we do NOT pretend they are venue-specific.
    # ------------------------------------------------------------

    team_xg_ratio = _safe_float(
        team_strength_record.get(
            "underlying_attack_xg_ratio"
        ),
        default=1.0,
    )

    team_xgi_ratio = _safe_float(
        team_strength_record.get(
            "underlying_attack_xgi_ratio"
        ),
        default=1.0,
    )

    opponent_xg_ratio = _safe_float(
        opponent_strength_record.get(
            "underlying_attack_xg_ratio"
        ),
        default=1.0,
    )

    opponent_xgi_ratio = _safe_float(
        opponent_strength_record.get(
            "underlying_attack_xgi_ratio"
        ),
        default=1.0,
    )

    # ------------------------------------------------------------
    # IMPORTANT MODELLING NOTE
    #
    # We do not yet have a validated team-level underlying
    # defensive xG model.
    #
    # Therefore we should NOT manufacture:
    #
    #     team xG / opponent xGC
    #
    # using a potentially unreliable field.
    #
    # Instead, we expose the underlying attacking strengths
    # independently for later expected-goals modelling.
    # ------------------------------------------------------------

    underlying_xg_attack_strength = team_xg_ratio

    underlying_xgi_attack_strength = team_xgi_ratio

    # ------------------------------------------------------------
    # Relative underlying attacking matchup.
    #
    # This is intentionally labelled "relative" because the
    # opponent values represent attacking strength, not defensive
    # xG conceded.
    #
    # A proper expected-goals model will replace this with a
    # validated attack-vs-defence calculation.
    # ------------------------------------------------------------

    relative_xg_attack_matchup = _safe_ratio(
        team_xg_ratio,
        opponent_xg_ratio,
    )

    relative_xgi_attack_matchup = _safe_ratio(
        team_xgi_ratio,
        opponent_xgi_ratio,
    )

    # ------------------------------------------------------------
    # Return all components separately.
    # ------------------------------------------------------------

    return {
        "venue": venue,

        # --------------------------------------------------------
        # Observed venue-specific strength.
        # --------------------------------------------------------

        "team_attack_ratio": team_venue_metrics[
            "attack_ratio"
        ],

        "team_defence_ratio": team_venue_metrics[
            "defence_ratio"
        ],

        "opponent_attack_ratio": opponent_venue_metrics[
            "attack_ratio"
        ],

        "opponent_defence_ratio": opponent_venue_metrics[
            "defence_ratio"
        ],

        # --------------------------------------------------------
        # Observed matchup indicators.
        # --------------------------------------------------------

        "observed_attack_matchup": (
            observed_attack_matchup
        ),

        "observed_defence_matchup": (
            observed_defence_matchup
        ),

        # --------------------------------------------------------
        # Underlying attacking strength.
        # --------------------------------------------------------

        "underlying_xg_attack_strength": (
            underlying_xg_attack_strength
        ),

        "underlying_xgi_attack_strength": (
            underlying_xgi_attack_strength
        ),

        # --------------------------------------------------------
        # Relative underlying attacking indicators.
        #
        # These are diagnostic only at this stage.
        # --------------------------------------------------------

        "relative_xg_attack_matchup": (
            relative_xg_attack_matchup
        ),

        "relative_xgi_attack_matchup": (
            relative_xgi_attack_matchup
        ),
    }


# ============================================================
# MAIN FUNCTION
# ============================================================

def build_fixture_model(
    fixtures: list[dict[str, Any]],
    team_strength: dict[int, dict[str, Any]],
    include_finished: bool = False,
) -> list[dict[str, Any]]:
    """
    Build transparent fixture matchup records.

    Parameters
    ----------
    fixtures:
        Structured fixture records returned by
        build_fixture_data().

    team_strength:
        Team-strength records returned by
        build_team_strength().

    include_finished:
        If False, only upcoming/uncompleted fixtures are returned.

        If True, completed fixtures are also included.

        The latter will be useful later when we perform historical
        model evaluation.

    Returns
    -------
    list[dict[str, Any]]
        One fixture-model record per eligible fixture.

    Important
    ---------
    This function does NOT calculate:

    - expected goals
    - expected assists
    - expected clean sheets
    - expected FPL points
    - transfer recommendations

    Those belong to later modelling layers.
    """

    # ------------------------------------------------------------
    # Validate fixture input.
    # ------------------------------------------------------------

    if not isinstance(fixtures, list):
        raise TypeError(
            "fixtures must be a list."
        )

    # ------------------------------------------------------------
    # Validate team-strength input.
    # ------------------------------------------------------------

    if not isinstance(team_strength, dict):
        raise TypeError(
            "team_strength must be a dictionary keyed by team ID."
        )

    model_records = []

    # ------------------------------------------------------------
    # Process every fixture.
    # ------------------------------------------------------------

    for fixture in fixtures:

        # --------------------------------------------------------
        # Determine completion status.
        # --------------------------------------------------------

        finished = bool(
            fixture.get("finished", False)
        )

        # By default, this model is intended for upcoming fixtures.
        if finished and not include_finished:
            continue

        # --------------------------------------------------------
        # Required fixture identifiers.
        # --------------------------------------------------------

        fixture_id = fixture.get("fixture_id")
        gameweek = fixture.get("gameweek")

        home_team_id = fixture.get("home_team_id")
        away_team_id = fixture.get("away_team_id")

        if home_team_id is None:
            raise ValueError(
                f"Fixture {fixture_id} is missing home_team_id."
            )

        if away_team_id is None:
            raise ValueError(
                f"Fixture {fixture_id} is missing away_team_id."
            )

        # --------------------------------------------------------
        # Retrieve strength records.
        # --------------------------------------------------------

        home_strength = _get_team_strength(
            team_strength,
            int(home_team_id),
        )

        away_strength = _get_team_strength(
            team_strength,
            int(away_team_id),
        )

        # --------------------------------------------------------
        # Build HOME-team perspective.
        # --------------------------------------------------------

        home_matchup = _build_matchup_for_team(
            team_strength_record=home_strength,
            opponent_strength_record=away_strength,
            venue="home",
        )

        # --------------------------------------------------------
        # Build AWAY-team perspective.
        # --------------------------------------------------------

        away_matchup = _build_matchup_for_team(
            team_strength_record=away_strength,
            opponent_strength_record=home_strength,
            venue="away",
        )

        # --------------------------------------------------------
        # Sample sizes.
        #
        # These will become important later when we introduce
        # statistical shrinkage / reliability weighting.
        # --------------------------------------------------------

        home_sample_size = int(
            _safe_float(
                home_strength.get("played"),
                default=0,
            )
        )

        away_sample_size = int(
            _safe_float(
                away_strength.get("played"),
                default=0,
            )
        )

        # --------------------------------------------------------
        # Flag whether the current sample is still small.
        # --------------------------------------------------------

        small_sample = (
            home_sample_size < MINIMUM_SAMPLE_WARNING
            or away_sample_size < MINIMUM_SAMPLE_WARNING
        )

        # --------------------------------------------------------
        # Construct final fixture-model record.
        # --------------------------------------------------------

        model_record = {

            # ====================================================
            # FIXTURE IDENTITY
            # ====================================================

            "fixture_id": fixture_id,
            "gameweek": gameweek,
            "kickoff_time": fixture.get("kickoff_time"),
            "finished": finished,

            # ====================================================
            # HOME TEAM
            # ====================================================

            "home_team_id": home_team_id,
            "home_team": fixture.get("home_team"),

            # ====================================================
            # AWAY TEAM
            # ====================================================

            "away_team_id": away_team_id,
            "away_team": fixture.get("away_team"),

            # ====================================================
            # OFFICIAL FPL BENCHMARK
            #
            # These fields are retained for comparison only.
            #
            # They are NOT inputs into our internal model.
            # ====================================================

            "official_fpl_home_difficulty": (
                fixture.get("home_difficulty")
            ),

            "official_fpl_away_difficulty": (
                fixture.get("away_difficulty")
            ),

            # ====================================================
            # HOME MATCHUP
            # ====================================================

            "home_matchup": home_matchup,

            # ====================================================
            # AWAY MATCHUP
            # ====================================================

            "away_matchup": away_matchup,

            # ====================================================
            # SAMPLE SIZE / RELIABILITY
            # ====================================================

            "home_team_sample_size": home_sample_size,
            "away_team_sample_size": away_sample_size,
            "small_sample_warning": small_sample,
        }

        model_records.append(model_record)

    # ------------------------------------------------------------
    # Return all fixture-model records.
    # ------------------------------------------------------------

    return model_records