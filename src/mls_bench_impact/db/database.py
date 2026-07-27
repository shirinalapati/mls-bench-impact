from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from mls_bench_impact.config.settings import settings

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = Path(db_path or settings.db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(db_path: Path | None = None) -> Path:
    path = Path(db_path or settings.db_path)
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with connect(path) as conn:
        conn.executescript(schema)
        conn.execute(
            """
            INSERT OR IGNORE INTO competitions(competition_id, competition_name, competition_code)
            VALUES ('mls', 'Major League Soccer', 'MLS')
            """
        )
        for season in settings.seasons:
            conn.execute(
                """
                INSERT OR IGNORE INTO seasons(season_id, competition_id, season_name)
                VALUES (?, 'mls', ?)
                """,
                (f"mls-{season}", season),
            )
        conn.execute(
            """
            INSERT OR IGNORE INTO data_sources(source_id, source_name, source_type, base_url, notes)
            VALUES
            ('asa', 'American Soccer Analysis API', 'api', ?, 'Game-level G+/xG'),
            ('fotmob', 'FotMob match pages', 'web_hydration', ?, 'Lineups, events, shotmap')
            """,
            (settings.asa_base_url, settings.fotmob_base_url),
        )
        conn.commit()
    return path


@contextmanager
def db_session(db_path: Path | None = None):
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()