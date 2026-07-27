from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.utils import get_column_letter

from mls_bench_impact import MODEL_VERSION
from mls_bench_impact.config.constants import METRIC_DICTIONARY_SEED
from mls_bench_impact.config.settings import settings


SHEETS = [
    "Executive Summary",
    "Overall Bench Rankings",
    "Position Rankings",
    "Context Leaderboards",
    "Substitute vs Starter",
    "Team Bench Analysis",
    "Player Profiles",
    "Appearance History",
    "Metric Dictionary",
    "Methodology",
    "Data Sources",
    "Validation",
    "Limitations",
]


def _auto_width(ws):
    for col in ws.columns:
        letter = get_column_letter(col[0].column)
        length = max(len(str(c.value)) if c.value is not None else 0 for c in col[:200])
        ws.column_dimensions[letter].width = min(max(length + 2, 12), 42)


def export_workbook(conn, path: Path | None = None, period: str = "2025-2026") -> Path:
    path = Path(path or settings.exports_dir / f"MLS_Bench_Impact_{period}.xlsx")
    path.parent.mkdir(parents=True, exist_ok=True)

    scores = pd.read_sql_query(
        """
        SELECT s.*, p.player_name, t.team_name AS club
        FROM player_bench_scores s
        JOIN players p ON p.player_id = s.player_id
        LEFT JOIN teams t ON t.team_id = s.club_team_id
        WHERE s.evaluation_period=? AND s.model_version=?
        ORDER BY s.overall_rank NULLS LAST, s.bench_impact_score DESC
        """,
        conn,
        params=(period, MODEL_VERSION),
    )
    apps = pd.read_sql_query(
        """
        SELECT a.*, p.player_name, t.team_name AS club, o.team_name AS opponent
        FROM substitute_appearances a
        JOIN players p ON p.player_id=a.player_id
        LEFT JOIN teams t ON t.team_id=a.team_id
        LEFT JOIN teams o ON o.team_id=a.opponent_id
        WHERE a.season IN ('2025','2026')
        """,
        conn,
    )
    adv = pd.read_sql_query(
        """
        SELECT a.*, p.player_name
        FROM player_substitute_advantage a
        JOIN players p ON p.player_id=a.player_id
        WHERE a.evaluation_period=? AND a.model_version=?
        """,
        conn,
        params=(period, MODEL_VERSION),
    )

    summary = pd.DataFrame(
        [
            {"Field": "Project", "Value": "MLS Bench Impact"},
            {"Field": "Evaluation period", "Value": period},
            {"Field": "Model version", "Value": MODEL_VERSION},
            {"Field": "Data cutoff", "Value": settings.data_cutoff_date},
            {"Field": "Ranked players", "Value": int(scores["overall_rank"].notna().sum())},
            {"Field": "Substitute appearances", "Value": int(len(apps))},
            {
                "Field": "Top player",
                "Value": scores.loc[scores["overall_rank"] == 1, "player_name"].iloc[0]
                if (scores["overall_rank"] == 1).any()
                else "N/A",
            },
        ]
    )

    metric_dict = pd.DataFrame(METRIC_DICTIONARY_SEED)
    methodology = pd.DataFrame(
        [
            {"Topic": "Bench Impact Score", "Detail": "0.50*SSI + 0.30*ATI + 0.20*PIF (configured weights)"},
            {"Topic": "Shrinkage", "Detail": "Empirical Bayes toward position-season prior; prior strength 450 minutes"},
            {"Topic": "Team impact", "Detail": "Ridge-adjusted post-entry team xG differential association"},
            {"Topic": "Causal language", "Detail": "Associations only; not causal substitution effects"},
        ]
    )
    sources = pd.DataFrame(
        [
            {"Source": "American Soccer Analysis", "Use": "Game-level Goals Added / xG"},
            {"Source": "FotMob", "Use": "Lineups, substitutions, score state, shotmap xG"},
        ]
    )
    limitations = pd.DataFrame(
        [
            {"Limitation": "ASA G+ is game-level for played minutes, not possession-timestamped after entry"},
            {"Limitation": "FotMob xG model differs from ASA xG"},
            {"Limitation": "Simultaneous substitutions confound individual team-impact attribution"},
            {"Limitation": "Identity bridging can miss obscure name variants"},
        ]
    )
    validation = pd.read_sql_query("SELECT * FROM validation_results ORDER BY validation_id DESC LIMIT 200", conn)

    team = (
        scores.groupby("club")
        .agg(
            players=("player_id", "count"),
            median_bis=("bench_impact_score", "median"),
            total_bench_minutes=("substitute_minutes", "sum"),
        )
        .reset_index()
        .sort_values("median_bis", ascending=False)
    )

    context_rows = []
    for state, label in [("trailing", "Best while trailing"), ("tied", "Best while tied"), ("leading", "Best while leading")]:
        g = apps[apps["score_state_simple"] == state]
        if g.empty:
            continue
        summ = (
            g.groupby("player_id")
            .agg(apps=("appearance_id", "count"), minutes=("substitute_minutes", "sum"), mean_change=("post_entry_change", "mean"))
            .reset_index()
        )
        summ = summ[(summ["apps"] >= 5) & (summ["minutes"] >= 90)]
        summ = summ.merge(scores[["player_id", "player_name", "club", "position_group"]], on="player_id", how="left")
        summ["leaderboard"] = label
        context_rows.append(summ.sort_values("mean_change", ascending=False).head(25))
    context = pd.concat(context_rows, ignore_index=True) if context_rows else pd.DataFrame()

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Executive Summary", index=False)
        scores.to_excel(writer, sheet_name="Overall Bench Rankings", index=False)
        scores.sort_values(["position_group", "position_rank"]).to_excel(writer, sheet_name="Position Rankings", index=False)
        context.to_excel(writer, sheet_name="Context Leaderboards", index=False)
        adv.to_excel(writer, sheet_name="Substitute vs Starter", index=False)
        team.to_excel(writer, sheet_name="Team Bench Analysis", index=False)
        scores.to_excel(writer, sheet_name="Player Profiles", index=False)
        apps.to_excel(writer, sheet_name="Appearance History", index=False)
        metric_dict.to_excel(writer, sheet_name="Metric Dictionary", index=False)
        methodology.to_excel(writer, sheet_name="Methodology", index=False)
        sources.to_excel(writer, sheet_name="Data Sources", index=False)
        validation.to_excel(writer, sheet_name="Validation", index=False)
        limitations.to_excel(writer, sheet_name="Limitations", index=False)

        wb = writer.book
        for name in SHEETS:
            if name not in wb.sheetnames:
                continue
            ws = wb[name]
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            _auto_width(ws)
            # conditional formatting on Bench Impact if present
            headers = [c.value for c in ws[1]]
            if "bench_impact_score" in headers:
                idx = headers.index("bench_impact_score") + 1
                col = get_column_letter(idx)
                ws.conditional_formatting.add(
                    f"{col}2:{col}{ws.max_row}",
                    ColorScaleRule(start_type="min", start_color="F8696B", mid_type="percentile", mid_value=50, mid_color="FFEB84", end_type="max", end_color="63BE7B"),
                )
    return path


def export_csvs(conn, out_dir: Path | None = None, period: str = "2025-2026") -> list[Path]:
    out_dir = Path(out_dir or settings.exports_dir / "csv")
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    scores = pd.read_sql_query(
        """
        SELECT s.*, p.player_name, t.team_name AS club
        FROM player_bench_scores s
        JOIN players p ON p.player_id=s.player_id
        LEFT JOIN teams t ON t.team_id=s.club_team_id
        WHERE evaluation_period=?
        """,
        conn,
        params=(period,),
    )
    p = out_dir / f"bench_rankings_{period}.csv"
    scores.to_csv(p, index=False)
    paths.append(p)
    apps = pd.read_sql_query("SELECT * FROM substitute_appearances", conn)
    p2 = out_dir / "substitute_appearances.csv"
    apps.to_csv(p2, index=False)
    paths.append(p2)
    return paths