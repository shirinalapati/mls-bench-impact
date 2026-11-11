from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MBI_", env_file=".env", extra="ignore")

    project_root: Path = ROOT
    data_dir: Path = ROOT / "data"
    raw_dir: Path = ROOT / "data" / "raw"
    processed_dir: Path = ROOT / "data" / "processed"
    exports_dir: Path = ROOT / "data" / "exports"
    reports_dir: Path = ROOT / "reports"
    db_path: Path = (
        ROOT / "data" / "release" / "mls_bench_impact.db"
        if (ROOT / "data" / "release" / "mls_bench_impact.db").exists()
        else ROOT / "data" / "processed" / "mls_bench_impact.db"
    )

    asa_base_url: str = "https://app.americansocceranalysis.com/api/v1"
    fotmob_base_url: str = "https://www.fotmob.com"
    fotmob_league_id: int = 130

    seasons: tuple[str, ...] = ("2025", "2026")
    default_evaluation_period: str = "2025-2026"
    model_version: str = "1.0.0"

    prior_strength_minutes: float = 450.0
    min_sub_appearances: int = 8
    min_sub_minutes: int = 180
    min_starts_for_advantage: int = 6
    min_starter_minutes_for_advantage: int = 450

    bis_weight_ssi: float = 0.50
    bis_weight_ati: float = 0.30
    bis_weight_pif: float = 0.20

    request_timeout_s: float = 45.0
    fotmob_concurrency: int = 4
    fotmob_delay_s: float = 0.15
    allow_synthetic: bool = False

    # Empty -> date of the last successful pipeline run recorded in the DB (what the
    # app shows), else today. The pipeline stamps each run with today's date unless
    # MBI_DATA_CUTOFF_DATE is set explicitly.
    data_cutoff_date: str = ""

    @model_validator(mode="after")
    def _resolve_cutoff(self) -> Settings:
        if not self.data_cutoff_date:
            self.data_cutoff_date = _last_run_cutoff(self.db_path) or date.today().isoformat()
        return self


def _last_run_cutoff(db_path: Path) -> str | None:
    if not db_path.exists():
        return None
    try:
        with closing(sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)) as conn:
            row = conn.execute(
                """
                SELECT data_cutoff_date FROM pipeline_runs
                WHERE status = 'ok' AND data_cutoff_date IS NOT NULL
                ORDER BY finished_at DESC LIMIT 1
                """
            ).fetchone()
    except sqlite3.Error:
        return None
    return row[0] if row else None


settings = Settings()