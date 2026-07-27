# Validation

Implemented in `src/mls_bench_impact/validation/run_validation.py`.

Checks include:

- Split-half reliability of substitute G+/96  
- Year-to-year Bench Impact correlation (2025 vs 2026)  
- Rank stability under alternate BIS weights (60/25/15, 50/30/20, 40/40/20, equal)  
- Top-10 Jaccard stability after excluding simultaneous triple substitutions  
- Correlation of BIS with raw G+/96 baseline (should relate, not collapse)

Outputs:

- `reports/model_validation.html`  
- `reports/ranking_stability.html`  
- rows in `validation_results`