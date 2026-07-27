# EVENT SCHEMA AUDIT — MLS Bench Impact

## FotMob match event schema (production)

Source path: `pageProps.content.matchFacts.events.events[]`

| Native field | Type | Definition | Unit | Notes |
| --- | --- | --- | --- | --- |
| `type` | string | `Goal`, `Card`, `Substitution`, `Half` | categorical | Primary event class |
| `time` | int | Clock minute | minute | 1–90+ |
| `overloadTime` | int/null | Stoppage minute | minute | e.g. 3 for 90+3 |
| `timeStr` | int/string | Display minute | minute | Prefer `time`+`overloadTime` |
| `homeScore` | int | Home goals before/at event | goals | Present on goals/subs |
| `awayScore` | int | Away goals before/at event | goals | Present on goals/subs |
| `isHome` | bool | Event attributed to home side | flag | |
| `card` | string/null | `Yellow` / `Red` | categorical | On `Card` events |
| `injuredPlayerOut` | bool | Injury-flagged substitution | flag | Do not infer if false |
| `swap` | array | `[playerIn, playerOut]` | players | Each has `id`, `name` |
| `player` | object | Primary player (goals/cards) | player | Often empty on subs |
| `ownGoal` | bool/null | Own goal flag | flag | |
| `newScore` | [h,a] | Score after goal | goals | Goals only |

### Shotmap schema

Source: `content.shotmap.shots[]`

| Field | Definition |
| --- | --- |
| `min`, `minAdded` | Shot timing |
| `expectedGoals` | Shot xG |
| `teamId`, `playerId` | Attribution |
| `isOwnGoal` | Exclude from for-team xG when true |
| `period` | FirstHalf / SecondHalf / etc. |

### Lineup schema

| Path | Definition |
| --- | --- |
| `lineup.homeTeam.starters[]` | Starting XI with `positionId` |
| `lineup.homeTeam.subs[]` | Bench pool |
| `*.performance.substitutionEvents[]` | `{time, type: subIn\|subOut}` |
| `formation` | Formation string before kickoff |

### Player match stats

Source: `content.playerStats[playerId].stats[*].stats`

Key stats extracted: `minutes_played`, `expected_goals`, `expected_assists`, `goals`, `assists`, `total_shots`, `chances_created`, `defensive_actions`, `touches_opp_box`.

## ASA game-level player metrics schema

### xG (`/mls/players/xgoals?split_by_games=true`)

| Field | Definition | Unit |
| --- | --- | --- |
| `player_id`, `game_id`, `team_id` | Keys | id |
| `minutes_played` | On-field minutes in game | minutes |
| `general_position` | ASA position code (ST, W, AM, CM, DM, FB, CB, GK) | cat |
| `xgoals`, `xassists` | Expected goals / assists | goals |
| `goals`, `primary_assists`, `shots`, `key_passes` | Counting stats | count |

### Goals Added (`/mls/players/goals-added?split_by_games=true`)

| Field | Definition |
| --- | --- |
| `data[].action_type` | Dribbling, Fouling, Interrupting, Passing, Receiving, Shooting |
| `data[].goals_added_raw` | Raw G+ for action type |
| `data[].goals_added_above_avg` | Above average G+ |
| `minutes_played` | Minutes associated with the row |

**Total G+** = sum of `goals_added_raw` across action types (outfield).

## Normalized project event types

Internal `match_events.event_type`:

- `goal`, `own_goal`, `yellow_card`, `red_card`, `substitution`, `period_end`

Internal time fields:

- `clock_minute`, `stoppage_minute`, `normalized_minute`  
  where `normalized_minute = clock_minute + 0.01 * stoppage_minute` for ordering, and interval math uses `clock_minute + stoppage_minute` capped by match `expanded_minutes`.
