from __future__ import annotations

import plotly.express as px
import streamlit as st

from mls_bench_impact.app.data_access import load_advantage, meta_banner

st.set_page_config(page_title="Substitute vs Starter", layout="wide")
st.title("Substitute vs Starter")
st.caption(meta_banner())

period = st.sidebar.selectbox("Evaluation period", ["2025-2026", "2025", "2026"])
df = load_advantage(period)
if df.empty:
    st.warning("No data.")
    st.stop()

cat = st.sidebar.multiselect(
    "Categories",
    ["Better as substitute", "Similar in both roles", "Better as starter", "Insufficient evidence"],
    default=["Better as substitute", "Similar in both roles", "Better as starter"],
)
view = df.copy()
view["category"] = view["interpretation"].fillna("Insufficient evidence")
view.loc[view["available"] == 0, "category"] = "Insufficient evidence"
view = view[view["category"].isin(cat) | ((view["available"] == 0) & ("Insufficient evidence" in cat))]

st.dataframe(
    view[
        [
            c
            for c in [
                "player_name",
                "club",
                "position_group",
                "substitute_appearances",
                "substitute_minutes",
                "starts",
                "starting_minutes",
                "adjusted_substitute_rate",
                "adjusted_starter_rate",
                "substitute_advantage_raw",
                "advantage_percentile",
                "ci_low",
                "ci_high",
                "data_confidence",
                "interpretation",
            ]
            if c in view.columns
        ]
    ],
    use_container_width=True,
    hide_index=True,
)

eligible = view[view["available"] == 1].dropna(subset=["adjusted_starter_rate", "adjusted_substitute_rate"])
if len(eligible):
    fig = px.scatter(
        eligible,
        x="adjusted_starter_rate",
        y="adjusted_substitute_rate",
        color="position_group",
        hover_name="player_name",
        title="Adjusted starter vs substitute impact",
    )
    lims = [
        float(min(eligible["adjusted_starter_rate"].min(), eligible["adjusted_substitute_rate"].min())),
        float(max(eligible["adjusted_starter_rate"].max(), eligible["adjusted_substitute_rate"].max())),
    ]
    fig.add_shape(type="line", x0=lims[0], y0=lims[0], x1=lims[1], y1=lims[1], line=dict(dash="dash"))
    st.plotly_chart(fig, use_container_width=True)

st.info("Players are not labeled 'better as substitute' from a raw rate difference alone — eligibility, shrinkage, and uncertainty intervals are required.")