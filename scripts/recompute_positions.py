#!/usr/bin/env python3
"""Recompute appearance position groups from ASA primary pos or FotMob usual role."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from mls_bench_impact.config.constants import POSITION_GROUPS
from mls_bench_impact.db.database import connect
from mls_bench_impact.transform.identity import load_aliases
from mls_bench_impact.transform.intervals import _pos_group_from_codes
from mls_bench_impact.utils.text import normalize_name


def main() -> None:
    conn = connect()
    # Apply aliases: attach fotmob ids / merge Francis->Frankie
    aliases = load_aliases()
    for fotmob_name, asa_id in aliases.items():
        asa = conn.execute("SELECT player_id FROM players WHERE asa_player_id=?", (asa_id,)).fetchone()
        fm = conn.execute(
            "SELECT player_id, fotmob_player_id FROM players WHERE normalized_name=? AND fotmob_player_id IS NOT NULL",
            (fotmob_name,),
        ).fetchone()
        if asa and fm:
            conn.execute(
                "UPDATE players SET fotmob_player_id=? WHERE player_id=?",
                (fm["fotmob_player_id"], asa["player_id"]),
            )
            # remap appearances from fm id to asa id
            for table in ("substitute_appearances", "starter_appearances", "player_match_intervals", "lineups"):
                conn.execute(
                    f"UPDATE {table} SET player_id=? WHERE player_id=?",
                    (asa["player_id"], fm["player_id"]),
                )

    # ASA positions
    from mls_bench_impact.ingest import asa as asa_mod

    asa_mod.backfill_positions_from_xgoals(conn)

    # FotMob usual role modal per fotmob player id
    usual_modes: dict[str, int] = {}
    slot_modes: dict[str, int] = {}
    usual_counts: dict[str, Counter] = defaultdict(Counter)
    slot_counts: dict[str, Counter] = defaultdict(Counter)
    for fp in Path("data/raw/fotmob/matches").glob("*.json"):
        d = json.loads(fp.read_text())
        lineup = (d.get("content") or {}).get("lineup") or {}
        for side in ("homeTeam", "awayTeam"):
            team = lineup.get(side) or {}
            for bucket in ("starters", "subs"):
                for p in team.get(bucket) or []:
                    pid = str(p.get("id"))
                    if p.get("usualPlayingPositionId") is not None:
                        usual_counts[pid][int(p["usualPlayingPositionId"])] += 1
                    if p.get("positionId") is not None:
                        slot_counts[pid][int(p["positionId"])] += 1
    for pid, ctr in usual_counts.items():
        usual_modes[pid] = ctr.most_common(1)[0][0]
    for pid, ctr in slot_counts.items():
        slot_modes[pid] = ctr.most_common(1)[0][0]

    players = conn.execute("SELECT player_id, asa_player_id, fotmob_player_id, primary_position, position_group FROM players").fetchall()
    for p in players:
        if p["primary_position"]:
            pg = POSITION_GROUPS.get(p["primary_position"], p["position_group"])
            conn.execute("UPDATE players SET position_group=? WHERE player_id=?", (pg, p["player_id"]))
            continue
        fm = p["fotmob_player_id"]
        if not fm:
            continue
        usual = usual_modes.get(str(fm))
        slot = slot_modes.get(str(fm))
        pg = _pos_group_from_codes(slot, usual, None)
        conn.execute("UPDATE players SET position_group=? WHERE player_id=?", (pg, p["player_id"]))

    conn.execute(
        """
        UPDATE substitute_appearances
        SET position_group=(SELECT position_group FROM players WHERE players.player_id=substitute_appearances.player_id),
            entering_position=(SELECT primary_position FROM players WHERE players.player_id=substitute_appearances.player_id)
        """
    )
    conn.execute(
        """
        UPDATE starter_appearances
        SET position_group=(SELECT position_group FROM players WHERE players.player_id=starter_appearances.player_id)
        """
    )
    conn.commit()
    for name in ["Hirving Lozano", "Ramiro Enrique", "Cengiz Ünder", "Francis Westfield", "Frankie Westfield", "Bruno Damiani"]:
        row = conn.execute(
            "SELECT player_id, primary_position, position_group, fotmob_player_id, asa_player_id FROM players WHERE player_name=?",
            (name,),
        ).fetchone()
        print(name, dict(row) if row else None)
    conn.close()


if __name__ == "__main__":
    main()