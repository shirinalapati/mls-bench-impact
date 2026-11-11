from __future__ import annotations

import time
from typing import Any

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from mls_bench_impact.config.settings import settings

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": (
            "MLS-Bench-Impact/1.0 (+research portfolio; polite cache; "
            "contact: local-dev)"
        ),
        "Accept": "application/json,text/html",
    }
)


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=1, max=20))
def get_json(url: str, params: dict[str, Any] | None = None) -> Any:
    resp = SESSION.get(url, params=params, timeout=settings.request_timeout_s)
    resp.raise_for_status()
    return resp.json()


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=1, max=20))
def get_text(url: str, params: dict[str, Any] | None = None) -> str:
    resp = SESSION.get(url, params=params, timeout=settings.request_timeout_s)
    resp.raise_for_status()
    return resp.text


def polite_pause(seconds: float | None = None) -> None:
    time.sleep(seconds if seconds is not None else settings.fotmob_delay_s)