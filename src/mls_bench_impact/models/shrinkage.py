from __future__ import annotations

import numpy as np
import pandas as pd


def reliability_weight(minutes: float, prior_strength: float = 450.0) -> float:
    minutes = max(float(minutes or 0), 0.0)
    return minutes / (minutes + prior_strength)


def shrink_rate(observed: float, prior: float, minutes: float, prior_strength: float = 450.0) -> float:
    w = reliability_weight(minutes, prior_strength)
    return w * observed + (1 - w) * prior


def position_context_priors(
    df: pd.DataFrame,
    value_col: str = "player_gplus_per96",
    minutes_col: str = "substitute_minutes",
    group_cols: list[str] | None = None,
) -> pd.DataFrame:
    group_cols = group_cols or ["position_group", "season"]
    rows = []
    for keys, g in df.dropna(subset=[value_col]).groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        w = g[minutes_col].fillna(0).clip(lower=0)
        if w.sum() <= 0:
            prior = float(g[value_col].mean())
        else:
            prior = float(np.average(g[value_col], weights=w))
        rec = dict(zip(group_cols, keys))
        rec["prior"] = prior
        rec["n"] = len(g)
        rows.append(rec)
    return pd.DataFrame(rows)


def apply_shrinkage(
    df: pd.DataFrame,
    value_col: str = "player_gplus_per96",
    minutes_col: str = "substitute_minutes",
    prior_strength: float = 450.0,
    group_cols: list[str] | None = None,
) -> pd.Series:
    group_cols = group_cols or ["position_group", "season"]
    priors = position_context_priors(df, value_col, minutes_col, group_cols)
    prior_map = priors.set_index(group_cols)["prior"].to_dict()
    global_prior = float(df[value_col].dropna().mean()) if df[value_col].notna().any() else 0.0

    adjusted = []
    for _, row in df.iterrows():
        key = tuple(row.get(c) for c in group_cols)
        if len(group_cols) == 1:
            key = key[0]
        prior = prior_map.get(key, global_prior)
        obs = row.get(value_col)
        if pd.isna(obs):
            adjusted.append(np.nan)
        else:
            adjusted.append(shrink_rate(float(obs), float(prior), float(row.get(minutes_col) or 0), prior_strength))
    return pd.Series(adjusted, index=df.index, name=f"adjusted_{value_col}")


def percentile_within_groups(values: pd.Series, groups: pd.Series) -> pd.Series:
    out = pd.Series(np.nan, index=values.index, dtype=float)
    for _, idx in groups.groupby(groups).groups.items():
        v = values.loc[idx]
        valid = v.dropna()
        if valid.empty:
            continue
        ranks = valid.rank(pct=True, method="average") * 100
        out.loc[ranks.index] = ranks
    return out