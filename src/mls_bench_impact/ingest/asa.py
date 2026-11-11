from __future__ import annotations

import calendar
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from mls_bench_impact.config.settings import settings
from mls_bench_impact.utils.http import get_json
from mls_bench_impact.utils.text import normalize_name, normalize_team_name


def _cache_path(name: str) -> Path:
    path = settings.raw_dir / "asa" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_or_fetch(cache_name: str, url: str, params: dict[str, Any] | None = None, force: bool = False) -> Any:
    cache = _cache_path(cache_name)
    if cache.exists() and not force:
        return json.loads(cache.read_text(encoding="utf-8"))
    data = get_json(url, params=params)
    cache.write_text(json.dumps(data), encoding="utf-8")
    return data


def fetch_teams(force: bool = False) -> list[dict]:
    return _load_or_fetch("teams.json", f"{settings.asa_base_url}/mls/teams", force=force)


def fetch_players(force: bool = False) -> list[dict]:
    return _load_or_fetch("players.json", f"{settings.asa_base_url}/mls/players", force=force)


def fetch_games(season: str, force: bool = False) -> list[dict]:
    return _load_or_fetch(
        f"games_{season}.json",
        f"{settings.asa_base_url}/mls/games",
        params={"season_name": season},
        force=force,
    )


# The ASA API silently truncates any response at this many rows.
ASA_ROW_LIMIT = 10_000


def _month_windows(first: date, last: date) -> list[tuple[str, str]]:
    windows = []
    y, m = first.year, first.month
    while (y, m) <= (last.year, last.month):
        end = date(y, m, calendar.monthrange(y, m)[1])
        windows.append((date(y, m, 1).isoformat(), end.isoformat()))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return windows


def _fetch_player_games(cache_name: str, endpoint: str, season: str, force: bool = False) -> list[dict]:
    """Player-by-game rows for one season.

    A single season-wide request is capped at ASA_ROW_LIMIT rows, which dropped about a
    third of player-games (a full season is ~15k rows). Query month by month instead and
    keep only that season's games.
    """
    cache = _cache_path(cache_name)
    if cache.exists() and not force:
        return json.loads(cache.read_text(encoding="utf-8"))
    games = fetch_games(season, force=force)
    season_games = {g["game_id"] for g in games}
    days = sorted(date.fromisoformat(g["date_time_utc"][:10]) for g in games)
    if not days:
        return []
    # Pad a day each side: ASA may filter on local rather than UTC dates.
    windows = _month_windows(days[0] - timedelta(days=1), days[-1] + timedelta(days=1))
    rows: dict[tuple[str, str], dict] = {}
    for start, end in windows:
        chunk = get_json(
            f"{settings.asa_base_url}/mls/players/{endpoint}",
            params={"split_by_games": "true", "minimum_minutes": 1, "start_date": start, "end_date": end},
        )
        if len(chunk) >= ASA_ROW_LIMIT:
            raise RuntimeError(f"ASA {endpoint} {start}..{end} hit the {ASA_ROW_LIMIT}-row cap; use smaller windows")
        for r in chunk:
            if r["game_id"] in season_games:
                rows[(r["player_id"], r["game_id"])] = r
    data = list(rows.values())
    cache.write_text(json.dumps(data), encoding="utf-8")
    return data


def fetch_player_xgoals_by_game(season: str, force: bool = False) -> list[dict]:
    return _fetch_player_games(f"player_xgoals_games_{season}.json", "xgoals", season, force=force)


def fetch_player_goals_added_by_game(season: str, force: bool = False) -> list[dict]:
    return _fetch_player_games(f"player_gplus_games_{season}.json", "goals-added", season, force=force)


def fetch_team_xgoals_by_game(season: str, force: bool = False) -> list[dict]:
    return _load_or_fetch(
        f"team_xgoals_games_{season}.json",
        f"{settings.asa_base_url}/mls/teams/xgoals",
        params={"season_name": season, "split_by_games": "true"},
        force=force,
    )


def flatten_goals_added(row: dict) -> dict:
    components = {d["action_type"]: d for d in row.get("data") or []}
    total = sum(float(d.get("goals_added_raw") or 0) for d in components.values())
    return {
        "player_id": row["player_id"],
        "game_id": row.get("game_id"),
        "team_id": row.get("team_id"),
        "general_position": row.get("general_position"),
        "minutes_played": row.get("minutes_played"),
        "goals_added_total": total,
        "gplus_shooting": float((components.get("Shooting") or {}).get("goals_added_raw") or 0),
        "gplus_passing": float((components.get("Passing") or {}).get("goals_added_raw") or 0),
        "gplus_receiving": float((components.get("Receiving") or {}).get("goals_added_raw") or 0),
        "gplus_dribbling": float((components.get("Dribbling") or {}).get("goals_added_raw") or 0),
        "gplus_interrupting": float((components.get("Interrupting") or {}).get("goals_added_raw") or 0),
        "gplus_fouling": float((components.get("Fouling") or {}).get("goals_added_raw") or 0),
    }


