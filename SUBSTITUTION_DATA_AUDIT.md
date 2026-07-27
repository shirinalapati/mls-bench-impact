# SUBSTITUTION DATA AUDIT — MLS Bench Impact

## Feasibility conclusion

FotMob substitution events are sufficient to build production-grade substitute appearances for MLS 2025 and 2026 YTD, including entry minute, score state, simultaneous groups, injury flags, and replaced-player identity.

## Validation checks performed on sample match `5070991` (STL vs CLT, 2026-02-21)

| Check | Result |
| --- | --- |
| Substitution events present | 9 events |
| `swap[0]` = entrant / `swap[1]` = exited | Consistent with lineup `subIn`/`subOut` |
| Score on sub event | Present (`homeScore`, `awayScore`) |
| Simultaneous subs | Three away subs at minute 69 |
| Injury flag | Field `injuredPlayerOut` present (false in sample) |
| Added-time subs | Events at minute 90 with `overloadTime` |
| Minutes for sub | PlayerStats `Minutes played` = 31 for 59' entrant |

## Coverage expectations

| Population | Expectation |
| --- | --- |
| Finished MLS matches 2025 | ~540 with lineups |
| Finished MLS matches 2026 YTD | ~253 with lineups |
| Matches missing lineup/events | Flagged `data_quality_flags`; excluded from official rankings |
| Players without ASA bridge | Appear in warehouse; excluded from official Bench Impact until matched |

## Interval construction rules

1. Starters begin at normalized minute 0.
2. Substitute entrants begin at substitution normalized minute.
3. Exit = earliest of: `subOut`, red card dismissal, match `expanded_minutes`.
4. Players listed only on bench with no `subIn` → no on-field interval.
5. Duplicate identical substitution events → dedupe by (match, team, in, out, minute).
6. Player cannot be starter and unused bench simultaneously; if both starter and subIn exist, treat as data error flag.
7. Abandoned / non-FT matches excluded from production scoring.

## Attribution uncertainty

| Pattern | Model Uncertainty effect |
| --- | --- |
| Single-player substitution | Baseline |
| 2+ teammates enter same timestamp | Increase simultaneous-sub component |
| Red-card state already active | Increase red-card contamination component |
| Missing shotmap | Team-impact component missing → renormalize Bench Impact if ≥2 components remain |

## ASA join strategy for individual G+

For each FotMob substitute appearance, join ASA `players/goals-added?split_by_games=true` on bridged player + bridged game.

Because ASA rows describe only the minutes the player participated, a pure substitute appearance’s game-level G+ is the substitute contribution for that match. Mixed starter/sub double-counts are avoided by role labeling from FotMob intervals (starter appearances vs substitute appearances are separate rows).
