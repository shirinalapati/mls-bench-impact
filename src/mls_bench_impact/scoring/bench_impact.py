from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pandas as pd

from mls_bench_impact import MODEL_VERSION
from mls_bench_impact.config.settings import settings
from mls_bench_impact.models.positive_frequency import compute_positive_impact_frequency
from mls_bench_impact.models.shrinkage import apply_shrinkage, percentile_within_groups
from mls_bench_impact.models.team_impact import effects_to_percentiles, fit_team_impact_model
from mls_bench_impact.scoring.confidence import classify_player, data_confidence, model_uncertainty
from mls_bench_impact.scoring.substitute_advantage import compute_substitute_advantage

PERIOD_FILTERS = {
    "2025": lambda s: s == "2025",
    "2026": lambda s: s == "2026",
    "2025-2026": lambda s: s in ("2025", "2026"),
}


def _load_appearances(conn, period: str) -> pd.DataFrame:
    df = pd.read_sql_query("SELECT * FROM substitute_appearances", conn)
    if df.empty:
        return df
    mask = df["season"].map(PERIOD_FILTERS[period])
    return df.loc[mask].copy()


def _load_starters(conn, period: str) -> pd.DataFrame:
    df = pd.read_sql_query("SELECT * FROM starter_appearances", conn)
    if df.empty:
        return df
    return df.loc[df["season"].map(PERIOD_FILTERS[period])].copy()


def _attach_strength(conn, apps: pd.DataFrame) -> pd.DataFrame:
    if apps.empty:
        return apps
    # team strength from ASA team xg expanding means approx: use average post-entry change baseline 0
    # simple strength: mean goal diff of team in period prior not available easily; use 0 filled with match xg if present
    apps = apps.copy()
    apps["team_strength"] = apps["team_strength"].fillna(0)
    apps["opponent_strength"] = apps["opponent_strength"].fillna(0)
    apps["expanded_minutes"] = 96
    # join match expanded minutes
    mm = pd.read_sql_query("SELECT match_id, expanded_minutes FROM matches", conn)
    apps = apps.merge(mm, on="match_id", how="left", suffixes=("", "_m"))
    apps["expanded_minutes"] = apps["expanded_minutes_m"].fillna(apps["expanded_minutes"])
    return apps


