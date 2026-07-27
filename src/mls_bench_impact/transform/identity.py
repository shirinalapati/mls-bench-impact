from __future__ import annotations

import csv
from pathlib import Path

from rapidfuzz import fuzz, process

from mls_bench_impact.config.settings import settings
from mls_bench_impact.utils.text import normalize_name, normalize_team_name

ALIASES_PATH = settings.project_root / "config" / "identity_aliases.csv"


def load_aliases() -> dict[str, str]:
    """Map fotmob normalized name -> asa player_id (without prefix)."""
    if not ALIASES_PATH.exists():
        return {}
    out = {}
    with ALIASES_PATH.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out[normalize_name(row["fotmob_name"])] = row["asa_player_id"]
    return out


def bridge_teams(conn) -> int:
    asa = conn.execute(
        "SELECT team_id, asa_team_id, normalized_name, team_name FROM teams WHERE asa_team_id IS NOT NULL"
    ).fetchall()
    fm = conn.execute(
        "SELECT team_id, fotmob_team_id, normalized_name, team_name FROM teams WHERE fotmob_team_id IS NOT NULL"
    ).fetchall()
    asa_by_norm = {r["normalized_name"]: r for r in asa}
    linked = 0
    for f in fm:
        a = asa_by_norm.get(f["normalized_name"])
        if not a:
            # fuzzy
            choices = list(asa_by_norm.keys())
            match = process.extractOne(f["normalized_name"], choices, scorer=fuzz.token_sort_ratio)
            if match and match[1] >= 90:
                a = asa_by_norm[match[0]]
        if not a:
            continue
        # prefer ASA id as canonical; stamp fotmob id onto ASA row and remap references gradually
        conn.execute(
            "UPDATE teams SET fotmob_team_id=? WHERE team_id=?",
            (f["fotmob_team_id"], a["team_id"]),
        )
        linked += 1
    return linked


def bridge_matches(conn) -> int:
    """Link ASA and FotMob matches by date + home/away normalized names."""
    asa_matches = conn.execute(
        """
        SELECT m.match_id, m.asa_game_id, m.match_date, m.home_score, m.away_score,
               th.normalized_name AS home_name, ta.normalized_name AS away_name
        FROM matches m
        JOIN teams th ON th.team_id = m.home_team_id
        JOIN teams ta ON ta.team_id = m.away_team_id
        WHERE m.asa_game_id IS NOT NULL
        """
    ).fetchall()
    # FotMob matches may be stored with fm teams only after ingest_fotmob_matches
    fm_matches = conn.execute(
        """
        SELECT m.match_id, m.fotmob_match_id, m.match_date, m.home_score, m.away_score,
               th.normalized_name AS home_name, ta.normalized_name AS away_name
        FROM matches m
        JOIN teams th ON th.team_id = m.home_team_id
        JOIN teams ta ON ta.team_id = m.away_team_id
        WHERE m.fotmob_match_id IS NOT NULL AND m.asa_game_id IS NULL
        """
    ).fetchall()

    index: dict[tuple[str, str, str], sqlite_row] = {}
    for a in asa_matches:
        index[(a["match_date"], a["home_name"], a["away_name"])] = a

    linked = 0
    for f in fm_matches:
        key = (f["match_date"], f["home_name"], f["away_name"])
        a = index.get(key)
        if not a:
            # try swapped? no
            continue
        conn.execute(
            "UPDATE matches SET fotmob_match_id=? WHERE match_id=?",
            (f["fotmob_match_id"], a["match_id"]),
        )
        # mark fm match as superseded by deleting? keep both but we'll use ASA match_id as canonical
        conn.execute(
            "UPDATE matches SET asa_game_id=? WHERE match_id=?",
            (a["asa_game_id"], f["match_id"]),
        )
        linked += 1
    return linked


# fix type hint without importing sqlite3 Row name incorrectly
sqlite_row = object


def bridge_players(conn) -> int:
    aliases = load_aliases()
    asa_players = conn.execute(
        """
        SELECT player_id, asa_player_id, normalized_name, player_name, birth_date
        FROM players WHERE asa_player_id IS NOT NULL
        """
    ).fetchall()
    fm_players = conn.execute(
        """
        SELECT player_id, fotmob_player_id, normalized_name, player_name
        FROM players WHERE fotmob_player_id IS NOT NULL AND asa_player_id IS NULL
        """
    ).fetchall()

    asa_by_norm: dict[str, list] = {}
    for p in asa_players:
        asa_by_norm.setdefault(p["normalized_name"], []).append(p)

    asa_choices = list(asa_by_norm.keys())
    linked = 0
    for f in fm_players:
        target_asa_id = aliases.get(f["normalized_name"])
        chosen = None
        if target_asa_id:
            row = conn.execute(
                "SELECT * FROM players WHERE asa_player_id=?", (target_asa_id,)
            ).fetchone()
            chosen = row
        else:
            exact = asa_by_norm.get(f["normalized_name"])
            if exact and len(exact) == 1:
                chosen = exact[0]
            else:
                match = process.extractOne(f["normalized_name"], asa_choices, scorer=fuzz.token_sort_ratio)
                if match and match[1] >= 93:
                    cands = asa_by_norm[match[0]]
                    if len(cands) == 1:
                        chosen = cands[0]
        if not chosen:
            continue
        conn.execute(
            "UPDATE players SET fotmob_player_id=? WHERE player_id=?",
            (f["fotmob_player_id"], chosen["player_id"]),
        )
        linked += 1
    return linked


