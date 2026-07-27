import sqlite3
from pathlib import Path

import pytest

from mls_bench_impact.db.database import init_db
from mls_bench_impact.config.settings import settings


@pytest.fixture(scope="module")
def db_path(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "test.db"
    init_db(path)
    return path


def test_schema_has_core_tables(db_path):
    conn = sqlite3.connect(db_path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    for t in [
        "players",
        "teams",
        "matches",
        "substitutions",
        "player_match_intervals",
        "substitute_appearances",
        "player_bench_scores",
        "model_runs",
    ]:
        assert t in tables


def test_no_synthetic_insert(db_path):
    conn = sqlite3.connect(db_path)
    with pytest.raises(Exception):
        conn.execute(
            "INSERT INTO players(player_id, player_name, normalized_name, is_synthetic) VALUES ('x','Demo','demo',1)"
        )
        conn.commit()


def test_production_db_no_synthetic_if_present():
    if not Path(settings.db_path).exists():
        pytest.skip("production db not built")
    conn = sqlite3.connect(settings.db_path)
    n = conn.execute("SELECT COUNT(*) FROM players WHERE is_synthetic=1").fetchone()[0]
    assert n == 0