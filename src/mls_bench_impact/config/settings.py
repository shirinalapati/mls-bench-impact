from __future__ import annotations

from pathlib import Path

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

    data_cutoff_date: str = "2026-07-26"


settings = Settings()