def ingest_asa_reference(conn, force: bool = False) -> dict[str, int]:
    teams = fetch_teams(force=force)
    players = fetch_players(force=force)
    n_teams = n_players = 0
    for t in teams:
        conn.execute(
            """
            INSERT INTO teams(team_id, asa_team_id, team_name, team_short_name, team_abbreviation, normalized_name)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(team_id) DO UPDATE SET
              asa_team_id=excluded.asa_team_id,
              team_name=excluded.team_name,
              team_short_name=excluded.team_short_name,
              team_abbreviation=excluded.team_abbreviation,
              normalized_name=excluded.normalized_name
            """,
            (
                f"asa:{t['team_id']}",
                t["team_id"],
                t["team_name"],
                t.get("team_short_name"),
                t.get("team_abbreviation"),
                normalize_team_name(t["team_name"]),
            ),
        )
        n_teams += 1

    for p in players:
        name = p.get("player_name") or ""
        pid = f"asa:{p['player_id']}"
        conn.execute(
            """
            INSERT INTO players(player_id, asa_player_id, player_name, normalized_name, birth_date, nationality, is_goalkeeper, is_synthetic)
            VALUES (?, ?, ?, ?, ?, ?, 0, 0)
            ON CONFLICT(player_id) DO UPDATE SET
              player_name=excluded.player_name,
              normalized_name=excluded.normalized_name,
              birth_date=excluded.birth_date,
              nationality=excluded.nationality
            """,
            (
                pid,
                p["player_id"],
                name,
                normalize_name(name),
                p.get("birth_date"),
                p.get("nationality"),
            ),
        )
        n_players += 1
    return {"teams": n_teams, "players": n_players}


def ingest_asa_games(conn, seasons: tuple[str, ...] | None = None, force: bool = False) -> int:
    seasons = seasons or settings.seasons
    count = 0
    for season in seasons:
        games = fetch_games(season, force=force)
        for g in games:
            if g.get("status") != "FullTime":
                continue
            home = f"asa:{g['home_team_id']}"
            away = f"asa:{g['away_team_id']}"
            match_id = f"asa:{g['game_id']}"
            conn.execute(
                """
                INSERT INTO matches(
                  match_id, asa_game_id, season_id, competition_id, match_date, match_datetime_utc,
                  home_team_id, away_team_id, home_score, away_score, status, is_knockout,
                  expanded_minutes, data_cutoff_date
                ) VALUES (?, ?, ?, 'mls', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(match_id) DO UPDATE SET
                  home_score=excluded.home_score,
                  away_score=excluded.away_score,
                  status=excluded.status,
                  expanded_minutes=excluded.expanded_minutes,
                  is_knockout=excluded.is_knockout
                """,
                (
                    match_id,
                    g["game_id"],
                    f"mls-{season}",
                    (g.get("date_time_utc") or "")[:10],
                    g.get("date_time_utc"),
                    home,
                    away,
                    g.get("home_score"),
                    g.get("away_score"),
                    g.get("status"),
                    1 if g.get("knockout_game") else 0,
                    g.get("expanded_minutes") or 90,
                    settings.data_cutoff_date,
                ),
            )
            count += 1
    return count


def backfill_positions_from_xgoals(conn, seasons: tuple[str, ...] | None = None, force: bool = False) -> int:
    from collections import Counter

    from mls_bench_impact.config.constants import POSITION_GROUPS

    seasons = seasons or settings.seasons
    counts: dict[str, Counter] = {}
    for season in seasons:
        for r in fetch_player_xgoals_by_game(season, force=force):
            counts.setdefault(r["player_id"], Counter())[r.get("general_position")] += 1
    n = 0
    for asa_id, ctr in counts.items():
        pos = ctr.most_common(1)[0][0]
        if not pos:
            continue
        pg = POSITION_GROUPS.get(pos, "Central and defensive midfielders")
        is_gk = 1 if pos == "GK" else 0
        cur = conn.execute(
            """
            UPDATE players
            SET primary_position=?, position_group=?, is_goalkeeper=CASE WHEN ?=1 THEN 1 ELSE is_goalkeeper END
            WHERE asa_player_id=?
            """,
            (pos, pg, is_gk, asa_id),
        )
        n += cur.rowcount
    return n


