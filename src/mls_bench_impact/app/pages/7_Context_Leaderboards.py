from __future__ import annotations

import streamlit as st

from mls_bench_impact.app.data_access import load_advantage, load_appearances, load_rankings, meta_banner

st.set_page_config(page_title="Context Leaderboards", layout="wide")
st.title("Context Leaderboards")
st.caption(meta_banner())

period = st.selectbox("Evaluation period", ["2025-2026", "2025", "2026"])
rankings = load_rankings(period)
apps = load_appearances()
adv = load_advantage(period)
if rankings.empty:
    st.warning("No data.")
    st.stop()

board = st.selectbox(
    "Leaderboard",
    [
        "Best while trailing",
        "Best while tied",
        "Best while leading",
        "Best early substitutes",
        "Best late substitutes",
        "Best attacking sparks",
        "Best defensive closers",
        "Highest Positive Impact Frequency",
        "Strongest Substitute Advantage",
        "Best young substitutes",
        "Best veteran substitutes",
        "Small-sample watchlist",
    ],
)

MIN_APPS = 5
MIN_MIN = 90


def context_board(mask, value_col="post_entry_change"):
    g = apps.loc[mask].groupby("player_id").agg(apps=("appearance_id", "count"), minutes=("substitute_minutes", "sum"), value=(value_col, "mean")).reset_index()
    g = g[(g["apps"] >= MIN_APPS) & (g["minutes"] >= MIN_MIN)]
    g = g.merge(rankings[["player_id", "player_name", "club", "position_group", "bench_impact_score", "data_confidence"]], on="player_id", how="left")
    return g.sort_values("value", ascending=False).head(40)


if board == "Best while trailing":
    out = context_board(apps["score_state_simple"] == "trailing")
elif board == "Best while tied":
    out = context_board(apps["score_state_simple"] == "tied")
elif board == "Best while leading":
    out = context_board(apps["score_state_simple"] == "leading")
elif board == "Best early substitutes":
    out = context_board(apps["entry_timing_category"].isin(["early", "emergency_early", "halftime"]))
elif board == "Best late substitutes":
    out = context_board(apps["entry_timing_category"] == "late")
elif board == "Best attacking sparks":
    out = rankings[rankings["classification_tags"].fillna("").str.contains("Offensive Spark")].sort_values("bench_impact_score", ascending=False)
elif board == "Best defensive closers":
    out = rankings[rankings["classification_tags"].fillna("").str.contains("Defensive Closer")].sort_values("bench_impact_score", ascending=False)
elif board == "Highest Positive Impact Frequency":
    out = rankings[rankings["overall_rank"].notna()].sort_values("positive_impact_frequency", ascending=False).head(40)
elif board == "Strongest Substitute Advantage":
    out = adv[adv["available"] == 1].sort_values("advantage_percentile", ascending=False).head(40)
elif board == "Best young substitutes":
    out = rankings[(rankings["age"] <= 23) & (rankings["overall_rank"].notna())].sort_values("bench_impact_score", ascending=False).head(40)
elif board == "Best veteran substitutes":
    out = rankings[(rankings["age"] >= 30) & (rankings["overall_rank"].notna())].sort_values("bench_impact_score", ascending=False).head(40)
else:
    out = rankings[rankings["classification_primary"] == "Small-Sample Watchlist"].sort_values("bench_impact_score", ascending=False)

st.dataframe(out, use_container_width=True, hide_index=True)
st.caption(f"Context boards require at least {MIN_APPS} appearances and {MIN_MIN} minutes in-context where applicable.")