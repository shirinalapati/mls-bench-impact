from __future__ import annotations

import streamlit as st

from mls_bench_impact.app.data_access import load_rankings, meta_banner
from mls_bench_impact.config.settings import settings

st.set_page_config(
    page_title="MLS Bench Impact",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
    html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
    h1, h2, h3 { font-family: 'Space Grotesk', sans-serif; letter-spacing: -0.02em; }
    .stApp {
      background:
        radial-gradient(1200px 600px at 10% -10%, rgba(15, 118, 110, 0.18), transparent 55%),
        radial-gradient(900px 500px at 90% 0%, rgba(180, 83, 9, 0.12), transparent 50%),
        linear-gradient(180deg, #f7f3ec 0%, #eef2f0 45%, #f8faf9 100%);
    }
    .hero-brand { font-size: 3rem; font-weight: 700; color: #0f3d38; margin-bottom: 0.2rem; }
    .hero-sub { font-size: 1.25rem; color: #1f2937; max-width: 40rem; }
    .meta { color: #4b5563; font-size: 0.9rem; margin-top: 0.75rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="hero-brand">MLS Bench Impact</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hero-sub">Identifying Major League Soccer’s most effective substitutes with context-aware, sample-size-aware public-data metrics.</div>',
    unsafe_allow_html=True,
)
st.markdown(f'<div class="meta">{meta_banner()}</div>', unsafe_allow_html=True)

st.divider()
c1, c2, c3 = st.columns(3)
try:
    rankings = load_rankings("2025-2026")
    ranked = rankings[rankings["overall_rank"].notna()]
    c1.metric("Ranked substitutes", f"{len(ranked):,}")
    c2.metric("Evaluation period", "2025–2026 YTD")
    if len(ranked):
        top = ranked.sort_values("overall_rank").iloc[0]
        c3.metric("Current #1", top["player_name"])
    else:
        c3.metric("Current #1", "Run pipeline")
except Exception:
    c1.metric("Ranked substitutes", "—")
    c2.metric("Database", "Not built")
    c3.metric("Action", "make all")

st.markdown("### Research questions")
st.write(
    "1. Which MLS players provide the greatest **measurable** impact when entering as substitutes after accounting for minutes, position, entry minute, score state, opponent/team strength, and substitution context?"
)
st.write(
    "2. Which players perform meaningfully better as substitutes than as starters?"
)

st.markdown("### Navigate")
st.write(
    "Use the sidebar pages: About & Methodology · Rankings · Player Profile · Substitute vs Starter · Team Bench Analysis · Match Explorer · Context Leaderboards · Compare Players."
)
st.info(
    "Scores estimate associations from public data. They do **not** claim that a substitution caused team improvement."
)
st.caption(f"DB: `{settings.db_path}`")