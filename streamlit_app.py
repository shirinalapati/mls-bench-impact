"""Root entrypoint for Streamlit Community Cloud."""
from __future__ import annotations

import os
from pathlib import Path

# Prefer packaged release DB on cloud hosts without a pipeline run
release_db = Path(__file__).resolve().parent / "data" / "release" / "mls_bench_impact.db"
if release_db.exists() and not os.environ.get("MBI_DB_PATH"):
    os.environ["MBI_DB_PATH"] = str(release_db)

from mls_bench_impact.app.streamlit_app import *  # noqa: E402,F403