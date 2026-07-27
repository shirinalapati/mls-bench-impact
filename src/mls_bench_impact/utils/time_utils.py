from __future__ import annotations


def normalized_minute(clock_minute: float | int | None, stoppage: float | int | None = 0) -> float:
    """Convert clock + stoppage into a comparable minute value."""
    clock = float(clock_minute or 0)
    stop = float(stoppage or 0)
    if stop < 0:
        stop = 0
    return clock + stop


def entry_timing_category(minute: float, is_halftime: bool = False) -> str:
    if is_halftime or abs(minute - 45.0) < 1e-6 or abs(minute - 46.0) < 1e-6:
        # exact HT markers still also tagged; primary HT uses is_halftime
        pass
    if is_halftime:
        return "halftime"
    if minute < 30:
        return "emergency_early"
    if minute < 60:
        return "early"
    if minute <= 75:
        return "standard"
    return "late"


def score_state_detailed(diff: int) -> str:
    if diff >= 2:
        return "leading_by_two_plus"
    if diff == 1:
        return "leading_by_one"
    if diff == 0:
        return "tied"
    if diff == -1:
        return "trailing_by_one"
    return "trailing_by_two_plus"


def score_state_simple(diff: int) -> str:
    if diff > 0:
        return "leading"
    if diff < 0:
        return "trailing"
    return "tied"


def tactical_situation(
    score_diff: int,
    entry_minute: float,
    is_halftime: bool,
    red_card_state: str,
    injured: bool,
) -> str:
    if injured:
        return "injury_replacement"
    if red_card_state and red_card_state not in ("none", "balanced", ""):
        return "red_card_response"
    if is_halftime:
        return "halftime_tactical_change"
    if score_diff < 0:
        return "chasing_the_match"
    if score_diff > 0 and entry_minute >= 75:
        return "protecting_a_lead"
    if score_diff == 0:
        return "maintaining_control"
    if score_diff > 0:
        return "protecting_a_lead"
    return "unknown"