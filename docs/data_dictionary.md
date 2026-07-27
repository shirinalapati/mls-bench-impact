# Data Dictionary

Core production tables are defined in `src/mls_bench_impact/db/schema.sql`.

Key score fields in `player_bench_scores`:

| Field | Definition |
| --- | --- |
| `substitute_sporting_impact` | Position percentile of shrunk substitute G+/96 |
| `adjusted_team_impact_after_entry` | Position percentile of ridge player effect |
| `positive_impact_frequency` | Shrunk positive appearance share |
| `substitute_advantage` | Adjusted sub − starter rate |
| `bench_impact_score` | Configured blend of SSI/ATI/PIF |
| `data_confidence` | High/Medium/Low/Insufficient |
| `model_uncertainty` | 0–100 (lower better) |
| `model_version` / `data_version` | Reproducibility metadata |
| `source_cutoff_dates` | Data cutoff stamp |

Metric dictionary seed used by the app/exports lives in `config/constants.py` (`METRIC_DICTIONARY_SEED`) so formulas cannot silently drift from code configuration.