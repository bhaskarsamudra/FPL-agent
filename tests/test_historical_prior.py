"""
Tests for the Historical Prior Layer.

The tests use a small deterministic synthetic dataset so that the methodology
can be verified without depending on an external data download.
"""

import pandas as pd
import pytest

from historical_prior import (
    MAX_HISTORICAL_SEASONS,
    RECENCY_WEIGHTS,
    build_historical_prior,
    build_historical_priors,
    get_prior_seasons,
    priors_to_dataframe,
)


def make_matches():
    """Create deterministic historical matches for three seasons."""

    rows = []

    # Each season contains two matches for Team A and two for Team B.
    # Values are intentionally different by season so recency weighting can
    # be verified exactly.
    season_values = {
        "2023/24": (2, 1, 2, 1),
        "2024/25": (3, 1, 1, 2),
        "2025/26": (4, 2, 2, 3),
    }

    match_number = 0

    for season, (a_home, b_home, a_away, b_away) in season_values.items():
        match_number += 1
        rows.append(
            {
                "season": season,
                "home_team": "Team A",
                "away_team": "Team B",
                "home_goals": a_home,
                "away_goals": b_home,
                "match_id": f"m{match_number}",
            }
        )

        match_number += 1
        rows.append(
            {
                "season": season,
                "home_team": "Team B",
                "away_team": "Team A",
                "home_goals": b_away,
                "away_goals": a_away,
                "match_id": f"m{match_number}",
            }
        )

    return pd.DataFrame(rows)


def test_prior_seasons_are_strictly_before_target_and_newest_first():
    """Only completed seasons before the target can enter the prior."""

    available = [
        "2020/21",
        "2021/22",
        "2022/23",
        "2023/24",
        "2024/25",
        "2025/26",
    ]

    result = get_prior_seasons("2026/27", available)

    assert result == ["2025/26", "2024/25", "2023/24"]
    assert len(result) == MAX_HISTORICAL_SEASONS


def test_target_season_is_never_used():
    """The target season must never become historical evidence."""

    available = ["2024/25", "2025/26", "2026/27"]

    result = get_prior_seasons("2026/27", available)

    assert "2026/27" not in result
    assert result == ["2025/26", "2024/25"]


def test_recency_weights_are_newest_first():
    """The documented baseline weights are 60%, 30%, 10%."""

    assert RECENCY_WEIGHTS == (0.60, 0.30, 0.10)
    assert sum(RECENCY_WEIGHTS) == pytest.approx(1.0)


def test_prior_contains_three_seasons_and_metadata():
    """A team with three seasons of history receives three weighted inputs."""

    matches = make_matches()
    prior = build_historical_prior(matches, "2026/27", "Team A")

    assert prior.historical_prior_available is True
    assert prior.seasons_used == ("2025/26", "2024/25", "2023/24")
    assert prior.season_count == 3
    assert prior.sample_size == 6
    assert prior.recency_weights == pytest.approx((0.60, 0.30, 0.10))


def test_missing_team_has_no_fabricated_prior():
    """A team with no historical evidence must remain explicitly unavailable."""

    matches = make_matches()
    prior = build_historical_prior(matches, "2026/27", "Promoted Team")

    assert prior.historical_prior_available is False
    assert prior.season_count == 0
    assert prior.sample_size == 0
    assert prior.attack_overall is None
    assert prior.defence_overall is None


def test_missing_middle_season_does_not_receive_zero_value():
    """Missing historical seasons are skipped, not fabricated as zero strength."""

    matches = make_matches()
    matches = matches[matches["season"] != "2024/25"].copy()

    prior = build_historical_prior(matches, "2026/27", "Team A")

    assert prior.seasons_used == ("2025/26", "2023/24")
    assert prior.season_count == 2
    assert prior.recency_weights == pytest.approx((0.60 / 0.90, 0.30 / 0.90))


def test_underlying_metrics_are_not_fabricated():
    """Result-only historical data must not invent xG/xGA values."""

    matches = make_matches()
    prior = build_historical_prior(matches, "2026/27", "Team A")

    assert prior.underlying_xg_overall is None
    assert prior.underlying_xga_overall is None


def test_historical_prior_is_not_current_season_state():
    """Adding target-season matches must not change the historical prior."""

    matches = make_matches()
    baseline = build_historical_prior(matches, "2026/27", "Team A")

    target_rows = pd.DataFrame(
        [
            {
                "season": "2026/27",
                "home_team": "Team A",
                "away_team": "Team B",
                "home_goals": 10,
                "away_goals": 0,
                "match_id": "future-1",
            }
        ]
    )

    expanded = pd.concat([matches, target_rows], ignore_index=True)
    after_target_added = build_historical_prior(expanded, "2026/27", "Team A")

    assert after_target_added == baseline


def test_multiple_team_builder_and_dataframe_conversion():
    """The batch API and diagnostic tabular conversion work as expected."""

    matches = make_matches()
    priors = build_historical_priors(
        matches,
        "2026/27",
        teams=["Team A", "Team B"],
    )

    assert set(priors) == {"Team A", "Team B"}

    frame = priors_to_dataframe(priors)

    assert len(frame) == 2
    assert set(frame["team"]) == {"Team A", "Team B"}
    assert "historical_prior_available" in frame.columns