def compute_period_scores(conn, period: str = "2025-2026") -> pd.DataFrame:
    apps = _attach_strength(conn, _load_appearances(conn, period))
    starters = _load_starters(conn, period)
    if apps.empty:
        return pd.DataFrame()

    # exclude GK
    players = pd.read_sql_query("SELECT player_id, player_name, birth_date, position_group, is_goalkeeper FROM players", conn)
    apps = apps.merge(players[["player_id", "is_goalkeeper"]], on="player_id", how="left")
    apps = apps.loc[apps["is_goalkeeper"].fillna(0) == 0].copy()

    # Individual rate: prefer ASA G+/96; fall back to FotMob (xG+xA)/96 as documented alternative
    apps["individual_rate"] = apps["player_gplus_per96"]
    fallback = (apps["player_xg"].fillna(0) + apps["player_xa"].fillna(0)) / apps["substitute_minutes"].clip(lower=1) * 96
    apps.loc[apps["individual_rate"].isna() & apps["substitute_minutes"].gt(0), "individual_rate"] = fallback[
        apps["individual_rate"].isna() & apps["substitute_minutes"].gt(0)
    ]
    apps["adjusted_gplus_per96"] = apply_shrinkage(
        apps,
        value_col="individual_rate",
        minutes_col="substitute_minutes",
        prior_strength=settings.prior_strength_minutes,
    )

    # player-level observed aggregates
    agg = apps.groupby("player_id").agg(
        substitute_appearances=("appearance_id", "count"),
        substitute_minutes=("substitute_minutes", "sum"),
        median_entry_minute=("entry_minute", "median"),
        position_group=("position_group", lambda s: s.mode().iloc[0] if len(s.dropna()) else "Central and defensive midfielders"),
        team_id=("team_id", lambda s: s.mode().iloc[0] if len(s.dropna()) else None),
        observed_gplus_per96=("individual_rate", "mean"),
        adjusted_gplus_per96=("adjusted_gplus_per96", "mean"),
        coverage_gplus=("individual_rate", lambda s: float(s.notna().mean())),
        coverage_team=("post_entry_xg_diff_per90", lambda s: float(s.notna().mean())),
        simultaneous_rate=("simultaneous_sub_count", lambda s: float((s.fillna(1) >= 2).mean())),
        red_card_rate=("red_card_state", lambda s: float((s.fillna("none") != "none").mean())),
        seasons=("season", lambda s: ",".join(sorted(set(s)))),
    ).reset_index()

    # SSI percentile
    agg["substitute_sporting_impact"] = percentile_within_groups(agg["adjusted_gplus_per96"], agg["position_group"])

    # Team impact model
    model = fit_team_impact_model(apps)
    if model.get("ok"):
        pos_map = agg.set_index("player_id")["position_group"].to_dict()
        ati_pct = effects_to_percentiles(model["player_effects"], pos_map)
        agg["team_impact_point"] = agg["player_id"].map(model["player_effects"])
        agg["adjusted_team_impact_after_entry"] = agg["player_id"].map(ati_pct)
        ci = model.get("ci") or {}
        agg["team_impact_ci_low"] = agg["player_id"].map(lambda p: ci.get(p, (np.nan, np.nan))[0])
        agg["team_impact_ci_high"] = agg["player_id"].map(lambda p: ci.get(p, (np.nan, np.nan))[1])
        # write residuals back
        app_res = model["appearance_frame"][["appearance_id", "adjusted_post_entry_residual", "positive_appearance"]]
        for _, r in app_res.iterrows():
            conn.execute(
                """
                UPDATE substitute_appearances
                SET adjusted_post_entry_residual=?, positive_appearance=?
                WHERE appearance_id=?
                """,
                (float(r["adjusted_post_entry_residual"]), int(r["positive_appearance"]), int(r["appearance_id"])),
            )
        apps = apps.merge(app_res, on="appearance_id", how="left", suffixes=("", "_m"))
        if "positive_appearance_m" in apps:
            apps["positive_appearance"] = apps["positive_appearance_m"].fillna(apps.get("positive_appearance"))
    else:
        agg["team_impact_point"] = np.nan
        agg["adjusted_team_impact_after_entry"] = np.nan
        agg["team_impact_ci_low"] = np.nan
        agg["team_impact_ci_high"] = np.nan
        apps["positive_appearance"] = (apps["post_entry_change"].fillna(0) > 0).astype(int)

    pif = compute_positive_impact_frequency(apps)
    agg = agg.merge(
        pif[
            [
                "player_id",
                "positive_impact_frequency",
                "positive_impact_frequency_percentile",
                "raw_frequency",
                "positive_appearances",
            ]
        ],
        on="player_id",
        how="left",
    )

    adv = compute_substitute_advantage(apps, starters)
    agg = agg.merge(
        adv[
            [
                "player_id",
                "adjusted_substitute_rate",
                "adjusted_starter_rate",
                "substitute_advantage_raw",
                "substitute_advantage_adjusted",
                "advantage_percentile",
                "available",
                "interpretation",
                "ci_low",
                "ci_high",
                "starts",
                "starting_minutes",
            ]
        ],
        on="player_id",
        how="left",
        suffixes=("", "_adv"),
    )
    agg.rename(columns={"available": "advantage_available", "advantage_percentile": "substitute_advantage_percentile"}, inplace=True)

    # context helpers for classification
    trailing = apps[apps["score_state_simple"].isin(["trailing", "tied"])]
    leading = apps[apps["score_state_simple"] == "leading"]
    t_imp = trailing.groupby("player_id")["adjusted_post_entry_residual"].mean() if "adjusted_post_entry_residual" in trailing else trailing.groupby("player_id")["post_entry_change"].mean()
    t_n = trailing.groupby("player_id").size()
    l_imp = leading.groupby("player_id")["post_entry_change"].mean()
    agg["trailing_tied_impact"] = agg["player_id"].map(lambda p: float(t_imp.get(p, np.nan)) if p in t_imp.index else np.nan)
    # convert to pseudo percentile-ish 0-100 via rank later; for rules use residual>0 share
    agg["trailing_tied_apps"] = agg["player_id"].map(lambda p: int(t_n.get(p, 0)))
    agg["leading_impact"] = agg["player_id"].map(lambda p: 50 + 50 * np.tanh(l_imp.get(p, 0)) if p in l_imp.index else 0)
    agg["attack_context_score"] = agg["substitute_sporting_impact"].fillna(0)

    # Bench Impact Score with missing-component renormalization
    rows = []
    for _, r in agg.iterrows():
        comps = {
            "ssi": r.get("substitute_sporting_impact"),
            "ati": r.get("adjusted_team_impact_after_entry"),
            "pif": r.get("positive_impact_frequency_percentile"),
        }
        weights = {
            "ssi": settings.bis_weight_ssi,
            "ati": settings.bis_weight_ati,
            "pif": settings.bis_weight_pif,
        }
        missing = [k for k, v in comps.items() if pd.isna(v)]
        available = {k: v for k, v in comps.items() if not pd.isna(v)}
        bis = np.nan
        if len(available) == 3:
            bis = sum(weights[k] * available[k] for k in available)
        elif len(available) == 2:
            wsum = sum(weights[k] for k in available)
            bis = sum(weights[k] / wsum * available[k] for k in available)
        # coverage
        coverage = float(np.nanmean([r.get("coverage_gplus"), r.get("coverage_team")]))
        conf = data_confidence(
            int(r["substitute_appearances"]),
            float(r["substitute_minutes"]),
            coverage,
            float(r.get("simultaneous_rate") or 0),
            "2025" in str(r.get("seasons")) and "2026" in str(r.get("seasons")),
        )
        ci_width = None
        if not pd.isna(r.get("team_impact_ci_high")) and not pd.isna(r.get("team_impact_ci_low")):
            ci_width = float(r["team_impact_ci_high"] - r["team_impact_ci_low"])
        unc = model_uncertainty(
            int(r["substitute_appearances"]),
            float(r["substitute_minutes"]),
            coverage,
            float(r.get("simultaneous_rate") or 0),
            float(r.get("red_card_rate") or 0),
            ci_width,
            None,
        )
        rec = r.to_dict()
        rec["bench_impact_score"] = bis
        rec["data_confidence"] = conf
        rec["model_uncertainty"] = unc
        rec["components_missing"] = ",".join(missing)
        rec["substitute_advantage"] = r.get("substitute_advantage_adjusted")
        primary, tags = classify_player(rec)
        # downgrade elite if missing team impact
        if "ati" in missing and primary == "Elite Game Changer":
            primary = "Strong Bench Contributor"
        rec["classification_primary"] = primary
        rec["classification_tags"] = "|".join(tags)
        rows.append(rec)

    out = pd.DataFrame(rows)
    # official ranking universe
    official = out[
        (out["substitute_appearances"] >= settings.min_sub_appearances)
        & (out["substitute_minutes"] >= settings.min_sub_minutes)
        & (out["bench_impact_score"].notna())
    ].copy()
    official = official.sort_values(["bench_impact_score", "substitute_minutes", "player_id"], ascending=[False, False, True])
    official["overall_rank"] = np.arange(1, len(official) + 1)
    official["position_rank"] = official.groupby("position_group")["bench_impact_score"].rank(ascending=False, method="first")
    out = out.merge(official[["player_id", "overall_rank", "position_rank"]], on="player_id", how="left")

    # age
    def age_from_birth(b):
        if not b:
            return np.nan
        try:
            y = int(str(b)[:4])
            return 2026 - y
        except Exception:  # noqa: BLE001
            return np.nan

    pdata = players.set_index("player_id")
    out["age"] = out["player_id"].map(lambda p: age_from_birth(pdata.loc[p]["birth_date"] if p in pdata.index else None))
    out["evaluation_period"] = period
    out["model_version"] = MODEL_VERSION
    out["data_version"] = f"asa+fotmob-{settings.data_cutoff_date}"
    out["calculation_timestamp"] = datetime.now(UTC).isoformat()
    out["source_cutoff_dates"] = settings.data_cutoff_date
    return out


