PYTHON ?= .venv/bin/python
export PYTHONPATH := src:$(PYTHONPATH)

.PHONY: install db ingest pipeline validate exports test lint app all ci

.venv:
	python3 -m venv .venv
	.venv/bin/pip install -q -U pip

install: .venv
	$(PYTHON) -m pip install -q -r requirements.txt
	$(PYTHON) -m pip install -q -e .

db:
	$(PYTHON) -c "from mls_bench_impact.db.database import init_db; print(init_db())"

ingest:
	$(PYTHON) -m mls_bench_impact.pipeline

pipeline: ingest
	$(PYTHON) -c "from mls_bench_impact.validation.run_validation import run_validation; print(run_validation())"
	$(PYTHON) -c "from mls_bench_impact.db.database import db_session; from mls_bench_impact.exports.excel_export import export_workbook, export_csvs; \
from mls_bench_impact.exports.pdf_report import export_player_pdf; \
\
with db_session() as conn: \
  print(export_workbook(conn)); \
  print(export_csvs(conn)); \
  import pandas as pd; \
  top=pd.read_sql_query(\"SELECT player_id FROM player_bench_scores WHERE evaluation_period='2025-2026' AND overall_rank=1\", conn); \
  print(export_player_pdf(conn, top.iloc[0]['player_id']) if len(top) else 'no top player')"

validate:
	$(PYTHON) -c "from mls_bench_impact.validation.run_validation import run_validation; print(run_validation())"

exports:
	$(PYTHON) -c "from mls_bench_impact.db.database import db_session; from mls_bench_impact.exports.excel_export import export_workbook, export_csvs; \
\
with db_session() as conn: print(export_workbook(conn)); print(export_csvs(conn))"

test:
	$(PYTHON) -m pytest tests -q

lint:
	$(PYTHON) -m ruff check src tests || true

app:
	$(PYTHON) -m streamlit run src/mls_bench_impact/app/streamlit_app.py --server.headless true

all: install db pipeline test
	@echo "MLS Bench Impact production build complete"

ci: install lint test
	$(PYTHON) -c "from pathlib import Path; req=['README.md','DATA_FEASIBILITY_AUDIT.md','docs/methodology.md','docs/deployment.md'];\
assert all(Path(p).exists() for p in req), req"