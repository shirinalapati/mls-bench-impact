# Deployment

## Local production run

```bash
chmod +x scripts/run_production.sh
./scripts/run_production.sh
```

Or stepwise:

```bash
make install
make pipeline
make app
```

## Streamlit Community Cloud

1. Push repository to GitHub  
2. Create a Streamlit Cloud app pointed at `src/mls_bench_impact/app/streamlit_app.py`  
3. Set Python version ≥3.11  
4. Either commit a built `data/processed/mls_bench_impact.db` or run the pipeline in a Cloud job/build step before serving  

## Environment

| Variable | Default | Meaning |
| --- | --- | --- |
| `MBI_DB_PATH` | `data/processed/mls_bench_impact.db` | SQLite path |
| `MBI_ALLOW_SYNTHETIC` | `false` | Must remain false in production |

## Health expectations

- Banner shows model version + data cutoff  
- Empty states when DB missing  
- Export buttons/paths under `data/exports/`  
- Failed refresh should leave last good DB intact (pipeline writes after successful stages)