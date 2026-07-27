# DATA SOURCE AUDIT — MLS Bench Impact

**Audit date:** 2026-07-26  
**Production sources:** American Soccer Analysis (ASA) API + FotMob public match pages  
**Excluded from production:** synthetic fixtures, demo players, MLS NEXT Pro, USL, NCAA

---

## 1. American Soccer Analysis API

| Property | Value |
| --- | --- |
| Base URL | `https://app.americansocceranalysis.com/api/v1` |
| Client | Direct HTTPS JSON (optional `itscalledsoccer` wrapper) |
| Auth | None for public endpoints used here |
| Update cadence | Continuous during MLS season; game rows update after finalization |
| Seasons used | 2025, 2026 |
| League filter | `mls` only |

### Endpoints used

| Endpoint | Purpose |
| --- | --- |
| `/mls/players` | Player IDs, names, birth dates |
| `/mls/teams` | Team IDs and names |
| `/mls/games?season_name=` | Match calendar, scores, `expanded_minutes`, knockout flag, status |
| `/mls/players/xgoals?split_by_games=true` | Per-game xG, xA, shots, goals, assists, minutes |
| `/mls/players/goals-added?split_by_games=true` | Per-game G+ action components + minutes |
| `/mls/teams/xgoals?split_by_games=true` | Team game xG for/against (strength priors) |
| `/mls/games/xgoals` | Match-level team xG summary |

### Coverage observed (audit pull)

| Season | Completed games (`status=FullTime`) | Knockout games |
| --- | --- | --- |
| 2025 | 540 | 30 |
| 2026 YTD | 253 | 0 observed in sample pull |

### Known limitations

- No native substitution timestamps or lineup starter flags
- G+/xG are **game aggregates for the minutes the player played**, not possession-timestamped after entry
- No red-card or score-state fields on player metric endpoints
- Goalkeeper G+ uses a separate model; outfield rankings exclude GK

---

## 2. FotMob public match pages

| Property | Value |
| --- | --- |
| Access method | HTML `__NEXT_DATA__` JSON hydration |
| League | MLS `leagueId=130` |
| Season pages | `/leagues/130/overview/mls?season=2025` and `2026` |
| Match pages | `/match/{matchId}` |
| Update cadence | Live during matches; finalized shortly after FT |
| Rate policy | Polite crawl with cache; no paid API key |

### Payload regions used

| Region | Purpose |
| --- | --- |
| `fixtures.allMatches` | Season match list, FT status, score string |
| `content.lineup` | Starters, bench, formations, subIn/subOut events |
| `content.matchFacts.events` | Goals, cards, substitutions with `homeScore`/`awayScore` |
| `content.shotmap.shots` | Minute-level shot xG for team windows |
| `content.playerStats` | Minutes, xG, xA, shots, defensive actions for intervals |
| `header.events` | Alternate goal listing with assist metadata |

### Coverage observed

| Season | Fixtures listed | Finished |
| --- | --- | --- |
| 2025 | 540 | 540 |
| 2026 | 510 | 253 (YTD as of audit) |

### Known limitations

- Not an official Opta feed; occasional missing lineups on abandoned/low-coverage matches
- Substitution `swap[0]` = player in, `swap[1]` = player out (validated against lineup `subIn`/`subOut`)
- Added time via `time` + `overloadTime` (e.g., 90 + 3)
- No native Goals Added
- Player IDs are FotMob IDs; must be bridged to ASA

---

## 3. Sources considered and rejected for production

| Source | Reason |
| --- | --- |
| BallDontLie MLS | Match events/lineups require paid ALL-STAR+; not assumed available |
| StatsBomb Open Data | No current MLS 2025–2026 open release covering this scope |
| Synthetic generators | Forbidden in production rankings |

---

## 4. Entity resolution

Players and teams are linked ASA ↔ FotMob by:

1. Normalized full name
2. Club name / abbreviation alignment for the match date
3. Birth year when available
4. Manual alias table (`config/identity_aliases.csv`) for residual collisions

Unmatched ASA players are retained in the warehouse but **cannot enter production rankings** until bridged for substitution context.
