from news_layer import build_player_news_signals


def test_news_signal_is_actionable_for_injury():
    rows = build_player_news_signals([
        {
            "id": 1,
            "status": "i",
            "news": "Minor injury",
            "chance_of_playing_this_round": 50,
            "chance_of_playing_next_round": 75,
        }
    ])
    assert rows[1].actionable
    assert rows[1].chance_this_round == 50
