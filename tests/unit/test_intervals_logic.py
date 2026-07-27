from mls_bench_impact.transform.intervals import _red_card_state, _score_before_minute, _window_xg


def test_score_before_minute():
    events = [
        {"type": "Goal", "time": 10, "overloadTime": 0, "isHome": True, "newScore": [1, 0], "ownGoal": False},
        {"type": "Goal", "time": 70, "overloadTime": 0, "isHome": False, "newScore": [1, 1], "ownGoal": False},
    ]
    assert _score_before_minute(events, 60, True) == (1, 0)
    assert _score_before_minute(events, 60, False) == (0, 1)


def test_red_card_state():
    events = [{"type": "Card", "card": "Red", "time": 40, "overloadTime": 0, "isHome": True}]
    assert _red_card_state(events, 50, True) == "team_short"
    assert _red_card_state(events, 50, False) == "opponent_short"


def test_window_xg():
    shots = [
        {"min": 10, "minAdded": 0, "expectedGoals": 0.2, "teamId": 1, "isOwnGoal": False},
        {"min": 80, "minAdded": 0, "expectedGoals": 0.4, "teamId": 2, "isOwnGoal": False},
    ]
    xf, xa, sf, sa = _window_xg(shots, 1, 0, 90)
    assert abs(xf - 0.2) < 1e-9
    assert abs(xa - 0.4) < 1e-9