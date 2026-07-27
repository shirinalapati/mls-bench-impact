from __future__ import annotations

import numpy as np
import pandas as pd


def beta_binomial_adjust(successes: float, appearances: float, alpha: float = 2.0, beta: float = 2.0) -> float:
    appearances = max(float(appearances), 0.0)
    successes = max(float(successes), 0.0)
    return (successes + alpha) / (appearances + alpha + beta)


def compute_positive_impact_frequency(appearances: pd.DataFrame) -> pd.DataFrame:
    rows = []
    # Position priors first
    pos_prior = (
        appearances.groupby("position_group")["positive_appearance"].mean().to_dict()
        if "positive_appearance" in appearances.columns
        else {}
    )
    for player_id, g in appearances.groupby("player_id"):
        pos = (
            g["position_group"].mode().iloc[0]
            if len(g["position_group"].dropna())
            else "Central and defensive midfielders"
        )
        pos_rate = float(pos_prior.get(pos, 0.5) or 0.5)
        strength = 4.0
        alpha = pos_rate * strength
        beta = (1 - pos_rate) * strength
        succ = float(g["positive_appearance"].fillna(0).sum()) if "positive_appearance" in g else 0.0
        n = float(len(g))
        adj = beta_binomial_adjust(succ, n, alpha=max(alpha, 0.5), beta=max(beta, 0.5))
        rows.append(
            {
                "player_id": player_id,
                "position_group": pos,
                "positive_appearances": succ,
                "appearances": n,
                "raw_frequency": succ / n if n else np.nan,
                "positive_impact_frequency": adj,
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["positive_impact_frequency_percentile"] = out.groupby("position_group")[
        "positive_impact_frequency"
    ].rank(pct=True, method="average") * 100
    return out