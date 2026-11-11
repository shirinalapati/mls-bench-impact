from __future__ import annotations

import json
import os
import traceback
import uuid
from datetime import UTC, date, datetime

from mls_bench_impact import MODEL_VERSION
from mls_bench_impact.config.settings import settings
from mls_bench_impact.db.database import db_session, init_db
from mls_bench_impact.ingest import asa
from mls_bench_impact.scoring.bench_impact import compute_period_scores, persist_scores
from mls_bench_impact.transform.intervals import build_all_intervals


def _now() -> str:
    return datetime.now(UTC).isoformat()


def run_pipeline(
    seasons: tuple[str, ...] | None = None,
    force_fetch: bool = False,
    skip_fotmob: bool = False,
) -> dict:
    seasons = seasons or settings.seasons
    if not os.environ.get("MBI_DATA_CUTOFF_DATE"):
        settings.data_cutoff_date = date.today().isoformat()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    settings.reports_dir.mkdir(parents=True, exist_ok=True)

    run_id = str(uuid.uuid4())
    stages: dict[str, object] = {}
    init_db()
    status = "ok"
    error_message = None

    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO pipeline_runs(pipeline_run_id, started_at, status, stages_json, data_cutoff_date)
            VALUES (?, ?, 'running', '{}', ?)
            """,
            (run_id, _now(), settings.data_cutoff_date),
        )
        try:
            stages["asa_reference"] = asa.ingest_asa_reference(conn, force=force_fetch)
            stages["asa_games"] = asa.ingest_asa_games(conn, seasons=seasons, force=force_fetch)
            stages["asa_player_metrics"] = asa.ingest_asa_player_metrics(conn, seasons=seasons, force=force_fetch)
            stages["asa_positions"] = asa.backfill_positions_from_xgoals(conn, seasons=seasons, force=False)

            if not skip_fotmob:
                stages["intervals"] = build_all_intervals(conn, seasons=seasons, force_fetch=force_fetch)

            # Backfill individual metrics from FotMob when ASA G+ is absent
            conn.execute(
                """
                UPDATE substitute_appearances
                SET player_xg = COALESCE(player_xg, (
                      SELECT m.fotmob_xg FROM player_match_metrics m
                      WHERE m.match_id = substitute_appearances.match_id
                        AND m.player_id = substitute_appearances.player_id
                        AND m.source = 'fotmob'
                    )),
                    player_xa = COALESCE(player_xa, (
                      SELECT m.fotmob_xa FROM player_match_metrics m
                      WHERE m.match_id = substitute_appearances.match_id
                        AND m.player_id = substitute_appearances.player_id
                        AND m.source = 'fotmob'
                    )),
                    player_shots = COALESCE(player_shots, (
                      SELECT m.shots FROM player_match_metrics m
                      WHERE m.match_id = substitute_appearances.match_id
                        AND m.player_id = substitute_appearances.player_id
                        AND m.source = 'fotmob'
                    ))
                """
            )

            # strength attach for appearances
            strength = asa.load_team_strength_map(seasons=seasons, force=False)
            apps = conn.execute("SELECT appearance_id, match_id, team_id, opponent_id FROM substitute_appearances").fetchall()
            for a in apps:
                # map asa ids
                m = conn.execute("SELECT asa_game_id FROM matches WHERE match_id=?", (a["match_id"],)).fetchone()
                t = conn.execute("SELECT asa_team_id FROM teams WHERE team_id=?", (a["team_id"],)).fetchone()
                o = conn.execute("SELECT asa_team_id FROM teams WHERE team_id=?", (a["opponent_id"],)).fetchone()
                if not m or not m["asa_game_id"]:
                    continue
                ts = strength.get((t["asa_team_id"], m["asa_game_id"]), 0) if t and t["asa_team_id"] else 0
                os_ = strength.get((o["asa_team_id"], m["asa_game_id"]), 0) if o and o["asa_team_id"] else 0
                conn.execute(
                    "UPDATE substitute_appearances SET team_strength=?, opponent_strength=? WHERE appearance_id=?",
                    (ts, os_, a["appearance_id"]),
                )

            score_counts = {}
            for period in ("2025", "2026", "2025-2026"):
                scores = compute_period_scores(conn, period=period)
                score_counts[period] = persist_scores(conn, scores, period)
                model_run_id = f"{MODEL_VERSION}-{period}-{run_id[:8]}"
                conn.execute(
                    """
                    INSERT INTO model_runs(model_run_id, model_version, data_version, evaluation_period, started_at, finished_at, parameters_json, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'ok')
                    """,
                    (
                        model_run_id,
                        MODEL_VERSION,
                        f"asa+fotmob-{settings.data_cutoff_date}",
                        period,
                        _now(),
                        _now(),
                        json.dumps(
                            {
                                "weights": [settings.bis_weight_ssi, settings.bis_weight_ati, settings.bis_weight_pif],
                                "prior_strength": settings.prior_strength_minutes,
                                "min_apps": settings.min_sub_appearances,
                                "min_minutes": settings.min_sub_minutes,
                            }
                        ),
                    ),
                )
            stages["scores"] = score_counts

            # exports + validation invoked by caller scripts to keep pipeline import light
            conn.execute(
                """
                UPDATE pipeline_runs SET finished_at=?, status=?, stages_json=? WHERE pipeline_run_id=?
                """,
                (_now(), status, json.dumps(stages), run_id),
            )
        except Exception as exc:  # noqa: BLE001
            status = "error"
            error_message = f"{exc}\n{traceback.format_exc()}"
            conn.execute(
                """
                UPDATE pipeline_runs SET finished_at=?, status=?, stages_json=?, error_message=? WHERE pipeline_run_id=?
                """,
                (_now(), status, json.dumps(stages), error_message, run_id),
            )
            raise

    return {"run_id": run_id, "status": status, "stages": stages, "db_path": str(settings.db_path)}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run MLS Bench Impact production pipeline")
    parser.add_argument("--force-fetch", action="store_true")
    parser.add_argument("--skip-fotmob", action="store_true")
    parser.add_argument("--seasons", nargs="*", default=None)
    args = parser.parse_args()
    seasons = tuple(args.seasons) if args.seasons else None
    result = run_pipeline(seasons=seasons, force_fetch=args.force_fetch, skip_fotmob=args.skip_fotmob)
    print(json.dumps(result, indent=2))