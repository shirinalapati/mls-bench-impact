# DATA FEASIBILITY AUDIT — MLS Bench Impact

**Verdict:** Production analysis is feasible for both research questions using ASA + FotMob, with documented substitutes for unavailable event-level Goals Added timestamps.

| # | Requirement | Supported? | Implementation |
| ---: | --- | --- | --- |
| 1 | Match identifiers | Yes | ASA `game_id` + FotMob `matchId` + bridge table |
| 2 | Player identifiers | Yes | ASA `player_id` + FotMob player `id` + bridge |
| 3 | Team identifiers | Yes | ASA `team_id` + FotMob team `id` + bridge |
| 4 | Starting lineups | Yes | FotMob `lineup.*.starters` |
| 5 | Substitute events | Yes | FotMob events `type=Substitution` + lineup `substitutionEvents` |
| 6 | Entry minute | Yes | Event `time` (+ `overloadTime`) |
| 7 | Exit minute | Yes | Later `subOut`, red card, or match end (`expanded_minutes`) |
| 8 | Added-time handling | Yes | Normalized minute = clock + overload; match end from ASA `expanded_minutes` / FotMob FT |
| 9 | Score at entry | Yes | Substitution event `homeScore`/`awayScore` |
| 10 | Home and away | Yes | Lineup side + ASA home/away team IDs |
| 11 | Red-card events | Yes | FotMob `Card` with `card=Red` / second yellow if present |
| 12 | Event timestamps | Partial | Minute resolution (not HH:MM:SS); sufficient for soccer analytics |
| 13 | Player actions after entry | Partial | FotMob player match stats + shotmap shots after entry; ASA game G+ for sub-only minutes |
| 14 | Team actions before/after entry | Yes (xG) | Shotmap split at entry minute; goals from events |
| 15 | Expected goals | Yes | ASA player/team xG; FotMob shot xG |
| 16 | Goals Added | Partial | ASA **game-level** G+ by player (not possession-time stamped). Used as primary individual measure for role-aligned minutes |
| 17 | Shots | Yes | ASA + FotMob |
| 18 | Possessions / sequences | No | Not available publicly at production quality → not used |
| 19 | Opponent strength | Yes | Derived from ASA team xG differentials (season-to-date prior to match, leakage-safe) |
| 20 | Team strength | Yes | Same |
| 21 | Simultaneous substitutions | Yes | Group by team + normalized minute |
| 22 | Player position | Yes | ASA `general_position` + FotMob position IDs → project position groups |
| 23 | Competition and season | Yes | MLS; ASA `season_name`; FotMob season; ASA `knockout_game` for playoffs |
| 24 | Starter vs substitute minutes | Yes | Interval builder from lineups + subs |

## Strongest defensible metric stack

1. **Substitute Sporting Impact:** shrunk ASA total G+/96 in substitute appearances, position-context prior, position-group percentile.
2. **Adjusted Team Impact After Entry:** ridge-adjusted post-entry team xG differential per 90 from FotMob shotmap windows.
3. **Positive Impact Frequency:** share of appearances with positive adjusted post-entry residual (beta-binomial shrinkage).
4. **Substitute Advantage:** shrunk sub vs starter G+/96 difference with context adjustment and eligibility gates.

## Explicit gaps (not fabricated)

- Possession-value chains and event-timed G+ after entry
- Confirmed injury replacements beyond FotMob `injuredPlayerOut`
- Official Opta xG (FotMob/ASA models differ; both disclosed)
- Perfect cross-provider identity without aliases

Production never silently fills these gaps with synthetic values.
