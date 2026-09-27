"""Tests for dataset freshness policies."""

from freshness_policy import get_policy, is_fresh


def test_historical_data_is_immutable():
    policy = get_policy("historical_match_data")
    assert policy.immutable is True
    assert is_fresh(999999, "historical_match_data") is True


def test_missing_data_is_stale():
    assert is_fresh(None, "player_summary") is False


def test_normal_and_deadline_ttls_differ():
    policy = get_policy("availability_news")
    assert policy.ttl_minutes == 180
    assert policy.near_deadline_ttl_minutes == 15
    assert is_fresh(30, "availability_news") is True
    assert is_fresh(30, "availability_news", near_deadline=True) is False


def test_season_rules_are_long_lived():
    policy = get_policy("season_rules")
    assert policy.immutable is False
    assert policy.ttl_minutes == 525600
    assert is_fresh(525000, "season_rules") is True
    assert is_fresh(526000, "season_rules") is False
