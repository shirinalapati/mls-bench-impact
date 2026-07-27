from __future__ import annotations

import streamlit as st

from mls_bench_impact.app.data_access import load_match_detail, load_matches, meta_banner

st.set_page_config(page_title="Match Explorer", layout="wide")
st.title("Match Explorer")
st.caption(meta_banner())

season = st.sidebar.selectbox("Season", ["2026", "2025"])
matches = load_matches(season)
if matches.empty:
    st.warning("No bridged matches yet.")
    st.stop()

matches["label"] = matches["match_date"] + " · " + matches["home_team"] + " vs " + matches["away_team"]
label = st.selectbox("Match", matches["label"].tolist())
m = matches[matches["label"] == label].iloc[0]
detail = load_match_detail(m["match_id"])

st.subheader(f"{m['home_team']} {m['home_score']}–{m['away_score']} {m['away_team']}")
st.write(f"Date {m['match_date']} · Expanded minutes {m['expanded_minutes']} · Knockout={bool(m['is_knockout'])}")

st.markdown("### Timeline events")
events = detail["events"]
st.dataframe(events, use_container_width=True, hide_index=True)

st.markdown("### Substitutions")
subs = detail["substitutions"]
if len(subs) and (subs["simultaneous_sub_count"] >= 2).any():
    st.warning("One or more simultaneous multi-player substitutions — attribution confidence is reduced.")
st.dataframe(subs, use_container_width=True, hide_index=True)

st.markdown("### Player intervals")
st.dataframe(detail["intervals"], use_container_width=True, hide_index=True)

st.markdown("### Post-entry contributions")
st.dataframe(detail["appearances"], use_container_width=True, hide_index=True)