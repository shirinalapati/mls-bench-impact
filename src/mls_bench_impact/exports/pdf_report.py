from __future__ import annotations

from pathlib import Path

import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from mls_bench_impact import MODEL_VERSION
from mls_bench_impact.config.settings import settings


def export_player_pdf(conn, player_id: str, period: str = "2025-2026", path: Path | None = None) -> Path:
    row = pd.read_sql_query(
        """
        SELECT s.*, p.player_name, t.team_name AS club
        FROM player_bench_scores s
        JOIN players p ON p.player_id=s.player_id
        LEFT JOIN teams t ON t.team_id=s.club_team_id
        WHERE s.player_id=? AND s.evaluation_period=?
        """,
        conn,
        params=(player_id, period),
    )
    if row.empty:
        raise ValueError(f"No scores for {player_id}")
    r = row.iloc[0]
    out = Path(path or settings.exports_dir / "pdf" / f"{r['player_name'].replace(' ', '_')}_bench_impact.pdf")
    out.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(out), pagesize=letter)
    width, height = letter
    y = height - inch
    c.setFont("Helvetica-Bold", 16)
    c.drawString(inch, y, "MLS Bench Impact — Player Report")
    y -= 28
    c.setFont("Helvetica-Bold", 14)
    c.drawString(inch, y, str(r["player_name"]))
    y -= 18
    c.setFont("Helvetica", 11)
    lines = [
        f"Club: {r.get('club')} | Position: {r.get('position_group')} | Age: {r.get('age')}",
        f"Evaluation period: {period} | Model: {MODEL_VERSION} | Data cutoff: {settings.data_cutoff_date}",
        f"Substitute appearances: {r.get('substitute_appearances')} | Minutes: {r.get('substitute_minutes'):.0f}",
        f"Median entry minute: {r.get('median_entry_minute')}",
        "",
        f"Bench Impact Score: {r.get('bench_impact_score')}",
        f"Substitute Sporting Impact: {r.get('substitute_sporting_impact')}",
        f"Adjusted Team Impact After Entry: {r.get('adjusted_team_impact_after_entry')}",
        f"Positive Impact Frequency: {r.get('positive_impact_frequency')}",
        f"Substitute Advantage: {r.get('substitute_advantage')}",
        f"Data Confidence: {r.get('data_confidence')} | Model Uncertainty: {r.get('model_uncertainty')}",
        f"Classification: {r.get('classification_primary')}",
        "",
        "Interpretation note:",
        "Scores estimate measurable associations using public data.",
        "They do not prove that a substitution caused team improvement.",
        "",
        "Limitations: game-level Goals Added; simultaneous-sub confounding;",
        "sample-size shrinkage toward position priors.",
    ]
    for line in lines:
        c.drawString(inch, y, str(line)[:95])
        y -= 14
        if y < inch:
            c.showPage()
            y = height - inch
            c.setFont("Helvetica", 11)
    c.showPage()
    c.save()
    return out