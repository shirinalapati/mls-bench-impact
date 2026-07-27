#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from mls_bench_impact.config.constants import POSITION_GROUPS
from mls_bench_impact.db.database import connect


def main() -> None:
    conn = connect()
    asa_dir = Path("data/raw/asa")
    pos_counts: dict[str, Counter] = {}
    for season in ("2025", "2026"):
        rows = json.loads((asa_dir / f"player_xgoals_games_{season}.json").read_text())
        for r in rows:
            pos_counts.setdefault(r["player_id"], Counter())[r.get("general_position")] += 1

    updates = 0
    for asa_id, ctr in pos_counts.items():
        pos = ctr.most_common(1)[0][0]
        if not pos or pos == "GK":
            if pos == "GK":
                conn.execute(
                    "UPDATE players SET primary_position='GK', position_group='Goalkeepers', is_goalkeeper=1 WHERE asa_player_id=?",
                    (asa_id,),
                )
            continue
        pg = POSITION_GROUPS.get(pos, "Central and defensive midfielders")
        cur = conn.execute(
            "UPDATE players SET primary_position=?, position_group=? WHERE asa_player_id=?",
            (pos, pg, asa_id),
        )
        updates += cur.rowcount
    print("player updates", updates)

    cur = conn.execute(
        """
        UPDATE substitute_appearances
        SET position_group=(SELECT position_group FROM players WHERE players.player_id=substitute_appearances.player_id),
            entering_position=(SELECT primary_position FROM players WHERE players.player_id=substitute_appearances.player_id)
        WHERE EXISTS(
          SELECT 1 FROM players p
          WHERE p.player_id=substitute_appearances.player_id AND p.position_group IS NOT NULL
        )
        """
    )
    print("app updates", cur.rowcount)
    cur = conn.execute(
        """
        UPDATE starter_appearances
        SET position_group=(SELECT position_group FROM players WHERE players.player_id=starter_appearances.player_id)
        WHERE EXISTS(
          SELECT 1 FROM players p
          WHERE p.player_id=starter_appearances.player_id AND p.position_group IS NOT NULL
        )
        """
    )
    print("starter updates", cur.rowcount)
    conn.commit()
    for name in ["Hirving Lozano", "Ramiro Enrique", "Cengiz Ünder", "Francis Westfield", "Bruno Damiani"]:
        row = conn.execute(
            "SELECT primary_position, position_group FROM players WHERE player_name=?",
            (name,),
        ).fetchone()
        print(name, dict(row) if row else None)
    conn.close()


if __name__ == "__main__":
    main()