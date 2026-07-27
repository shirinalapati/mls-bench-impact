from __future__ import annotations

import re
import unicodedata


def normalize_name(name: str | None) -> str:
    if not name:
        return ""
    text = unicodedata.normalize("NFKD", str(name))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    # common particle noise
    for token in (" jr", " sr", " ii", " iii", " iv"):
        if text.endswith(token):
            text = text[: -len(token)].strip()
    return text


TEAM_ALIASES = {
    "st louis city": "st louis city sc",
    "st. louis city": "st louis city sc",
    "st louis city sc": "st louis city sc",
    "la galaxy": "la galaxy",
    "los angeles galaxy": "la galaxy",
    "los angeles fc": "los angeles fc",
    "lafc": "los angeles fc",
    "inter miami": "inter miami cf",
    "inter miami cf": "inter miami cf",
    "nycfc": "new york city fc",
    "new york city fc": "new york city fc",
    "new york red bulls": "new york red bulls",
    "red bull new york": "new york red bulls",
    "minnesota united": "minnesota united fc",
    "minnesota united fc": "minnesota united fc",
    "austin fc": "austin fc",
    "charlotte fc": "charlotte fc",
    "fc cincinnati": "fc cincinnati",
    "columbus crew": "columbus crew",
    "chicago fire": "chicago fire fc",
    "chicago fire fc": "chicago fire fc",
    "fc dallas": "fc dallas",
    "houston dynamo": "houston dynamo fc",
    "houston dynamo fc": "houston dynamo fc",
    "sporting kansas city": "sporting kansas city",
    "real salt lake": "real salt lake",
    "san jose earthquakes": "san jose earthquakes",
    "seattle sounders": "seattle sounders fc",
    "seattle sounders fc": "seattle sounders fc",
    "portland timbers": "portland timbers",
    "vancouver whitecaps": "vancouver whitecaps fc",
    "vancouver whitecaps fc": "vancouver whitecaps fc",
    "cf montreal": "cf montreal",
    "montreal impact": "cf montreal",
    "toronto fc": "toronto fc",
    "orlando city": "orlando city sc",
    "orlando city sc": "orlando city sc",
    "philadelphia union": "philadelphia union",
    "dc united": "d c united",
    "d.c. united": "d c united",
    "d c united": "d c united",
    "new england revolution": "new england revolution",
    "nashville sc": "nashville sc",
    "atlanta united": "atlanta united fc",
    "atlanta united fc": "atlanta united fc",
    "san diego fc": "san diego fc",
}


def normalize_team_name(name: str | None) -> str:
    n = normalize_name(name)
    return TEAM_ALIASES.get(n, n)