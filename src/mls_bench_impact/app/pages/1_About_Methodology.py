from __future__ import annotations

import pandas as pd
import streamlit as st

from mls_bench_impact import MODEL_VERSION
from mls_bench_impact.app.data_access import meta_banner
from mls_bench_impact.config.constants import METRIC_DICTIONARY_SEED
from mls_bench_impact.config.settings import settings

st.set_page_config(page_title="About & Methodology", layout="wide")
st.title("About & Methodology")
st.caption(meta_banner())

st.markdown("## Research questions")
st.write(
    """
1. Which MLS players provide the greatest measurable impact when entering matches as substitutes,
   after accounting for playing time, position, entry minute, score state, opponent strength,
   team strength, and substitution context?
2. Which players perform meaningfully better as substitutes than they do as starters?
"""
)

with st.expander("What qualifies as a substitute appearance", expanded=True):
    st.write(
        """
A substitute appearance is an on-field interval that begins with a substitution event (player enters)
and ends at the earliest of: being substituted off, a red-card dismissal, or match end
(`expanded_minutes`). Unused bench players are excluded. Goalkeepers are excluded from production rankings.
"""
    )

with st.expander("Data sources and cutoffs"):
    st.write(f"- American Soccer Analysis API — game-level Goals Added and xG (cutoff {settings.data_cutoff_date})")
    st.write("- FotMob match pages — lineups, substitutions, score state, cards, shotmap xG")
    st.write("- MLS first team only; no NEXT Pro / USL / synthetic players")

with st.expander("Match interval construction"):
    st.write(
        """
For every match we identify starters and substitutes, record substitution timestamps (including stoppage),
build player on-field intervals, capture score and red-card state at entry, flag simultaneous substitutions,
and assign team shotmap xG to pre- and post-entry windows.
"""
    )

with st.expander("Score definitions (formulas)", expanded=True):
    st.latex(r"w_i = \frac{m_i}{m_i + m_0},\quad m_0=450")
    st.latex(r"\tilde{r}_i = w_i r_i + (1-w_i)\mu_{pos,season}")
    st.latex(r"SSI_i = \mathrm{percentile}_{pos}(\tilde{r}_i^{G+/96})")
    st.write("Adjusted Team Impact After Entry = position percentile of ridge player effect on post-entry team xG diff/90.")
    st.latex(r"PIF = \frac{s+\alpha}{n+\alpha+\beta}")
    st.latex(r"BIS = 0.50\cdot SSI + 0.30\cdot ATI + 0.20\cdot PIF\%")
    st.caption("Weights are expert-configured, not learned.")

with st.expander("Eligibility, confidence, uncertainty"):
    st.write(
        f"""
Official ranking thresholds (starting): ≥{settings.min_sub_appearances} substitute appearances and
≥{settings.min_sub_minutes} substitute minutes. Below-threshold players appear on the Small-Sample Watchlist.
Data Confidence labels sample/coverage quality (not player quality). Model Uncertainty is 0–100 (lower better).
"""
    )

with st.expander("Causal interpretation warning", expanded=True):
    st.warning(
        "These metrics estimate associations using public data. They do not prove that a player caused "
        "team improvement, created an exact goal value, or is a definitive tactical super-sub."
    )

st.markdown("## Metric Dictionary")
q = st.text_input("Search metrics")
md = pd.DataFrame(METRIC_DICTIONARY_SEED)
if q:
    md = md[md.apply(lambda r: q.lower() in str(r.values).lower(), axis=1)]
st.dataframe(md, use_container_width=True, hide_index=True)
st.caption(f"Model version {MODEL_VERSION}")