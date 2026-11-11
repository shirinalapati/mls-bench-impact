from __future__ import annotations

import numpy as np

from mls_bench_impact.config.settings import settings


def data_confidence(
    appearances: int,
    minutes: float,
    coverage: float,
    simultaneous_rate: float,
    has_both_seasons: bool,
) -> str:
    if appearances < settings.min_sub_appearances or minutes < settings.min_sub_minutes:
        return "Insufficient"
    if (
        appearances >= 15
        and minutes >= 400
        and coverage >= 0.85
        and simultaneous_rate <= 0.45
        and has_both_seasons
    ):
        return "High"
    if appearances >= 10 and minutes >= 250 and coverage >= 0.70:
        return "Medium"
    return "Low"


def model_uncertainty(
    appearances: int,
    minutes: float,
    coverage: float,
    simultaneous_rate: float,
    red_card_rate: float,
    ci_width: float | None,
    season_cv: float | None,
) -> float:
    """0-100 where lower is better."""
    reliability = minutes / (minutes + settings.prior_strength_minutes) if (minutes + settings.prior_strength_minutes) else 0
    sample_u = 100 * (1 - reliability)
    context_u = 100 * (1 - min(max(coverage, 0), 1))
    sim_u = 100 * min(max(simultaneous_rate, 0), 1)
    red_u = 80 * min(max(red_card_rate, 0), 1)
    ci_u = 0.0
    if ci_width is not None and not np.isnan(ci_width):
        ci_u = float(np.clip(ci_width / 0.5 * 100, 0, 100))
    season_u = 0.0 if season_cv is None or np.isnan(season_cv) else float(np.clip(season_cv * 100, 0, 100))
    score = 0.30 * sample_u + 0.20 * context_u + 0.20 * sim_u + 0.10 * red_u + 0.15 * ci_u + 0.05 * season_u
    return float(np.clip(score, 0, 100))


def classify_player(row: dict) -> tuple[str, list[str]]:
    tags: list[str] = []
    bis = row.get("bench_impact_score")
    ssi = row.get("substitute_sporting_impact")
    ati = row.get("adjusted_team_impact_after_entry")
    pif_pct = row.get("positive_impact_frequency_percentile")
    conf = row.get("data_confidence")
    apps = row.get("substitute_appearances") or 0
    mins = row.get("substitute_minutes") or 0
    pos = row.get("position_group") or ""
    adv_pct = row.get("substitute_advantage_percentile")
    adv_available = row.get("advantage_available")
    missing = row.get("components_missing") or ""

    official = apps >= settings.min_sub_appearances and mins >= settings.min_sub_minutes
    if not official:
        if bis is not None and bis >= 70:
            return "Small-Sample Watchlist", ["Small-Sample Watchlist"]
        return "Insufficient Evidence", ["Insufficient Evidence"]

    primary = "Reliable Bench Contributor"
    if (
        bis is not None
        and bis >= 90
        and ssi is not None
        and ssi >= 70
        and ati is not None
        and ati >= 65
        and conf in ("Medium", "High")
        and "adjusted_team_impact_after_entry" not in missing
    ):
        primary = "Elite Game Changer"
    elif bis is not None and bis >= 75 and ssi is not None and ssi >= 60 and conf != "Low":
        primary = "Strong Bench Contributor"
    elif (
        pif_pct is not None
        and pif_pct >= 50
        and ssi is not None
        and ssi >= 50
    ):
        primary = "Reliable Bench Contributor"

    # descriptive tags
    if row.get("trailing_tied_impact", 0) >= 70 and row.get("trailing_tied_apps", 0) >= 5:
        tags.append("Comeback Specialist")
        if primary == "Reliable Bench Contributor":
            primary = "Comeback Specialist"
    if pos in ("Strikers", "Wingers and attacking midfielders") and (ssi or 0) >= 65 and row.get("attack_context_score", 0) >= 60:
        tags.append("Offensive Spark")
        if primary in ("Reliable Bench Contributor",):
            primary = "Offensive Spark"
    if pos in ("Center backs", "Fullbacks and wingbacks", "Central and defensive midfielders") and row.get("leading_impact", 0) >= 65:
        tags.append("Defensive Closer")
        if primary in ("Reliable Bench Contributor",):
            primary = "Defensive Closer"
    if adv_available and adv_pct is not None and adv_pct >= 70 and (row.get("substitute_advantage_raw") or 0) > 0:
        tags.append("Substitute-Specific Performer")
        if primary == "Reliable Bench Contributor":
            primary = "Substitute-Specific Performer"
    if (ssi or 0) >= 70 and adv_available and (row.get("substitute_advantage_raw") or 0) <= 0:
        tags.append("Starter-Caliber Contributor")
        if primary == "Reliable Bench Contributor":
            primary = "Starter-Caliber Contributor"

    if primary not in tags:
        tags.insert(0, primary)
    return primary, tags