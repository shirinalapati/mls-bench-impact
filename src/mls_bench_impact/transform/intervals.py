from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from mls_bench_impact.config.constants import POSITION_GROUPS
from mls_bench_impact.ingest.fotmob import extract_stat, fetch_match_payload, finished_match_ids
from mls_bench_impact.transform.identity import (
    bridge_matches,
    bridge_players,
    bridge_teams,
    canonical_match_id,
    resolve_player_id,
    resolve_team_id,
)
from mls_bench_impact.utils.time_utils import (
    entry_timing_category,
    normalized_minute,
    score_state_detailed,
    score_state_simple,
    tactical_situation,
)


# FotMob usualPlayingPositionId is a coarse role code (observed):
# 0=GK, 1=Defender, 2=Midfielder, 3=Attacker
USUAL_ROLE_TO_GROUP = {
    0: "Goalkeepers",
    1: "Center backs",
    2: "Central and defensive midfielders",
    3: "Wingers and attacking midfielders",
}


def _pos_group_from_codes(position_id: int | None, usual: int | None, asa_pos: str | None) -> str:
    if asa_pos:
        return POSITION_GROUPS.get(asa_pos, "Central and defensive midfielders")
    if usual is not None and int(usual) in USUAL_ROLE_TO_GROUP:
        group = USUAL_ROLE_TO_GROUP[int(usual)]
        # Refine defenders / attackers with formation slot when available
        if group == "Center backs" and position_id is not None:
            # wide defensive slots -> fullbacks
            if int(position_id) in {2, 3, 4, 5, 66, 68, 69, 70}:
                return "Fullbacks and wingbacks"
        if group == "Wingers and attacking midfielders" and position_id is not None:
            if int(position_id) in {9, 10, 11, 105, 106, 107}:
                return "Strikers"
        return group
    if position_id is None:
        return "Central and defensive midfielders"
    code = int(position_id)
    if code >= 100:
        return "Strikers"
    if code >= 70:
        return "Wingers and attacking midfielders"
    if code >= 40:
        return "Central and defensive midfielders"
    if code >= 20:
        return "Fullbacks and wingbacks"
    return "Center backs"


