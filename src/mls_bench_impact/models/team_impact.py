from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

CONTEXT_COLS = [
    "entry_minute",
    "minutes_remaining",
    "score_difference_at_entry",
    "is_home",
    "team_strength",
    "opponent_strength",
    "simultaneous_sub_count",
    "pre_entry_xg_diff_per90",
]


def _design_matrix(df: pd.DataFrame, player_col: str = "player_id") -> tuple[pd.DataFrame, list[str]]:
    work = df.copy()
    work["minutes_remaining"] = (work.get("expanded_minutes", 96) - work["entry_minute"]).clip(lower=1)
    work["is_home"] = (work["home_away"] == "home").astype(float)
    work["team_strength"] = work["team_strength"].fillna(0)
    work["opponent_strength"] = work["opponent_strength"].fillna(0)
    work["simultaneous_sub_count"] = work["simultaneous_sub_count"].fillna(1)
    work["pre_entry_xg_diff_per90"] = work["pre_entry_xg_diff_per90"].fillna(0)
    work["score_difference_at_entry"] = work["score_difference_at_entry"].fillna(0)

    # one-hot limited contexts
    dummies = pd.get_dummies(
        work[["position_group", "season", "score_state_simple", "entry_timing_category", "red_card_state"]],
        dummy_na=True,
    )
    base = work[CONTEXT_COLS].astype(float)
    # player indicators — heavily regularized via ridge alpha
    players = pd.get_dummies(work[player_col], prefix="p")
    X = pd.concat([base, dummies, players], axis=1)
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0)
    return X, list(players.columns)


def fit_team_impact_model(df: pd.DataFrame, alpha: float = 50.0) -> dict[str, Any]:
    """Fit ridge model on post_entry_xg_diff_per90; return player effects + diagnostics."""
    data = df.dropna(subset=["post_entry_xg_diff_per90"]).copy()
    if len(data) < 50:
        return {"ok": False, "reason": "insufficient_rows", "player_effects": {}}

    y = data["post_entry_xg_diff_per90"].astype(float).values
    X, player_cols = _design_matrix(data)
    scaler = StandardScaler(with_mean=True, with_std=True)
    # scale non-player cols only
    non_player = [c for c in X.columns if c not in player_cols]
    Xs = X.copy()
    Xs[non_player] = scaler.fit_transform(X[non_player])

    model = Ridge(alpha=alpha, random_state=42)
    model.fit(Xs.values, y)
    coef = pd.Series(model.coef_, index=X.columns)
    player_effects = {c.replace("p_", "", 1): float(coef[c]) for c in player_cols}

    # residualized appearance outcome for PIF
    # prediction without player dummies
    coef_no_player = coef.copy()
    coef_no_player[player_cols] = 0
    baseline = Xs.values @ coef_no_player.values + model.intercept_
    residuals = y - baseline
    data = data.copy()
    data["adjusted_post_entry_residual"] = residuals
    data["positive_appearance"] = (residuals > 0).astype(int)

    # simple bootstrap CI for player effects (resample matches)
    rng = np.random.default_rng(42)
    boot = {pid: [] for pid in player_effects}
    n_boot = 40 if len(data) > 200 else 20
    idx = np.arange(len(data))
    for _ in range(n_boot):
        sample_idx = rng.choice(idx, size=len(idx), replace=True)
        Xs_b = Xs.iloc[sample_idx]
        y_b = y[sample_idx]
        m = Ridge(alpha=alpha, random_state=42)
        m.fit(Xs_b.values, y_b)
        c = pd.Series(m.coef_, index=X.columns)
        for pc in player_cols:
            boot[pc.replace("p_", "", 1)].append(float(c[pc]))

    ci = {}
    for pid, vals in boot.items():
        if not vals:
            continue
        ci[pid] = (float(np.percentile(vals, 5)), float(np.percentile(vals, 95)))

    return {
        "ok": True,
        "player_effects": player_effects,
        "ci": ci,
        "appearance_frame": data,
        "alpha": alpha,
        "n": int(len(data)),
        "r2": float(model.score(Xs.values, y)),
    }


def effects_to_percentiles(effects: dict[str, float], position_map: dict[str, str]) -> dict[str, float]:
    df = pd.DataFrame({"player_id": list(effects.keys()), "effect": list(effects.values())})
    df["position_group"] = df["player_id"].map(position_map)
    out = {}
    for _, g in df.groupby("position_group"):
        ranks = g["effect"].rank(pct=True, method="average") * 100
        for pid, val in zip(g["player_id"], ranks, strict=False):
            out[pid] = float(val)
    return out