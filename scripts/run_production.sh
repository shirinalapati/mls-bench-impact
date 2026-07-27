#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/src:${PYTHONPATH:-}"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install -q -U pip
python -m pip install -q -r requirements.txt
python -m pip install -q -e .

python3 -c "from mls_bench_impact.db.database import init_db; print('db', init_db())"
python3 -m mls_bench_impact.pipeline

python3 - <<'PY'
from mls_bench_impact.validation.run_validation import run_validation
from mls_bench_impact.db.database import db_session
from mls_bench_impact.exports.excel_export import export_workbook, export_csvs
from mls_bench_impact.exports.pdf_report import export_player_pdf
import pandas as pd

print(run_validation())
with db_session() as conn:
    print(export_workbook(conn))
    print(export_csvs(conn))
    top = pd.read_sql_query(
        "SELECT player_id FROM player_bench_scores WHERE evaluation_period='2025-2026' AND overall_rank=1",
        conn,
    )
    if len(top):
        print(export_player_pdf(conn, top.iloc[0]["player_id"]))
PY

python3 -m pytest tests -q
echo "Starting Streamlit app on port 8501"
exec python3 -m streamlit run src/mls_bench_impact/app/streamlit_app.py --server.port 8501