def persist_scores(conn, scores: pd.DataFrame, period: str) -> int:
    if scores.empty:
        return 0
    scores = scores.drop_duplicates(subset=["player_id"], keep="first").copy()
    conn.execute("DELETE FROM player_bench_scores WHERE evaluation_period=? AND model_version=?", (period, MODEL_VERSION))
    conn.execute("DELETE FROM player_substitute_advantage WHERE evaluation_period=? AND model_version=?", (period, MODEL_VERSION))
    n = 0
    for _, r in scores.iterrows():
        conn.execute(
            """
            INSERT INTO player_bench_scores(
              player_id, evaluation_period, position_group, club_team_id, age,
              substitute_appearances, substitute_minutes, median_entry_minute, starts, starting_minutes,
              substitute_sporting_impact, adjusted_team_impact_after_entry, positive_impact_frequency,
              positive_impact_frequency_percentile, substitute_advantage, substitute_advantage_percentile,
              bench_impact_score, overall_rank, position_rank, data_confidence, model_uncertainty,
              classification_primary, classification_tags, components_missing, observed_gplus_per96,
              adjusted_gplus_per96, team_impact_point, team_impact_ci_low, team_impact_ci_high,
              model_version, data_version, calculation_timestamp, source_cutoff_dates
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                r["player_id"],
                period,
                r.get("position_group"),
                r.get("team_id"),
                r.get("age"),
                int(r.get("substitute_appearances") or 0),
                float(r.get("substitute_minutes") or 0),
                r.get("median_entry_minute"),
                int(r.get("starts") or 0) if not pd.isna(r.get("starts")) else 0,
                float(r.get("starting_minutes") or 0) if not pd.isna(r.get("starting_minutes")) else 0,
                r.get("substitute_sporting_impact"),
                r.get("adjusted_team_impact_after_entry"),
                r.get("positive_impact_frequency"),
                r.get("positive_impact_frequency_percentile"),
                r.get("substitute_advantage"),
                r.get("substitute_advantage_percentile"),
                r.get("bench_impact_score"),
                r.get("overall_rank"),
                r.get("position_rank"),
                r.get("data_confidence"),
                r.get("model_uncertainty"),
                r.get("classification_primary"),
                r.get("classification_tags"),
                r.get("components_missing"),
                r.get("observed_gplus_per96"),
                r.get("adjusted_gplus_per96"),
                r.get("team_impact_point"),
                r.get("team_impact_ci_low"),
                r.get("team_impact_ci_high"),
                MODEL_VERSION,
                r.get("data_version"),
                r.get("calculation_timestamp"),
                r.get("source_cutoff_dates"),
            ),
        )
        conn.execute(
            """
            INSERT INTO player_substitute_advantage(
              player_id, evaluation_period, adjusted_substitute_rate, adjusted_starter_rate,
              substitute_advantage_raw, substitute_advantage_adjusted, advantage_percentile,
              ci_low, ci_high, interpretation, available, model_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                r["player_id"],
                period,
                r.get("adjusted_substitute_rate"),
                r.get("adjusted_starter_rate"),
                r.get("substitute_advantage_raw"),
                r.get("substitute_advantage"),
                r.get("substitute_advantage_percentile"),
                r.get("ci_low"),
                r.get("ci_high"),
                r.get("interpretation"),
                int(r.get("advantage_available") or 0),
                MODEL_VERSION,
            ),
        )
        n += 1
    return n