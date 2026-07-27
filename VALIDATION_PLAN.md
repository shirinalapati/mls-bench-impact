# VALIDATION PLAN — MLS Bench Impact

## Goals

Validate each scoring component separately, then ranking stability, without claiming causal super-sub discovery.

## Component tests

### Substitute Sporting Impact

- Split-half reliability of appearance-level individual rates  
- Year-to-year score correlation  
- Stability by minutes band and position  
- Comparison vs raw goals/assists and raw G+/96  
- Shrinkage effect (extreme small samples move toward priors)

### Adjusted Team Impact After Entry

- Time-aware / held-out appearance prediction error  
- Bootstrap intervals for player effects  
- Context-only baseline vs player-effect model  
- Sensitivity to excluding red-card and triple-sub appearances  

### Substitute Advantage

- Eligibility threshold sensitivity  
- Regression-to-the-mean checks  
- Unavailable (not zero) when starter sample is insufficient  

### Ranking

- Top-10 / Top-25 Jaccard under alternate weights  
- Spearman rank correlation across weight schemes  
- Stability after excluding penalty/red-card/triple-sub cases  
- Club concentration diagnostics  

## Implemented artifacts

- `src/mls_bench_impact/validation/run_validation.py`  
- `reports/model_validation.html`  
- `reports/ranking_stability.html`  
- `docs/validation.md`  

## Acceptance

- Weight-scheme Spearman > 0.9 for default neighbors  
- Missing components never silently filled with 50  
- Insufficient samples cannot receive Elite Game Changer  
- No synthetic players in production rankings