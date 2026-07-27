from __future__ import annotations

POSITION_GROUPS = {
    "ST": "Strikers",
    "CF": "Strikers",
    "W": "Wingers and attacking midfielders",
    "AM": "Wingers and attacking midfielders",
    "WM": "Wingers and attacking midfielders",
    "CM": "Central and defensive midfielders",
    "DM": "Central and defensive midfielders",
    "M": "Central and defensive midfielders",
    "FB": "Fullbacks and wingbacks",
    "WB": "Fullbacks and wingbacks",
    "CB": "Center backs",
    "D": "Center backs",
    "GK": "Goalkeepers",
}

BROAD_ROLES = {
    "Strikers": "Attacking substitute",
    "Wingers and attacking midfielders": "Attacking substitute",
    "Central and defensive midfielders": "Midfield-control substitute",
    "Fullbacks and wingbacks": "Defensive substitute",
    "Center backs": "Defensive substitute",
}

ENTRY_TIMING = {
    "emergency_early": (0, 30),
    "early": (0, 60),
    "standard": (60, 75),
    "late": (75, 200),
}

SCORE_STATE_DETAILED = [
    "leading_by_two_plus",
    "leading_by_one",
    "tied",
    "trailing_by_one",
    "trailing_by_two_plus",
]

SCORE_STATE_SIMPLE = ["leading", "tied", "trailing"]

BENCH_IMPACT_WEIGHTS = {
    "default": (0.50, 0.30, 0.20),
    "attack_heavy": (0.60, 0.25, 0.15),
    "balanced_team": (0.40, 0.40, 0.20),
    "equal": (1 / 3, 1 / 3, 1 / 3),
}

CLASSIFICATION_PRIMARY_ORDER = [
    "Elite Game Changer",
    "Strong Bench Contributor",
    "Comeback Specialist",
    "Offensive Spark",
    "Defensive Closer",
    "Substitute-Specific Performer",
    "Starter-Caliber Contributor",
    "Reliable Bench Contributor",
    "Small-Sample Watchlist",
    "Insufficient Evidence",
]

CAUSAL_FORBIDDEN_PHRASES = [
    "caused the team to improve",
    "created exactly",
    "definitive tactical effect",
    "best player overall",
    "proven super-sub",
    "causal impact",
]

METRIC_DICTIONARY_SEED = [
    {
        "display_name": "Substitute Sporting Impact",
        "internal_field": "substitute_sporting_impact",
        "definition": "Position-group percentile of reliability-adjusted substitute Goals Added per 96.",
        "unit": "percentile 0-100",
        "source": "ASA Goals Added + FotMob role labels",
        "native_or_derived": "derived",
        "higher_better": True,
    },
    {
        "display_name": "Adjusted Team Impact After Entry",
        "internal_field": "adjusted_team_impact_after_entry",
        "definition": "Position-group percentile of ridge-adjusted association between substitute entry and post-entry team xG differential per 90.",
        "unit": "percentile 0-100",
        "source": "FotMob shotmap + context model",
        "native_or_derived": "derived",
        "higher_better": True,
    },
    {
        "display_name": "Positive Impact Frequency",
        "internal_field": "positive_impact_frequency",
        "definition": "Beta-binomial adjusted share of substitute appearances with positive adjusted post-entry residual.",
        "unit": "proportion 0-1 / percentile",
        "source": "Team-impact residuals",
        "native_or_derived": "derived",
        "higher_better": True,
    },
    {
        "display_name": "Substitute Advantage",
        "internal_field": "substitute_advantage",
        "definition": "Context-adjusted difference between stabilized substitute and starter impact rates.",
        "unit": "rate diff + percentile",
        "source": "ASA G+/96 by role",
        "native_or_derived": "derived",
        "higher_better": True,
    },
    {
        "display_name": "Bench Impact Score",
        "internal_field": "bench_impact_score",
        "definition": "Configured blend of SSI, ATI, and PIF percentiles.",
        "unit": "0-100",
        "source": "Derived components",
        "native_or_derived": "derived",
        "higher_better": True,
    },
]