from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from mls_bench_impact import MODEL_VERSION
from mls_bench_impact.config.constants import BENCH_IMPACT_WEIGHTS
from mls_bench_impact.config.settings import settings
from mls_bench_impact.db.database import db_session


def _record(conn, test_name: str, component: str, metric_name: str, value: float, passed: bool, details: dict):
    conn.execute(
        """
        INSERT INTO validation_results(model_run_id, test_name, component, metric_name, metric_value, passed, details_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            None,
            test_name,
            component,
            metric_name,
            value,
            1 if passed else 0,
            json.dumps(details),
            datetime.now(timezone.utc).isoformat(),
        ),
    )


def run_validation(period: str = "2025-2026") -> dict:
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    with db_session() as conn:
        scores = pd.read_sql_query(
            "SELECT * FROM player_bench_scores WHERE evaluation_period=?",
            conn,
            params=(period,),
        )
        apps = pd.read_sql_query("SELECT * FROM substitute_appearances", conn)
        official = scores[scores["overall_rank"].notna()].copy()

        # split-half reliability on SSI via random split of appearances
        if not apps.empty and not official.empty:
            rng = np.random.default_rng(42)
            apps = apps.copy()
            apps["_half"] = rng.integers(0, 2, size=len(apps))
            half = apps.groupby(["player_id", "_half"])["player_gplus_per96"].mean().unstack()
            if half.shape[1] == 2:
                corr = float(half.corr().iloc[0, 1]) if half.dropna().shape[0] > 5 else np.nan
            else:
                corr = np.nan
            results["split_half_corr"] = corr
            _record(conn, "split_half_reliability", "SSI", "pearson", corr if corr == corr else -1, bool(corr == corr and corr > 0.1), {"n": int(half.dropna().shape[0])})

        # year-to-year if both seasons present
        s25 = scores[scores["evaluation_period"] == period]  # placeholder
        y25 = pd.read_sql_query("SELECT player_id, bench_impact_score FROM player_bench_scores WHERE evaluation_period='2025'", conn)
        y26 = pd.read_sql_query("SELECT player_id, bench_impact_score FROM player_bench_scores WHERE evaluation_period='2026'", conn)
        yy = y25.merge(y26, on="player_id", suffixes=("_25", "_26")).dropna()
        yoy = float(yy["bench_impact_score_25"].corr(yy["bench_impact_score_26"])) if len(yy) > 5 else np.nan
        results["yoy_corr"] = yoy
        _record(conn, "year_to_year_correlation", "BIS", "pearson", yoy if yoy == yoy else -1, bool(yoy == yoy), {"n": int(len(yy))})

        # weight sensitivity rank stability
        if not official.empty:
            base_rank = official.set_index("player_id")["overall_rank"]
            stabilities = {}
            for name, (w1, w2, w3) in BENCH_IMPACT_WEIGHTS.items():
                tmp = official.copy()
                ssi = tmp["substitute_sporting_impact"]
                ati = tmp["adjusted_team_impact_after_entry"]
                pif = tmp["positive_impact_frequency_percentile"]
                # renormalize if missing
                scores_alt = []
                for i in tmp.index:
                    vals = [("ssi", ssi.loc[i], w1), ("ati", ati.loc[i], w2), ("pif", pif.loc[i], w3)]
                    avail = [(v, w) for _, v, w in vals if pd.notna(v)]
                    if len(avail) < 2:
                        scores_alt.append(np.nan)
                    else:
                        ws = sum(w for _, w in avail)
                        scores_alt.append(sum(v * w / ws for v, w in avail))
                tmp["alt"] = scores_alt
                tmp = tmp.dropna(subset=["alt"]).sort_values("alt", ascending=False)
                tmp["alt_rank"] = np.arange(1, len(tmp) + 1)
                merged = tmp.set_index("player_id")["alt_rank"].to_frame().join(base_rank, how="inner")
                rho = float(merged["alt_rank"].corr(merged["overall_rank"], method="spearman")) if len(merged) > 5 else np.nan
                stabilities[name] = rho
                _record(conn, "weight_sensitivity", "ranking", name, rho if rho == rho else -1, bool(rho == rho and rho > 0.8), {})
            results["weight_stability"] = stabilities

            # top-10 stability under excluding simultaneous triple subs
            apps_f = apps[apps["simultaneous_sub_count"].fillna(1) < 3]
            keep = set(apps_f["player_id"])
            filtered = official[official["player_id"].isin(keep)].sort_values("bench_impact_score", ascending=False)
            top10 = set(official.nsmallest(10, "overall_rank")["player_id"])
            top10_f = set(filtered.head(10)["player_id"])
            jacc = len(top10 & top10_f) / len(top10 | top10_f) if top10 else np.nan
            results["top10_jaccard_no_triple"] = jacc
            _record(conn, "top10_stability_exclude_triple_subs", "ranking", "jaccard", jacc if jacc == jacc else -1, bool(jacc == jacc and jacc >= 0.4), {})

        # baselines comparison table
        if not apps.empty:
            base = apps.groupby("player_id").agg(
                goals=("player_xg", "sum"),  # proxy unavailable for goals; use xg
                apps=("appearance_id", "count"),
                minutes=("substitute_minutes", "sum"),
                gplus=("player_gplus", "sum"),
                gplus96=("player_gplus_per96", "mean"),
                gd=("post_entry_change", "mean"),
            ).reset_index()
            base = base.merge(official[["player_id", "overall_rank", "bench_impact_score"]], on="player_id", how="inner")
            results["baseline_corr_gplus96"] = float(base["gplus96"].corr(base["bench_impact_score"])) if base["gplus96"].notna().sum() > 5 else np.nan
            _record(
                conn,
                "baseline_vs_model",
                "BIS",
                "corr_raw_gplus96",
                results["baseline_corr_gplus96"] if results["baseline_corr_gplus96"] == results["baseline_corr_gplus96"] else -1,
                True,
                {"note": "Model should correlate but not collapse to raw G+/96"},
            )

        # HTML reports
        html = ["<html><head><title>Model Validation</title></head><body>"]
        html.append("<h1>MLS Bench Impact — Model Validation</h1>")
        html.append(f"<p>Model version {MODEL_VERSION} | Period {period}</p>")
        html.append("<ul>")
        for k, v in results.items():
            html.append(f"<li><b>{k}</b>: {v}</li>")
        html.append("</ul>")
        html.append("<p>Associations only. Not causal substitution effects.</p>")
        html.append("</body></html>")
        (settings.reports_dir / "model_validation.html").write_text("\n".join(html), encoding="utf-8")

        stab_html = ["<html><body><h1>Ranking Stability</h1>"]
        stab_html.append(f"<pre>{json.dumps(results.get('weight_stability', {}), indent=2)}</pre>")
        stab_html.append(f"<p>Top10 Jaccard excluding triple subs: {results.get('top10_jaccard_no_triple')}</p>")
        stab_html.append("</body></html>")
        (settings.reports_dir / "ranking_stability.html").write_text("\n".join(stab_html), encoding="utf-8")

    return results