def resolve_player_id(conn, fotmob_player_id: str | int | None, name: str | None) -> str | None:
    if fotmob_player_id is None and not name:
        return None
    if fotmob_player_id is not None:
        # Prefer ASA canonical row already linked to this FotMob id
        row = conn.execute(
            """
            SELECT player_id FROM players
            WHERE fotmob_player_id=? AND asa_player_id IS NOT NULL
            LIMIT 1
            """,
            (str(fotmob_player_id),),
        ).fetchone()
        if row:
            return row["player_id"]
        row = conn.execute(
            "SELECT player_id FROM players WHERE fotmob_player_id=?", (str(fotmob_player_id),)
        ).fetchone()
        if row:
            return row["player_id"]
        # try alias / exact name against ASA before creating fm-only row
        n = normalize_name(name)
        aliases = load_aliases()
        if n in aliases:
            a = conn.execute(
                "SELECT player_id FROM players WHERE asa_player_id=?", (aliases[n],)
            ).fetchone()
            if a:
                conn.execute(
                    "UPDATE players SET fotmob_player_id=? WHERE player_id=?",
                    (str(fotmob_player_id), a["player_id"]),
                )
                return a["player_id"]
        if n:
            a = conn.execute(
                """
                SELECT player_id FROM players
                WHERE normalized_name=? AND asa_player_id IS NOT NULL
                LIMIT 1
                """,
                (n,),
            ).fetchone()
            if a:
                conn.execute(
                    "UPDATE players SET fotmob_player_id=? WHERE player_id=?",
                    (str(fotmob_player_id), a["player_id"]),
                )
                return a["player_id"]
        from mls_bench_impact.ingest.fotmob import ensure_fotmob_player

        return ensure_fotmob_player(conn, fotmob_player_id, name or str(fotmob_player_id))
    n = normalize_name(name)
    row = conn.execute(
        "SELECT player_id FROM players WHERE normalized_name=? AND asa_player_id IS NOT NULL LIMIT 1",
        (n,),
    ).fetchone()
    if row:
        return row["player_id"]
    row = conn.execute("SELECT player_id FROM players WHERE normalized_name=? LIMIT 1", (n,)).fetchone()
    return row["player_id"] if row else None


def resolve_team_id(conn, fotmob_team_id: str | int | None, name: str | None) -> str | None:
    n = normalize_team_name(name) if name else None
    if n:
        asa = conn.execute(
            "SELECT team_id FROM teams WHERE normalized_name=? AND asa_team_id IS NOT NULL LIMIT 1",
            (n,),
        ).fetchone()
        if asa:
            if fotmob_team_id is not None:
                conn.execute(
                    "UPDATE teams SET fotmob_team_id=? WHERE team_id=?",
                    (str(fotmob_team_id), asa["team_id"]),
                )
            return asa["team_id"]
    if fotmob_team_id is not None:
        asa = conn.execute(
            "SELECT team_id FROM teams WHERE fotmob_team_id=? AND asa_team_id IS NOT NULL",
            (str(fotmob_team_id),),
        ).fetchone()
        if asa:
            return asa["team_id"]
        row = conn.execute(
            "SELECT team_id FROM teams WHERE fotmob_team_id=?", (str(fotmob_team_id),)
        ).fetchone()
        if row:
            return row["team_id"]
        from mls_bench_impact.ingest.fotmob import ensure_fotmob_team

        return ensure_fotmob_team(conn, fotmob_team_id, name or str(fotmob_team_id))
    if n:
        row = conn.execute("SELECT team_id FROM teams WHERE normalized_name=? LIMIT 1", (n,)).fetchone()
        return row["team_id"] if row else None
    return None


def canonical_match_id(conn, fotmob_match_id: str) -> str | None:
    row = conn.execute(
        "SELECT match_id FROM matches WHERE fotmob_match_id=? AND asa_game_id IS NOT NULL",
        (str(fotmob_match_id),),
    ).fetchone()
    if row:
        return row["match_id"]
    row = conn.execute(
        "SELECT match_id FROM matches WHERE fotmob_match_id=?", (str(fotmob_match_id),)
    ).fetchone()
    return row["match_id"] if row else None