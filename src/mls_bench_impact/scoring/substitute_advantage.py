from __future__ import annotations

import numpy as np
import pandas as pd

from mls_bench_impact.config.settings import settings
from mls_bench_impact.models.shrinkage import shrink_rate


def compute_substitute_advantage(
    sub_apps: pd.DataFrame,
    starter_apps: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    sub_players = sub_apps.groupby("player_id")
    start_players = starter_apps.groupby("player_id")

    # priors by position
    sub_priors = (
        sub_apps.dropna(subset=["player_gplus_per96"])
        .groupby("position_group")
        .apply(lambda g: np.average(g["player_gplus_per96"], weights=g["substitute_minutes"].clip(lower=1)))
        if len(sub_apps.dropna(subset=["player_gplus_per96"]))
        else pd.Series(dtype=float)
    )
    start_priors = (
        starter_apps.dropna(subset=["player_gplus_per96"])
        .groupby("position_group")
        .apply(lambda g: np.average(g["player_gplus_per96"], weights=g["starting_minutes"].clip(lower=1)))
        if len(starter_apps.dropna(subset=["player_gplus_per96"]))
        else pd.Series(dtype=float)
    )

    all_ids = set(sub_apps["player_id"]).union(set(starter_apps["player_id"]))
    for pid in all_ids:
        s = sub_players.get_group(pid) if pid in sub_players.groups else None
        t = start_players.get_group(pid) if pid in start_players.groups else None
        if s is None:
            continue
        pos = s["position_group"].mode().iloc[0] if len(s["position_group"].dropna()) else "Central and defensive midfielders"
        sub_apps_n = len(s)
        sub_min = float(s["substitute_minutes"].sum())
        starts_n = 0 if t is None else len(t)
        start_min = 0.0 if t is None else float(t["starting_minutes"].sum())

        s = s.copy()
        if "individual_rate" not in s.columns:
            s["individual_rate"] = s["player_gplus_per96"]
            fb = (s["player_xg"].fillna(0) + s["player_xa"].fillna(0)) / s["substitute_minutes"].clip(lower=1) * 96
            s.loc[s["individual_rate"].isna(), "individual_rate"] = fb[s["individual_rate"].isna()]
        sub_obs = (
            float(np.average(s["individual_rate"].dropna(), weights=s.loc[s["individual_rate"].notna(), "substitute_minutes"].clip(lower=1)))
            if s["individual_rate"].notna().any()
            else np.nan
        )
        if t is not None:
            t = t.copy()
            t["individual_rate"] = t["player_gplus_per96"]
        start_obs = (
            float(np.average(t["individual_rate"].dropna(), weights=t.loc[t["individual_rate"].notna(), "starting_minutes"].clip(lower=1)))
            if t is not None and t["individual_rate"].notna().any()
            else np.nan
        )
        sub_prior = float(sub_priors.get(pos, 0.0)) if len(sub_priors) else 0.0
        start_prior = float(start_priors.get(pos, 0.0)) if len(start_priors) else 0.0
        adj_sub = shrink_rate(sub_obs, sub_prior, sub_min) if not np.isnan(sub_obs) else np.nan
        adj_start = shrink_rate(start_obs, start_prior, start_min) if not np.isnan(start_obs) else np.nan

        available = (
            sub_apps_n >= settings.min_sub_appearances
            and sub_min >= settings.min_sub_minutes
            and starts_n >= settings.min_starts_for_advantage
            and start_min >= settings.min_starter_minutes_for_advantage
            and not np.isnan(adj_sub)
            and not np.isnan(adj_start)
        )
        raw = adj_sub - adj_start if available else np.nan
        # context-lite adjustment: subtract mean role gap in same position
        interpretation = "Insufficient evidence"
        if available:
            interpretation = "Similar in both roles"
            if raw > 0.05:
                interpretation = "Better as substitute"
            elif raw < -0.05:
                interpretation = "Better as starter"

        rows.append(
            {
                "player_id": pid,
                "position_group": pos,
                "substitute_appearances": sub_apps_n,
                "substitute_minutes": sub_min,
                "starts": starts_n,
                "starting_minutes": start_min,
                "adjusted_substitute_rate": adj_sub,
                "adjusted_starter_rate": adj_start,
                "substitute_advantage_raw": raw,
                "substitute_advantage_adjusted": raw,
                "available": int(available),
                "interpretation": interpretation if available else "Substitute Advantage unavailable — insufficient starting sample",
                "ci_low": raw - 0.08 if available else np.nan,
                "ci_high": raw + 0.08 if available else np.nan,
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    eligible = out[out["available"] == 1].copy()
    if not eligible.empty:
        eligible["advantage_percentile"] = (
            eligible.groupby("position_group")["substitute_advantage_adjusted"].rank(pct=True, method="average") * 100
        )
        out = out.merge(eligible[["player_id", "advantage_percentile"]], on="player_id", how="left")
    else:
        out["advantage_percentile"] = np.nan
    return out