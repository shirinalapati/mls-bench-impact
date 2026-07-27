from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from mls_bench_impact.config.settings import settings
from mls_bench_impact.utils.http import get_text, polite_pause
from mls_bench_impact.utils.text import normalize_name, normalize_team_name

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    re.DOTALL,
)


def _cache_dir() -> Path:
    path = settings.raw_dir / "fotmob"
    path.mkdir(parents=True, exist_ok=True)
    return path


def parse_next_data(html: str) -> dict[str, Any]:
    m = NEXT_DATA_RE.search(html)
    if not m:
        raise ValueError("No __NEXT_DATA__ found")
    return json.loads(m.group(1))


def fetch_league_fixtures(season: str, force: bool = False) -> list[dict]:
    cache = _cache_dir() / f"fixtures_{season}.json"
    if cache.exists() and not force:
        return json.loads(cache.read_text(encoding="utf-8"))
    url = f"{settings.fotmob_base_url}/leagues/{settings.fotmob_league_id}/overview/mls"
    html = get_text(url, params={"season": season})
    props = parse_next_data(html)["props"]["pageProps"]
    matches = props.get("fixtures", {}).get("allMatches") or []
    cache.write_text(json.dumps(matches), encoding="utf-8")
    return matches


def match_cache_path(match_id: str) -> Path:
    return _cache_dir() / "matches" / f"{match_id}.json"


def fetch_match_payload(match_id: str, force: bool = False) -> dict[str, Any] | None:
    cache = match_cache_path(str(match_id))
    cache.parent.mkdir(parents=True, exist_ok=True)
    if cache.exists() and not force:
        return json.loads(cache.read_text(encoding="utf-8"))
    url = f"{settings.fotmob_base_url}/match/{match_id}"
    try:
        html = get_text(url)
        props = parse_next_data(html)["props"]["pageProps"]
        slim = {
            "general": props.get("general"),
            "header": props.get("header"),
            "content": {
                "matchFacts": props.get("content", {}).get("matchFacts"),
                "lineup": props.get("content", {}).get("lineup"),
                "playerStats": props.get("content", {}).get("playerStats"),
                "shotmap": props.get("content", {}).get("shotmap"),
                "stats": props.get("content", {}).get("stats"),
            },
        }
        cache.write_text(json.dumps(slim), encoding="utf-8")
        polite_pause()
        return slim
    except Exception as exc:  # noqa: BLE001
        err_path = cache.with_suffix(".error.txt")
        err_path.write_text(str(exc), encoding="utf-8")
        return None


def fetch_matches_bulk(match_ids: list[str], force: bool = False, max_workers: int | None = None) -> dict[str, dict]:
    out: dict[str, dict] = {}
    pending = []
    for mid in match_ids:
        cache = match_cache_path(str(mid))
        if cache.exists() and not force:
            out[str(mid)] = json.loads(cache.read_text(encoding="utf-8"))
        else:
            pending.append(str(mid))

    workers = max_workers or settings.fotmob_concurrency
    if not pending:
        return out

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fetch_match_payload, mid, force): mid for mid in pending}
        for fut in as_completed(futs):
            mid = futs[fut]
            payload = fut.result()
            if payload:
                out[mid] = payload
    return out


def extract_stat(player_stats_block: dict, key: str) -> float | None:
    for section in player_stats_block.get("stats") or []:
        stats = section.get("stats") or {}
        for _label, payload in stats.items():
            if payload.get("key") == key:
                stat = payload.get("stat") or {}
                val = stat.get("value")
                if val is None:
                    return None
                try:
                    return float(val)
                except (TypeError, ValueError):
                    return None
    return None


def ensure_fotmob_team(conn, fotmob_team_id: str | int, name: str) -> str:
    team_id = f"fm:{fotmob_team_id}"
    conn.execute(
        """
        INSERT INTO teams(team_id, fotmob_team_id, team_name, normalized_name)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(team_id) DO UPDATE SET team_name=excluded.team_name, normalized_name=excluded.normalized_name
        """,
        (team_id, str(fotmob_team_id), name, normalize_team_name(name)),
    )
    return team_id


def ensure_fotmob_player(conn, fotmob_player_id: str | int, name: str, is_gk: bool = False) -> str:
    player_id = f"fm:{fotmob_player_id}"
    conn.execute(
        """
        INSERT INTO players(player_id, fotmob_player_id, player_name, normalized_name, is_goalkeeper, is_synthetic)
        VALUES (?, ?, ?, ?, ?, 0)
        ON CONFLICT(player_id) DO UPDATE SET
          player_name=excluded.player_name,
          normalized_name=excluded.normalized_name,
          is_goalkeeper=CASE
            WHEN excluded.is_goalkeeper=1 OR players.is_goalkeeper=1 THEN 1 ELSE 0 END
        """,
        (player_id, str(fotmob_player_id), name, normalize_name(name), 1 if is_gk else 0),
    )
    return player_id


def finished_match_ids(season: str, force: bool = False) -> list[str]:
    fixtures = fetch_league_fixtures(season, force=force)
    ids = []
    for m in fixtures:
        st = m.get("status") or {}
        if st.get("finished") and not st.get("cancelled"):
            ids.append(str(m["id"]))
    return ids