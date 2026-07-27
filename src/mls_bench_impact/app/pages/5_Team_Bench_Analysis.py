from __future__ import annotations

import plotly.express as px
import streamlit as st

from mls_bench_impact.app.data_access import load_appearances, load_rankings, load_teams, meta_banner

st.set_page_config(page_title="Team Bench Analysis", layout="wide")
st.title("Team Bench Analysis")
st.caption(meta_banner())

period = st.sidebar.selectbox("Evaluation period", ["2025-2026", "2025", "2026"])
rankings = load_rankings(period)
teams = load_teams()
if rankings.empty:
    st.warning("No data.")
    st.stop()

club = st.selectbox("Club", sorted(rankings["club"].dropna().unique()))
team = rankings[rankings["club"] == club].copy()
apps = load_appearances()
apps = apps[apps["club"] == club]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Bench players", len(team))
c2.metric("Total bench minutes", f"{team['substitute_minutes'].sum():.0f}")
c3.metric("Median Bench Impact", f"{team['bench_impact_score'].median():.1f}" if team["bench_impact_score"].notna().any() else "—")
c4.metric("Most common entry'", f"{apps['entry_minute'].median():.0f}" if len(apps) else "—")

st.markdown("### Most impactful substitutes")
st.dataframe(
    team.sort_values("bench_impact_score", ascending=False)[
        ["player_name", "position_group", "substitute_appearances", "substitute_minutes", "bench_impact_score", "classification_primary", "data_confidence"]
    ],
    use_container_width=True,
    hide_index=True,
)

fig = px.bar(team.sort_values("bench_impact_score", ascending=False).head(15), x="player_name", y="bench_impact_score", title="Bench Impact by player")
st.plotly_chart(fig, use_container_width=True)

c1, c2 = st.columns(2)
c1.plotly_chart(px.histogram(apps, x="entry_minute", nbins=18, title="Entry-minute distribution"), use_container_width=True)
if len(apps):
    ss = apps.groupby("score_state_simple").size().reset_index(name="count")
    c2.plotly_chart(px.bar(ss, x="score_state_simple", y="count", title="Score-state usage"), use_container_width=True)

st.markdown("### Role notes")
st.write("**Offensive substitutes / defensive closers / comeback specialists** are classification tags, not coaching prescriptions.")
tagged = team[team["classification_tags"].fillna("").str.contains("Spark|Closer|Comeback|Starter-Caliber|without", case=False)]
st.dataframe(tagged[["player_name", "classification_primary", "classification_tags", "bench_impact_score"]], use_container_width=True, hide_index=True)

freq_low = team[(team["substitute_appearances"] >= 10) & (team["bench_impact_score"].fillna(0) < 40)]
st.markdown("### Frequently used without strong measurable impact")
st.caption("Cautious wording: low measurable association is not proof of coaching error.")
st.dataframe(freq_low[["player_name", "substitute_appearances", "substitute_minutes", "bench_impact_score", "data_confidence"]], use_container_width=True, hide_index=True)

starter_cal = team[team["classification_tags"].fillna("").str.contains("Starter-Caliber")]
st.markdown("### Players potentially deserving more starts")
st.caption("Based on strong substitute impact with starter performance equal or stronger — not a lineup mandate.")
st.dataframe(starter_cal[["player_name", "bench_impact_score", "substitute_advantage", "classification_tags"]], use_container_width=True, hide_index=True)