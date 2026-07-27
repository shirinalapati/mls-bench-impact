# Model Card — MLS Bench Impact v1.0.0

## Model details

- Name: MLS Bench Impact Score and components  
- Version: 1.0.0  
- Type: Empirical-Bayes shrinkage + ridge contextual association model  
- Intended use: Research / portfolio analytics for MLS substitute impact

## Training data

Public ASA and FotMob MLS data for 2025 and 2026 YTD.

## Evaluation

See `docs/validation.md` and `reports/model_validation.html`.

## Ethical & interpretive considerations

- Not a causal substitute-effect estimator  
- Not a recommendation engine for coaching decisions  
- Small samples are shrunk and labeled with Data Confidence / Uncertainty  
- Missing values remain missing

## Limitations

Possession-timed Goals Added after entry is unavailable; ASA G+ is game-level for minutes played. Simultaneous substitutions confound ATI.