def ingest_asa_player_metrics(conn, seasons: tuple[str, ...] | None = None, force: bool = False) -> int:
    seasons = seasons or settings.seasons
    count = 0
    for season in seasons:
        xg_rows = { (r["player_id"], r["game_id"]): r for r in fetch_player_xgoals_by_game(season, force=force) }
        gplus_rows = fetch_player_goals_added_by_game(season, force=force)
        for raw in gplus_rows:
            flat = flatten_goals_added(raw)
            key = (flat["player_id"], flat["game_id"])
            xg = xg_rows.get(key, {})
            match_id = f"asa:{flat['game_id']}"
            player_id = f"asa:{flat['player_id']}"
            team_id = f"asa:{flat['team_id']}"
            # ensure player exists
            conn.execute(
                """
                INSERT OR IGNORE INTO players(player_id, asa_player_id, player_name, normalized_name, is_goalkeeper, is_synthetic)
                VALUES (?, ?, ?, ?, 0, 0)
                """,
                (player_id, flat["player_id"], flat["player_id"], normalize_name(flat["player_id"])),
            )
            pos = xg.get("general_position") or flat.get("general_position")
            if pos == "GK":
                conn.execute("UPDATE players SET is_goalkeeper=1, primary_position='GK', position_group='Goalkeepers' WHERE player_id=?", (player_id,))
            elif pos:
                from mls_bench_impact.config.constants import POSITION_GROUPS

                conn.execute(
                    "UPDATE players SET primary_position=?, position_group=? WHERE player_id=?",
                    (pos, POSITION_GROUPS.get(pos, "Central and defensive midfielders"), player_id),
                )
            conn.execute(
                """
                INSERT INTO player_match_metrics(
                  match_id, player_id, team_id, minutes_played, goals, assists, xgoals, xassists, shots, key_passes,
                  goals_added_total, gplus_shooting, gplus_passing, gplus_receiving, gplus_dribbling,
                  gplus_interrupting, gplus_fouling, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'asa')
                ON CONFLICT(match_id, player_id, source) DO UPDATE SET
                  minutes_played=excluded.minutes_played,
                  goals=excluded.goals,
                  assists=excluded.assists,
                  xgoals=excluded.xgoals,
                  xassists=excluded.xassists,
                  shots=excluded.shots,
                  key_passes=excluded.key_passes,
                  goals_added_total=excluded.goals_added_total,
                  gplus_shooting=excluded.gplus_shooting,
                  gplus_passing=excluded.gplus_passing,
                  gplus_receiving=excluded.gplus_receiving,
                  gplus_dribbling=excluded.gplus_dribbling,
                  gplus_interrupting=excluded.gplus_interrupting,
                  gplus_fouling=excluded.gplus_fouling
                """,
                (
                    match_id,
                    player_id,
                    team_id,
                    flat.get("minutes_played"),
                    xg.get("goals"),
                    xg.get("primary_assists"),
                    xg.get("xgoals"),
                    xg.get("xassists"),
                    xg.get("shots"),
                    xg.get("key_passes"),
                    flat.get("goals_added_total"),
                    flat.get("gplus_shooting"),
                    flat.get("gplus_passing"),
                    flat.get("gplus_receiving"),
                    flat.get("gplus_dribbling"),
                    flat.get("gplus_interrupting"),
                    flat.get("gplus_fouling"),
                ),
            )
            count += 1
    return count


def load_team_strength_map(seasons: tuple[str, ...] | None = None, force: bool = False) -> dict[tuple[str, str], float]:
    """Return {(asa_team_id, asa_game_id): prior_xg_diff_per_game} using expanding season mean excluding current game."""
    seasons = seasons or settings.seasons
    strength: dict[tuple[str, str], float] = {}
    for season in seasons:
        rows = fetch_team_xgoals_by_game(season, force=force)
        # need game dates
        games = {g["game_id"]: g for g in fetch_games(season, force=False)}
        by_team: dict[str, list[tuple[str, float]]] = {}
        for r in rows:
            gid = r["game_id"]
            g = games.get(gid)
            if not g:
                continue
            by_team.setdefault(r["team_id"], []).append(
                (g.get("date_time_utc") or "", gid, float(r.get("xgoal_difference") or 0))
            )
        for team_id, items in by_team.items():
            items_sorted = sorted(items, key=lambda x: x[0])
            cum = 0.0
            for i, (_dt, gid, val) in enumerate(items_sorted):
                prior = cum / i if i else 0.0
                strength[(team_id, gid)] = prior
                cum += val
    return strength