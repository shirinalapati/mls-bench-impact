from __future__ import annotations

import plotly.express as px
import streamlit as st

from mls_bench_impact.app.data_access import load_rankings, meta_banner

st.set_page_config(page_title="Bench Impact Rankings", layout="wide")
st.title("Bench Impact Rankings")
st.caption(meta_banner())

period = st.sidebar.selectbox("Evaluation period", ["2025-2026", "2025", "2026"], index=0)
df = load_rankings(period)
if df.empty:
    st.warning("No scores yet. Run `make pipeline`.")
    st.stop()

# Fixed production scores — filters only change visibility
st.sidebar.markdown("### Display filters")
clubs = ["All"] + sorted([c for c in df["club"].dropna().unique()])
club = st.sidebar.selectbox("Club", clubs)
positions = ["All"] + sorted([c for c in df["position_group"].dropna().unique()])
pos = st.sidebar.selectbox("Position group", positions)
min_apps = st.sidebar.number_input("Min appearances (display)", 0, 50, 8)
min_mins = st.sidebar.number_input("Min minutes (display)", 0, 2000, 180)
confs = st.sidebar.multiselect("Data Confidence", ["High", "Medium", "Low", "Insufficient"], default=["High", "Medium", "Low"])
classes = ["All"] + sorted([c for c in df["classification_primary"].dropna().unique()])
klass = st.sidebar.selectbox("Classification", classes)
age_min, age_max = st.sidebar.slider("Age", 15, 45, (15, 45))

view = df.copy()
# official ranked by default
show_watch = st.sidebar.checkbox("Include Small-Sample Watchlist", value=False)
if not show_watch:
    view = view[view["overall_rank"].notna()]
view = view[view["substitute_appearances"] >= min_apps]
view = view[view["substitute_minutes"] >= min_mins]
if club != "All":
    view = view[view["club"] == club]
if pos != "All":
    view = view[view["position_group"] == pos]
if confs:
    view = view[view["data_confidence"].isin(confs)]
if klass != "All":
    view = view[view["classification_primary"] == klass]
view = view[(view["age"].fillna(25) >= age_min) & (view["age"].fillna(25) <= age_max)]
view = view.sort_values(["overall_rank", "bench_impact_score"], ascending=[True, False])
view.insert(0, "display_rank", range(1, len(view) + 1))

cols = [
    "display_rank",
    "overall_rank",
    "position_rank",
    "player_name",
    "club",
    "position_group",
    "age",
    "substitute_appearances",
    "substitute_minutes",
    "median_entry_minute",
    "substitute_sporting_impact",
    "adjusted_team_impact_after_entry",
    "positive_impact_frequency",
    "bench_impact_score",
    "data_confidence",
    "model_uncertainty",
    "classification_primary",
]
st.dataframe(view[[c for c in cols if c in view.columns]], use_container_width=True, hide_index=True)
st.caption("Display filters do not alter stored Bench Impact Scores or fixed overall/position ranks.")

c1, c2 = st.columns(2)
fig = px.scatter(
    view.dropna(subset=["bench_impact_score"]),
    x="substitute_minutes",
    y="bench_impact_score",
    size="substitute_appearances",
    color="position_group",
    hover_name="player_name",
    hover_data=["club", "median_entry_minute", "data_confidence"],
    title="Bench Impact vs Substitute Minutes",
)
c1.plotly_chart(fig, use_container_width=True)
fig2 = px.scatter(
    view.dropna(subset=["substitute_sporting_impact", "adjusted_team_impact_after_entry"]),
    x="substitute_sporting_impact",
    y="adjusted_team_impact_after_entry",
    color="classification_primary",
    hover_name="player_name",
    title="Individual vs Team Impact",
)
fig2.add_hline(y=50, line_dash="dot")
fig2.add_vline(x=50, line_dash="dot")
c2.plotly_chart(fig2, use_container_width=True)