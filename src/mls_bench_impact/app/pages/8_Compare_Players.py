from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from mls_bench_impact.app.data_access import load_appearances, load_rankings, meta_banner

st.set_page_config(page_title="Compare Players", layout="wide")
st.title("Compare Players")
st.caption(meta_banner())

period = st.sidebar.selectbox("Evaluation period", ["2025-2026", "2025", "2026"])
df = load_rankings(period)
if df.empty:
    st.warning("No data.")
    st.stop()

options = df.sort_values("overall_rank")["player_name"].tolist()
picks = st.multiselect("Select 2–4 players", options, default=options[:2] if len(options) >= 2 else options)
if not (2 <= len(picks) <= 4):
    st.info("Select between two and four players.")
    st.stop()

comp = df[df["player_name"].isin(picks)].copy()
if comp["position_group"].nunique() > 1:
    st.warning("Comparing different position groups — percentiles are position-internal and not directly interchangeable.")

score_cols = [
    "bench_impact_score",
    "substitute_sporting_impact",
    "adjusted_team_impact_after_entry",
    "positive_impact_frequency_percentile",
    "substitute_advantage_percentile",
]
long = comp.melt(id_vars=["player_name", "position_group"], value_vars=[c for c in score_cols if c in comp.columns], var_name="metric", value_name="value")
fig = px.bar(long, x="metric", y="value", color="player_name", barmode="group", title="0–100 scores")
st.plotly_chart(fig, use_container_width=True)

comp["model_confidence"] = 100 - comp["model_uncertainty"]
st.dataframe(
    comp[
        [
            c
            for c in [
                "player_name",
                "club",
                "position_group",
                "bench_impact_score",
                "substitute_sporting_impact",
                "adjusted_team_impact_after_entry",
                "positive_impact_frequency",
                "substitute_advantage",
                "substitute_appearances",
                "substitute_minutes",
                "median_entry_minute",
                "data_confidence",
                "model_confidence",
            ]
            if c in comp.columns
        ]
    ],
    use_container_width=True,
    hide_index=True,
)

# raw sub vs starter differences
fig2 = go.Figure()
for _, r in comp.iterrows():
    fig2.add_trace(go.Bar(name=r["player_name"], x=["Substitute Advantage raw"], y=[r.get("substitute_advantage")]))
fig2.update_layout(barmode="group", title="Raw substitute-versus-starter differences")
st.plotly_chart(fig2, use_container_width=True)

apps = load_appearances()
apps = apps[apps["player_id"].isin(comp["player_id"])]
if len(apps):
    fig3 = px.histogram(apps, x="entry_minute", color="player_name", barmode="overlay", title="Appearance entry-minute distribution")
    st.plotly_chart(fig3, use_container_width=True)