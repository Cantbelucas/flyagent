"""Slaar flyselskabernes stjerner op i flyselskaber.json.

Google skriver flere selskaber sammen i en streng: "FinnairJAL",
"Scandinavian Airlines, LOT", "LufthansaANA". Vi finder derfor alle kendte navne
som delstrenge og ser, hvad der er tilbage bagefter.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

Db = dict


def load(path: str | Path = "flyselskaber.json") -> Db:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data["selskaber"]


def _pattern(name: str) -> re.Pattern:
    """Korte navne (ANA, JAL, LOT) skal matche praecist - ellers rammer de inde i
    andre ord. Lange navne matcher vi frit og uden hensyn til store bogstaver."""
    if len(name) <= 4:
        return re.compile(r"(?<![A-Za-z])" + re.escape(name) + r"(?![a-z])")
    return re.compile(re.escape(name), re.I)


def match_carriers(label: str, db: Db) -> tuple[list[tuple[str, int]], str]:
    """-> ([(selskab, stjerner), ...], resten der ikke kunne genkendes)"""
    rest = label or ""
    found: dict[str, int] = {}
    # Laengste navne forst, saa "Scandinavian Airlines" vinder over "SAS".
    for name in sorted(db, key=len, reverse=True):
        pat = _pattern(name)
        if pat.search(rest):
            found[name] = db[name]["stjerner"]
            rest = pat.sub(" ", rest)
    leftovers = re.sub(r"[^A-Za-z0-9 ]+", " ", rest)
    leftovers = " ".join(w for w in leftovers.split() if len(w) > 1)
    return sorted(found.items(), key=lambda kv: -kv[1]), leftovers


def vurder(label: str, db: Db, min_stjerner: int) -> dict:
    """Godkender et tilbud ud fra alle de selskaber, der flyver strackningen."""
    carriers, ukendt = match_carriers(label, db)
    stjerner = min((s for _, s in carriers), default=None)

    if ukendt:
        status = "ukendt"
        note = f"kender ikke '{ukendt}'"
    elif not carriers:
        status = "ukendt"
        note = "intet selskab oplyst"
    elif stjerner < min_stjerner:
        status = "afvist"
        lav = ", ".join(n for n, s in carriers if s < min_stjerner)
        note = f"{lav} har {stjerner} stjerner"
        status = "afvist"
    else:
        status = "ok"
        note = ""

    return {
        "status": status,
        "note": note,
        "stjerner": stjerner,
        "selskaber": [n for n, _ in carriers],
        "ukendt": ukendt,
        "booking": next((db[n].get("booking") for n, _ in carriers if db[n].get("booking")), None),
    }