def ingest_fotmob_match_shells(conn, seasons: tuple[str, ...] = ("2025", "2026"), force: bool = False) -> int:
    """Create FotMob match rows (later bridged to ASA)."""
    n = 0
    for season in seasons:
        for mid in finished_match_ids(season, force=force):
            # lightweight: store from fixtures file
            from mls_bench_impact.ingest.fotmob import fetch_league_fixtures

            break
    # better: iterate fixtures directly
    from mls_bench_impact.ingest.fotmob import fetch_league_fixtures

    for season in seasons:
        for m in fetch_league_fixtures(season, force=force):
            st = m.get("status") or {}
            if not st.get("finished") or st.get("cancelled"):
                continue
            home = m.get("home") or {}
            away = m.get("away") or {}
            home_id = resolve_team_id(conn, home.get("id"), home.get("name"))
            away_id = resolve_team_id(conn, away.get("id"), away.get("name"))
            score = st.get("scoreStr") or "0 - 0"
            try:
                hs, as_ = [int(x.strip()) for x in score.replace("–", "-").split("-")]
            except Exception:  # noqa: BLE001
                hs = as_ = None
            match_date = (st.get("utcTime") or "")[:10]
            fotmob_id = str(m["id"])
            # if already linked ASA match exists with this fotmob id, skip insert
            existing = conn.execute(
                "SELECT match_id FROM matches WHERE fotmob_match_id=?", (fotmob_id,)
            ).fetchone()
            if existing:
                continue
            # try find ASA match to attach
            asa = conn.execute(
                """
                SELECT m.match_id FROM matches m
                JOIN teams th ON th.team_id=m.home_team_id
                JOIN teams ta ON ta.team_id=m.away_team_id
                WHERE m.match_date=? AND th.normalized_name=? AND ta.normalized_name=?
                  AND m.asa_game_id IS NOT NULL
                """,
                (
                    match_date,
                    __import__("mls_bench_impact.utils.text", fromlist=["normalize_team_name"]).normalize_team_name(
                        home.get("name")
                    ),
                    __import__("mls_bench_impact.utils.text", fromlist=["normalize_team_name"]).normalize_team_name(
                        away.get("name")
                    ),
                ),
            ).fetchone()
            if asa:
                conn.execute(
                    "UPDATE matches SET fotmob_match_id=? WHERE match_id=?",
                    (fotmob_id, asa["match_id"]),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO matches(
                      match_id, fotmob_match_id, season_id, competition_id, match_date, match_datetime_utc,
                      home_team_id, away_team_id, home_score, away_score, status, is_knockout, expanded_minutes
                    ) VALUES (?, ?, ?, 'mls', ?, ?, ?, ?, ?, ?, 'FullTime', 0, 96)
                    """,
                    (
                        f"fm:{fotmob_id}",
                        fotmob_id,
                        f"mls-{season}",
                        match_date,
                        st.get("utcTime"),
                        home_id,
                        away_id,
                        hs,
                        as_,
                    ),
                )
            n += 1
    bridge_teams(conn)
    bridge_matches(conn)
    return n


def _score_before_minute(events: list[dict], minute: float, is_home_team: bool) -> tuple[int, int]:
    """Return (for, against) for a side using goal events strictly before entry."""
    home = away = 0
    for e in events:
        if e.get("type") != "Goal":
            continue
        m = normalized_minute(e.get("time"), e.get("overloadTime"))
        if m >= minute:
            continue
        # use newScore if present else increment
        if e.get("newScore"):
            home, away = int(e["newScore"][0]), int(e["newScore"][1])
        else:
            if e.get("ownGoal"):
                if e.get("isHome"):
                    away += 1
                else:
                    home += 1
            else:
                if e.get("isHome"):
                    home += 1
                else:
                    away += 1
    if is_home_team:
        return home, away
    return away, home


def _red_card_state(events: list[dict], minute: float, team_is_home: bool) -> str:
    home_reds = away_reds = 0
    for e in events:
        if e.get("type") != "Card":
            continue
        if str(e.get("card", "")).lower() != "red":
            continue
        m = normalized_minute(e.get("time"), e.get("overloadTime"))
        if m > minute:
            continue
        if e.get("isHome"):
            home_reds += 1
        else:
            away_reds += 1
    if home_reds == away_reds == 0:
        return "none"
    if team_is_home:
        if home_reds > away_reds:
            return "team_short"
        if away_reds > home_reds:
            return "opponent_short"
    else:
        if away_reds > home_reds:
            return "team_short"
        if home_reds > away_reds:
            return "opponent_short"
    return "balanced"


def _window_xg(shots: list[dict], team_fm_id: int | str, start: float, end: float) -> tuple[float, float, int, int]:
    team_fm_id = int(team_fm_id)
    xg_for = xg_against = 0.0
    sh_for = sh_against = 0
    for s in shots:
        m = normalized_minute(s.get("min"), s.get("minAdded"))
        if m < start or m >= end:
            continue
        xg = float(s.get("expectedGoals") or 0)
        if s.get("isOwnGoal"):
            # own goal credited against shooting team conceptually; skip xG add for for/against shot model
            continue
        if int(s.get("teamId") or -1) == team_fm_id:
            xg_for += xg
            sh_for += 1
        else:
            xg_against += xg
            sh_against += 1
    return xg_for, xg_against, sh_for, sh_against


def build_from_match_payload(conn, fotmob_match_id: str, payload: dict[str, Any]) -> dict[str, int]:
    general = payload.get("general") or {}
    content = payload.get("content") or {}
    lineup = content.get("lineup") or {}
    facts = content.get("matchFacts") or {}
    events = ((facts.get("events") or {}).get("events")) or []
    shots = ((content.get("shotmap") or {}).get("shots")) or []
    player_stats = content.get("playerStats") or {}

    match_id = canonical_match_id(conn, fotmob_match_id)
    if not match_id:
        return {"skipped": 1}

    match = conn.execute("SELECT * FROM matches WHERE match_id=?", (match_id,)).fetchone()
    if not match or match["status"] != "FullTime":
        return {"skipped": 1}

    expanded = float(match["expanded_minutes"] or 96)
    home_team_fm = (general.get("homeTeam") or {}).get("id") or (lineup.get("homeTeam") or {}).get("id")
    away_team_fm = (general.get("awayTeam") or {}).get("id") or (lineup.get("awayTeam") or {}).get("id")

    # clear prior derived rows for this match
    for table in (
        "match_events",
        "substitutions",
        "lineups",
        "player_match_intervals",
        "substitute_appearances",
        "starter_appearances",
        "team_match_windows",
    ):
        conn.execute(f"DELETE FROM {table} WHERE match_id=?", (match_id,))

    # ingest events
    for e in events:
        et = e.get("type")
        if et == "Goal":
            event_type = "own_goal" if e.get("ownGoal") else "goal"
            player = e.get("player") or {}
            pid = resolve_player_id(conn, player.get("id") or e.get("playerId"), player.get("name") or e.get("nameStr"))
        elif et == "Card":
            event_type = "red_card" if str(e.get("card", "")).lower() == "red" else "yellow_card"
            player = e.get("player") or {}
            pid = resolve_player_id(conn, player.get("id") or e.get("playerId"), player.get("name"))
        elif et == "Substitution":
            event_type = "substitution"
            swap = e.get("swap") or []
            pin = swap[0] if swap else {}
            pid = resolve_player_id(conn, pin.get("id"), pin.get("name"))
        else:
            continue
        nm = normalized_minute(e.get("time"), e.get("overloadTime"))
        team_id = match["home_team_id"] if e.get("isHome") else match["away_team_id"]
        conn.execute(
            """
            INSERT INTO match_events(
              match_id, team_id, player_id, event_type, clock_minute, stoppage_minute,
              normalized_minute, home_score, away_score, payload_json, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'fotmob')
            """,
            (
                match_id,
                team_id,
                pid,
                event_type,
                float(e.get("time") or 0),
                float(e.get("overloadTime") or 0),
                nm,
                e.get("homeScore"),
                e.get("awayScore"),
                json.dumps(e),
            ),
        )

    counts = defaultdict(int)
    # process each side
    for side, team_blob in (("home", lineup.get("homeTeam")), ("away", lineup.get("awayTeam"))):
        if not team_blob:
            continue
        is_home = side == "home"
        team_id = match["home_team_id"] if is_home else match["away_team_id"]
        opponent_id = match["away_team_id"] if is_home else match["home_team_id"]
        formation = team_blob.get("formation")
        fm_team_id = team_blob.get("id")

        starters = team_blob.get("starters") or []
        subs = team_blob.get("subs") or []
        all_players = [(True, p) for p in starters] + [(False, p) for p in subs]

        # map sub events from match facts for this side
        side_subs = [
            e
            for e in events
            if e.get("type") == "Substitution" and bool(e.get("isHome")) == is_home
        ]
        # simultaneous counts
        minute_groups: dict[float, list] = defaultdict(list)
        for e in side_subs:
            minute_groups[normalized_minute(e.get("time"), e.get("overloadTime"))].append(e)
        sim_count = {m: len(v) for m, v in minute_groups.items()}

        # build exit map from subOut / red cards
        sub_out_minute: dict[str, float] = {}
        sub_in_meta: dict[str, dict] = {}
        for e in side_subs:
            swap = e.get("swap") or []
            if len(swap) < 2:
                continue
            pin, pout = swap[0], swap[1]
            nm = normalized_minute(e.get("time"), e.get("overloadTime"))
            in_id = str(pin.get("id"))
            out_id = str(pout.get("id"))
            sub_out_minute[out_id] = min(nm, sub_out_minute.get(out_id, nm))
            sub_in_meta[in_id] = {
                "minute": nm,
                "clock": float(e.get("time") or 0),
                "stoppage": float(e.get("overloadTime") or 0),
                "out_id": out_id,
                "out_name": pout.get("name"),
                "injured": bool(e.get("injuredPlayerOut")),
                "home_score": e.get("homeScore"),
                "away_score": e.get("awayScore"),
                "sim": sim_count.get(nm, 1),
            }
            conn.execute(
                """
                INSERT OR IGNORE INTO substitutions(
                  match_id, team_id, player_in_id, player_out_id, clock_minute, stoppage_minute,
                  normalized_minute, entry_score_for, entry_score_against, score_difference_at_entry,
                  is_home, injured_player_out, simultaneous_sub_count, simultaneous_group_id, formation_before
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    match_id,
                    team_id,
                    resolve_player_id(conn, pin.get("id"), pin.get("name")),
                    resolve_player_id(conn, pout.get("id"), pout.get("name")),
                    float(e.get("time") or 0),
                    float(e.get("overloadTime") or 0),
                    nm,
                    (e.get("homeScore") if is_home else e.get("awayScore")),
                    (e.get("awayScore") if is_home else e.get("homeScore")),
                    (
                        (e.get("homeScore") or 0) - (e.get("awayScore") or 0)
                        if is_home
                        else (e.get("awayScore") or 0) - (e.get("homeScore") or 0)
                    ),
                    1 if is_home else 0,
                    1 if e.get("injuredPlayerOut") else 0,
                    sim_count.get(nm, 1),
                    f"{match_id}:{team_id}:{nm}",
                    formation,
                ),
            )
            counts["substitutions"] += 1

        # red card exits
        for e in events:
            if e.get("type") == "Card" and str(e.get("card", "")).lower() == "red" and bool(e.get("isHome")) == is_home:
                player = e.get("player") or {}
                pid = str(player.get("id") or e.get("playerId") or "")
                if pid:
                    nm = normalized_minute(e.get("time"), e.get("overloadTime"))
                    sub_out_minute[pid] = min(nm, sub_out_minute.get(pid, nm))

        for is_starter, p in all_players:
            fm_pid = str(p.get("id"))
            name = p.get("name")
            player_id = resolve_player_id(conn, fm_pid, name)
            is_gk = False
            ps = player_stats.get(str(fm_pid)) or player_stats.get(fm_pid)
            if ps:
                is_gk = bool(ps.get("isGoalkeeper"))
            if is_gk:
                conn.execute("UPDATE players SET is_goalkeeper=1, position_group='Goalkeepers' WHERE player_id=?", (player_id,))
            pos_id = p.get("positionId")
            usual = p.get("usualPlayingPositionId")
            # ASA position if available
            prow = conn.execute(
                "SELECT primary_position, position_group FROM players WHERE player_id=?",
                (player_id,),
            ).fetchone()
            asa_pos_code = prow["primary_position"] if prow else None
            if prow and prow["position_group"] and prow["position_group"] != "Goalkeepers":
                pos_group = prow["position_group"]
            else:
                pos_group = _pos_group_from_codes(pos_id, usual, asa_pos_code)
            if not is_gk and not (prow and prow["position_group"]):
                conn.execute(
                    "UPDATE players SET position_group=COALESCE(position_group, ?) WHERE player_id=?",
                    (pos_group, player_id),
                )

            conn.execute(
                """
                INSERT OR IGNORE INTO lineups(match_id, team_id, player_id, is_starter, shirt_number, position_code, formation)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (match_id, team_id, player_id, 1 if is_starter else 0, p.get("shirtNumber"), str(pos_id), formation),
            )
            counts["lineups"] += 1

            # determine interval
            if is_starter:
                entry = 0.0
                role = "starter"
                replaced = None
                sim = 1
                injured = False
            else:
                meta = sub_in_meta.get(fm_pid)
                if not meta:
                    continue  # unused bench
                entry = meta["minute"]
                role = "substitute"
                replaced = resolve_player_id(conn, meta["out_id"], meta["out_name"])
                sim = meta["sim"]
                injured = meta["injured"]

            exit_m = sub_out_minute.get(fm_pid, expanded)
            if exit_m < entry:
                exit_m = entry
            minutes = max(0.0, exit_m - entry)
            # prefer playerStats minutes when close
            if ps:
                mp = extract_stat(ps, "minutes_played")
                if mp is not None and abs(mp - minutes) <= 5:
                    minutes = mp

            entry_for, entry_against = _score_before_minute(events, entry, is_home)
            # final scores
            final_for = match["home_score"] if is_home else match["away_score"]
            final_against = match["away_score"] if is_home else match["home_score"]
            red_state = _red_card_state(events, entry, is_home)
            flags = []
            if sim >= 2:
                flags.append("simultaneous_sub")
            if red_state != "none":
                flags.append(f"red:{red_state}")

            conn.execute(
                """
                INSERT INTO player_match_intervals(
                  match_id, player_id, team_id, opponent_id, role, entry_minute, exit_minute, minutes_played,
                  is_home, entry_score_for, entry_score_against, exit_score_for, exit_score_against,
                  red_card_state, replaced_player_id, simultaneous_sub_count, data_quality_flags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    match_id,
                    player_id,
                    team_id,
                    opponent_id,
                    role,
                    entry,
                    exit_m,
                    minutes,
                    1 if is_home else 0,
                    entry_for,
                    entry_against,
                    final_for,
                    final_against,
                    red_state,
                    replaced,
                    sim,
                    ",".join(flags),
                ),
            )
            counts["intervals"] += 1

            # fotmob metrics upsert
            if ps:
                conn.execute(
                    """
                    INSERT INTO player_match_metrics(
                      match_id, player_id, team_id, minutes_played, goals, assists, fotmob_xg, fotmob_xa,
                      shots, defensive_actions, source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'fotmob')
                    ON CONFLICT(match_id, player_id, source) DO UPDATE SET
                      minutes_played=excluded.minutes_played,
                      goals=excluded.goals,
                      assists=excluded.assists,
                      fotmob_xg=excluded.fotmob_xg,
                      fotmob_xa=excluded.fotmob_xa,
                      shots=excluded.shots,
                      defensive_actions=excluded.defensive_actions
                    """,
                    (
                        match_id,
                        player_id,
                        team_id,
                        extract_stat(ps, "minutes_played"),
                        extract_stat(ps, "goals"),
                        extract_stat(ps, "assists"),
                        extract_stat(ps, "expected_goals"),
                        extract_stat(ps, "expected_assists"),
                        extract_stat(ps, "total_shots"),
                        extract_stat(ps, "defensive_actions"),
                    ),
                )

            if role == "substitute" and not is_gk:
                # team windows
                pre_end = entry
                post_start = entry
                xg_for_pre, xg_ag_pre, sh_for_pre, sh_ag_pre = _window_xg(shots, fm_team_id, 0, pre_end)
                xg_for_post, xg_ag_post, sh_for_post, sh_ag_post = _window_xg(shots, fm_team_id, post_start, expanded)
                pre_min = max(pre_end, 1e-6)
                post_min = max(expanded - post_start, 1e-6)
                pre_diff_p90 = (xg_for_pre - xg_ag_pre) / pre_min * 90
                post_diff_p90 = (xg_for_post - xg_ag_post) / post_min * 90
                for wtype, start, end, xf, xa, sf, sa in (
                    ("pre_entry", 0, pre_end, xg_for_pre, xg_ag_pre, sh_for_pre, sh_ag_pre),
                    ("post_entry", post_start, expanded, xg_for_post, xg_ag_post, sh_for_post, sh_ag_post),
                ):
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO team_match_windows(
                          match_id, team_id, window_type, start_minute, end_minute,
                          xg_for, xg_against, xg_diff, shots_for, shots_against
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (match_id, team_id, f"{wtype}:{player_id}", start, end, xf, xa, xf - xa, sf, sa),
                    )

                # ASA metrics if player bridged to ASA id used in metrics table
                # metrics stored under asa player ids on asa match ids
                asa_metric = None
                # try direct
                asa_metric = conn.execute(
                    "SELECT * FROM player_match_metrics WHERE match_id=? AND player_id=? AND source='asa'",
                    (match_id, player_id),
                ).fetchone()
                if not asa_metric:
                    # player may be fm: while metrics on asa:
                    fp = conn.execute("SELECT fotmob_player_id, asa_player_id, normalized_name FROM players WHERE player_id=?", (player_id,)).fetchone()
                    if fp and fp["asa_player_id"]:
                        asa_metric = conn.execute(
                            "SELECT * FROM player_match_metrics WHERE match_id=? AND player_id=? AND source='asa'",
                            (match_id, f"asa:{fp['asa_player_id']}"),
                        ).fetchone()
                    if not asa_metric and fp:
                        # find asa player with same fotmob link
                        linked = conn.execute(
                            "SELECT player_id FROM players WHERE fotmob_player_id=? AND asa_player_id IS NOT NULL",
                            (fp["fotmob_player_id"],),
                        ).fetchone()
                        if linked:
                            asa_metric = conn.execute(
                                "SELECT * FROM player_match_metrics WHERE match_id=? AND player_id=? AND source='asa'",
                                (match_id, linked["player_id"]),
                            ).fetchone()
                            player_id = linked["player_id"]  # canonicalize appearance to ASA player

                gplus = float(asa_metric["goals_added_total"]) if asa_metric and asa_metric["goals_added_total"] is not None else None
                gplus_p96 = (gplus / minutes * 96) if gplus is not None and minutes > 0 else None
                pxg = float(asa_metric["xgoals"]) if asa_metric and asa_metric["xgoals"] is not None else extract_stat(ps, "expected_goals") if ps else None
                pxa = float(asa_metric["xassists"]) if asa_metric and asa_metric["xassists"] is not None else extract_stat(ps, "expected_assists") if ps else None
                shots_n = float(asa_metric["shots"]) if asa_metric and asa_metric["shots"] is not None else extract_stat(ps, "total_shots") if ps else None

                diff = entry_for - entry_against
                is_ht = abs(entry - 45) < 0.51 or abs(entry - 46) < 0.51
                season = match["season_id"].replace("mls-", "")
                conn.execute(
                    """
                    INSERT OR REPLACE INTO substitute_appearances(
                      match_id, player_id, team_id, opponent_id, season, competition, match_date, home_away,
                      entry_minute, normalized_entry_minute, exit_minute, substitute_minutes,
                      entry_score_for, entry_score_against, score_difference_at_entry, score_state_at_entry,
                      score_state_simple, final_score_for, final_score_against, red_card_state,
                      simultaneous_sub_count, entering_position, position_group, replaced_player_id,
                      formation_before, entry_timing_category, tactical_situation,
                      pre_entry_xg_diff_per90, post_entry_xg_diff_per90, post_entry_change,
                      player_gplus, player_gplus_per96, player_xg, player_xa, player_shots, data_quality_flags
                    ) VALUES (?, ?, ?, ?, ?, 'MLS', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        match_id,
                        player_id,
                        team_id,
                        opponent_id,
                        season,
                        match["match_date"],
                        "home" if is_home else "away",
                        entry,
                        entry,
                        exit_m,
                        minutes,
                        entry_for,
                        entry_against,
                        diff,
                        score_state_detailed(diff),
                        score_state_simple(diff),
                        final_for,
                        final_against,
                        red_state,
                        sim,
                        asa_pos_code,
                        pos_group,
                        replaced,
                        formation,
                        entry_timing_category(entry, is_halftime=is_ht),
                        tactical_situation(diff, entry, is_ht, red_state, injured),
                        pre_diff_p90,
                        post_diff_p90,
                        post_diff_p90 - pre_diff_p90,
                        gplus,
                        gplus_p96,
                        pxg,
                        pxa,
                        shots_n,
                        ",".join(flags),
                    ),
                )
                counts["substitute_appearances"] += 1

            if role == "starter" and not is_gk:
                asa_metric = conn.execute(
                    "SELECT * FROM player_match_metrics WHERE match_id=? AND player_id=? AND source='asa'",
                    (match_id, player_id),
                ).fetchone()
                if not asa_metric:
                    fp = conn.execute("SELECT fotmob_player_id, asa_player_id FROM players WHERE player_id=?", (player_id,)).fetchone()
                    if fp and fp["asa_player_id"]:
                        asa_metric = conn.execute(
                            "SELECT * FROM player_match_metrics WHERE match_id=? AND player_id=? AND source='asa'",
                            (match_id, f"asa:{fp['asa_player_id']}"),
                        ).fetchone()
                        if asa_metric:
                            player_id = f"asa:{fp['asa_player_id']}"
                gplus = float(asa_metric["goals_added_total"]) if asa_metric and asa_metric["goals_added_total"] is not None else None
                gplus_p96 = (gplus / minutes * 96) if gplus is not None and minutes > 0 else None
                conn.execute(
                    """
                    INSERT OR REPLACE INTO starter_appearances(
                      match_id, player_id, team_id, opponent_id, season, match_date, home_away,
                      starting_minutes, position_group, player_gplus, player_gplus_per96, player_xg, player_xa
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        match_id,
                        player_id,
                        team_id,
                        opponent_id,
                        match["season_id"].replace("mls-", ""),
                        match["match_date"],
                        "home" if is_home else "away",
                        minutes,
                        pos_group,
                        gplus,
                        gplus_p96,
                        float(asa_metric["xgoals"]) if asa_metric and asa_metric["xgoals"] is not None else None,
                        float(asa_metric["xassists"]) if asa_metric and asa_metric["xassists"] is not None else None,
                    ),
                )
                counts["starter_appearances"] += 1

    bridge_players(conn)
    return dict(counts)


def build_all_intervals(conn, seasons: tuple[str, ...] = ("2025", "2026"), force_fetch: bool = False) -> dict[str, int]:
    from mls_bench_impact.ingest.fotmob import fetch_matches_bulk

    ingest_fotmob_match_shells(conn, seasons=seasons, force=force_fetch)
    bridge_teams(conn)
    bridge_matches(conn)
    bridge_players(conn)

    all_ids: list[str] = []
    for season in seasons:
        all_ids.extend(finished_match_ids(season, force=False))
    payloads = fetch_matches_bulk(all_ids, force=force_fetch)

    totals = defaultdict(int)
    for mid in all_ids:
        payload = payloads.get(str(mid)) or fetch_match_payload(mid, force=force_fetch)
        if not payload:
            totals["missing_payload"] += 1
            continue
        if not canonical_match_id(conn, mid):
            totals["unbridged_match"] += 1
            continue
        c = build_from_match_payload(conn, mid, payload)
        for k, v in c.items():
            totals[k] += v
        totals["matches_built"] += 1
        if totals["matches_built"] % 25 == 0:
            conn.commit()
    return dict(totals)