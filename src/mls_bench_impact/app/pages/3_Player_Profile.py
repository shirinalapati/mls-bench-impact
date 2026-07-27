from __future__ import annotations

import plotly.express as px
import streamlit as st

from mls_bench_impact.app.data_access import load_appearances, load_rankings, meta_banner

st.set_page_config(page_title="Player Profile", layout="wide")
st.title("Player Profile")
st.caption(meta_banner())

period = st.sidebar.selectbox("Evaluation period", ["2025-2026", "2025", "2026"])
df = load_rankings(period)
if df.empty:
    st.warning("No data.")
    st.stop()
names = df.sort_values("overall_rank")["player_name"].tolist()
name = st.selectbox("Player", names)
row = df[df["player_name"] == name].iloc[0]
apps = load_appearances(row["player_id"])

st.subheader(row["player_name"])
m1, m2, m3, m4 = st.columns(4)
m1.metric("Bench Impact Score", f"{row['bench_impact_score']:.1f}" if row["bench_impact_score"] == row["bench_impact_score"] else "—")
m2.metric("SSI", f"{row['substitute_sporting_impact']:.1f}" if row["substitute_sporting_impact"] == row["substitute_sporting_impact"] else "—")
m3.metric("Team Impact", f"{row['adjusted_team_impact_after_entry']:.1f}" if row["adjusted_team_impact_after_entry"] == row["adjusted_team_impact_after_entry"] else "—")
m4.metric("Model Uncertainty", f"{row['model_uncertainty']:.1f}" if row["model_uncertainty"] == row["model_uncertainty"] else "—")

st.write(
    f"**{row['club']}** · {row['position_group']} · Age {row['age']} · "
    f"{int(row['substitute_appearances'])} sub apps / {row['substitute_minutes']:.0f} min · "
    f"Median entry {row['median_entry_minute']:.0f}' · {row['classification_primary']} · "
    f"Confidence {row['data_confidence']}"
)

st.markdown("### Why the player ranks here")
bits = []
if row["substitute_sporting_impact"] == row["substitute_sporting_impact"]:
    bits.append(f"Substitute Sporting Impact at the {row['substitute_sporting_impact']:.0f}th percentile within position.")
if row["adjusted_team_impact_after_entry"] == row["adjusted_team_impact_after_entry"]:
    bits.append(
        f"Estimated association with team post-entry xG differential ranks at the {row['adjusted_team_impact_after_entry']:.0f}th percentile."
    )
if row["positive_impact_frequency"] == row["positive_impact_frequency"]:
    bits.append(f"Adjusted positive-appearance frequency is {row['positive_impact_frequency']:.0%}.")
if row.get("substitute_advantage") == row.get("substitute_advantage"):
    bits.append(f"Substitute Advantage raw rate difference is {row['substitute_advantage']:.3f} G+/96.")
else:
    bits.append("Substitute Advantage unavailable — insufficient starting sample." if (row.get("starts") or 0) < 6 else "")
bits.append(f"Sample: {int(row['substitute_appearances'])} appearances, {row['substitute_minutes']:.0f} minutes; Data Confidence={row['data_confidence']}.")
st.write(" ".join([b for b in bits if b]))

st.markdown("### Appearance history")
show = apps.sort_values("match_date", ascending=False)
st.dataframe(
    show[
        [
            c
            for c in [
                "match_date",
                "opponent",
                "home_away",
                "entry_minute",
                "score_state_at_entry",
                "final_score_for",
                "final_score_against",
                "substitute_minutes",
                "player_gplus_per96",
                "post_entry_change",
                "positive_appearance",
                "simultaneous_sub_count",
                "tactical_situation",
            ]
            if c in show.columns
        ]
    ],
    use_container_width=True,
    hide_index=True,
)

st.markdown("### Context splits")
if len(apps):
    for split_col, title in [
        ("score_state_simple", "Score state"),
        ("entry_timing_category", "Entry timing"),
        ("home_away", "Home/Away"),
    ]:
        g = apps.groupby(split_col).agg(apps=("appearance_id", "count"), minutes=("substitute_minutes", "sum"), mean_gplus=("player_gplus_per96", "mean"), mean_team=("post_entry_change", "mean")).reset_index()
        g["warning"] = g["apps"].lt(4).map({True: "Small sample", False: ""})
        st.write(f"**{title}**")
        st.dataframe(g, use_container_width=True, hide_index=True)

    fig = px.histogram(apps, x="adjusted_post_entry_residual" if "adjusted_post_entry_residual" in apps and apps["adjusted_post_entry_residual"].notna().any() else "post_entry_change", nbins=20, title="Appearance-level adjusted effects")
    st.plotly_chart(fig, use_container_width=True)

st.markdown("### Starter comparison")
st.write(
    f"Starts: {int(row.get('starts') or 0)} / {float(row.get('starting_minutes') or 0):.0f} min · "
    f"Substitute Advantage: {row.get('substitute_advantage') if row.get('substitute_advantage') == row.get('substitute_advantage') else 'unavailable'}"
)