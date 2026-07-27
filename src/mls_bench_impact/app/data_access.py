from __future__ import annotations

import sqlite3
from functools import lru_cache

import pandas as pd

from mls_bench_impact import MODEL_VERSION
from mls_bench_impact.config.settings import settings


@lru_cache(maxsize=1)
def get_db_path() -> str:
    return str(settings.db_path)


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def load_rankings(period: str = "2025-2026") -> pd.DataFrame:
    with connect() as conn:
        return pd.read_sql_query(
            """
            SELECT s.*, p.player_name, t.team_name AS club
            FROM player_bench_scores s
            JOIN players p ON p.player_id=s.player_id
            LEFT JOIN teams t ON t.team_id=s.club_team_id
            WHERE s.evaluation_period=? AND s.model_version=?
            ORDER BY CASE WHEN s.overall_rank IS NULL THEN 1 ELSE 0 END, s.overall_rank
            """,
            conn,
            params=(period, MODEL_VERSION),
        )


def load_player(player_id: str, period: str = "2025-2026") -> pd.Series | None:
    df = load_rankings(period)
    hit = df[df["player_id"] == player_id]
    return hit.iloc[0] if len(hit) else None


def load_appearances(player_id: str | None = None) -> pd.DataFrame:
    q = """
        SELECT a.*, p.player_name, t.team_name AS club, o.team_name AS opponent
        FROM substitute_appearances a
        JOIN players p ON p.player_id=a.player_id
        LEFT JOIN teams t ON t.team_id=a.team_id
        LEFT JOIN teams o ON o.team_id=a.opponent_id
    """
    params = []
    if player_id:
        q += " WHERE a.player_id=?"
        params.append(player_id)
    with connect() as conn:
        return pd.read_sql_query(q, conn, params=params)


def load_advantage(period: str = "2025-2026") -> pd.DataFrame:
    with connect() as conn:
        return pd.read_sql_query(
            """
            SELECT a.*, p.player_name, s.position_group, s.club_team_id, t.team_name AS club,
                   s.substitute_appearances, s.substitute_minutes, s.starts, s.starting_minutes,
                   s.data_confidence
            FROM player_substitute_advantage a
            JOIN players p ON p.player_id=a.player_id
            LEFT JOIN player_bench_scores s
              ON s.player_id=a.player_id AND s.evaluation_period=a.evaluation_period
            LEFT JOIN teams t ON t.team_id=s.club_team_id
            WHERE a.evaluation_period=?
            """,
            conn,
            params=(period,),
        )


def load_teams() -> pd.DataFrame:
    with connect() as conn:
        return pd.read_sql_query(
            "SELECT * FROM teams WHERE asa_team_id IS NOT NULL ORDER BY team_name",
            conn,
        )


def load_matches(season: str | None = None) -> pd.DataFrame:
    q = """
        SELECT m.*, th.team_name AS home_team, ta.team_name AS away_team
        FROM matches m
        JOIN teams th ON th.team_id=m.home_team_id
        JOIN teams ta ON ta.team_id=m.away_team_id
        WHERE m.status='FullTime' AND m.fotmob_match_id IS NOT NULL
    """
    params = []
    if season:
        q += " AND m.season_id=?"
        params.append(f"mls-{season}")
    q += " ORDER BY m.match_date DESC"
    with connect() as conn:
        return pd.read_sql_query(q, conn, params=params)


def load_match_detail(match_id: str) -> dict[str, pd.DataFrame]:
    with connect() as conn:
        events = pd.read_sql_query("SELECT * FROM match_events WHERE match_id=? ORDER BY normalized_minute", conn, params=(match_id,))
        subs = pd.read_sql_query("SELECT * FROM substitutions WHERE match_id=? ORDER BY normalized_minute", conn, params=(match_id,))
        intervals = pd.read_sql_query("SELECT * FROM player_match_intervals WHERE match_id=?", conn, params=(match_id,))
        apps = pd.read_sql_query("SELECT * FROM substitute_appearances WHERE match_id=?", conn, params=(match_id,))
    return {"events": events, "substitutions": subs, "intervals": intervals, "appearances": apps}


def meta_banner() -> str:
    return f"Model {MODEL_VERSION} · Data cutoff {settings.data_cutoff_date} · MLS first team only · Associations, not causal effects"