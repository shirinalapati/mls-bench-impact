# Methodology — MLS Bench Impact

## Research questions

1. Measurable substitute impact after context adjustment  
2. Substitute-versus-starter performance differences

## Interval construction

Starters begin at minute 0. Substitutes begin at FotMob substitution timestamps (`time` + `overloadTime`). Exit is the earliest of substitution-off, red card, or ASA `expanded_minutes`. Score state and red-card state are taken at entry. Simultaneous substitutions are grouped by team and normalized minute.

## Substitute Sporting Impact (SSI)

Primary measure: ASA total Goals Added per 96 in substitute appearances.  
Rates are shrunk toward position-season priors with prior strength 450 minutes, then converted to position-group percentiles (0–100).

G+ action components (shooting, passing, receiving, dribbling, interrupting, fouling) are explanatory only and are not double-counted in the main SSI formula.

## Adjusted Team Impact After Entry (ATI)

For each appearance, compute team shotmap xG for/against before and after entry, expressed per 90.  
Fit a ridge regression with context covariates and heavily regularized player indicators.  
Player coefficients are converted to position-group percentiles.  
Language: *estimated association with team performance after entry*.

## Positive Impact Frequency (PIF)

An appearance is positive when the adjusted post-entry residual is > 0.  
Frequencies use beta-binomial shrinkage with a mild position prior, then optional position percentiles for BIS.

## Substitute Advantage

Compare shrunk substitute G+/96 with shrunk starter G+/96 for players meeting both role sample thresholds.  
Unavailable when starting evidence is insufficient — never coded as zero.

## Bench Impact Score

\[
BIS = 0.50\cdot SSI + 0.30\cdot ATI + 0.20\cdot PIF\%
\]

Weights are configured, not learned. If one component is missing, renormalize only when ≥2 components remain; lower Data Confidence; do not award Elite Game Changer.

## Validation

Split-half reliability, year-to-year correlation, weight sensitivity, and exclusion stress tests are written to `reports/model_validation.html` and `reports/ranking_stability.html`.