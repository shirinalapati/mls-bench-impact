# MLS Bench Impact — Project Plan

## Research questions

1. Which MLS players provide the greatest measurable impact when entering matches as substitutes, after accounting for playing time, position, entry minute, score state, opponent strength, team strength, and substitution context?
2. Which players perform meaningfully better as substitutes than they do as starters?

## Scope

- MLS first-team only (regular season + optional playoffs filter)
- Evaluation periods: 2025 full season, 2026 season-to-date, combined 2025–2026 (default)
- Outfield players only (goalkeepers excluded)
- No MLS NEXT Pro, USL, NCAA, or synthetic players in production rankings

## Data architecture

| Layer | Source | Role |
| --- | --- | --- |
| Match events, lineups, substitutions, score at entry, cards, shot-level xG | FotMob public match pages (`__NEXT_DATA__`) | Interval construction, context, team-window xG |
| Players, teams, games, game-level Goals Added, xG/xA | American Soccer Analysis API | Individual substitute impact, team/opponent strength |
| Identity bridge | Name + club + match-date matching | Link ASA ↔ FotMob entities |

## Pipeline stages

1. Restore dependencies
2. Initialize SQLite schema
3. Ingest ASA reference + per-game metrics
4. Ingest FotMob fixtures + match payloads (cached)
5. Build match/player intervals and substitution records
6. Build substitute and starter appearance tables
7. Calculate Substitute Sporting Impact (shrunk G+/96)
8. Fit Adjusted Team Impact After Entry (ridge)
9. Calculate Positive Impact Frequency
10. Calculate Substitute Advantage
11. Generate Bench Impact Score, confidence, uncertainty, classifications
12. Run tests and validation reports
13. Generate Excel/CSV/PDF exports
14. Start application

## Metric strategy (defensible under available data)

- **Primary individual measure:** ASA game-level total Goals Added for appearances where the player entered as a substitute (ASA minutes align with on-field minutes for that role). Rate as G+/96 with position-context shrinkage.
- **Team impact:** FotMob shotmap xG for/against before vs after entry, converted to per-90 differentials, then ridge-adjusted for context. Language: *estimated association*, not causation.
- **Unavailable natively:** event-timestamped Goals Added by possession after entry; formation-change attribution beyond pre/post formation strings; injury confirmation beyond FotMob `injuredPlayerOut`.

## Application

Streamlit multipage app with production SQLite:

1. About & Methodology
2. Bench Impact Rankings
3. Player Profile
4. Substitute vs Starter
5. Team Bench Analysis
6. Match Explorer
7. Context Leaderboards
8. Compare Players

## Model versioning

- `MODEL_VERSION=1.0.0`
- Weights (configured, not learned): 0.50 / 0.30 / 0.20
- Prior strength: 450 substitute minutes
- Official eligibility baseline: ≥8 substitute appearances and ≥180 substitute minutes

## Deployment

- Reproducible: `make all` / `./scripts/run_production.sh`
- App: Streamlit (local + cloud deploy)
- CI: pytest, ruff, schema checks, docs presence
