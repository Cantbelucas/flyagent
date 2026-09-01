"""Kort resume af soegningen som tekst.

Bruges naar agenten koerer i skyen: resume.md bliver til den mail, du faar,
og status.json fortaeller automatikken, om der er noget nyt at raabe op om.
"""
from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path

UGEDAG = ["man", "tir", "ons", "tor", "fre", "lør", "søn"]
MAANED = ["jan", "feb", "mar", "apr", "maj", "jun",
          "jul", "aug", "sep", "okt", "nov", "dec"]


def kr(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def dato(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{UGEDAG[d.weekday()]}. {d.day}. {MAANED[d.month - 1]}"


def _ben(r: dict, valuta: str) -> str:
    stop = "direkte" if r.get("stops") == 0 else f"{r.get('stops')} stop"
    if r.get("layover"):
        stop += f" via {r['layover']}"
    minutter = r.get("duration_min") or 0
    tid = f"{minutter // 60}t{minutter % 60:02d}"
    linje = (f"**{kr(r['price'])} {valuta}** &middot; {dato(r['dato'])} &middot; "
             f"{r['fra']}&rarr;{r['til']} &middot; {r.get('airline') or '?'} "
             f"({r.get('stjerner') or '?'}&#9733;) &middot; {stop} &middot; {tid}")
    if r.get("kabine_detalje"):
        linje += f" &middot; {r['kabine_detalje']}"
    url = r.get("koeb_url") or r.get("google")
    saelger = (r.get("saelgere") or [{}])[0].get("navn")
    linje += f"\n  [{'Køb hos ' + saelger if saelger else 'Åbn bookingsiden'}]({url})"
    return linje


def _tabel(raekker: list[dict], valuta: str, antal: int = 5) -> str:
    if not raekker:
        return "_Ingen afgange opfyldte kravene._\n"
    ud = ["| Pris | Dato | Selskab | Stop | Tid | Køb |", "|---|---|---|---|---|---|"]
    for r in raekker[:antal]:
        minutter = r.get("duration_min") or 0
        stop = "direkte" if r.get("stops") == 0 else f"{r.get('stops')} stop"
        url = r.get("koeb_url") or r.get("google")
        saelger = (r.get("saelgere") or [{}])[0].get("navn") or "Google Flights"
        ud.append(f"| {kr(r['price'])} {valuta} | {dato(r['dato'])} "
                  f"| {r.get('airline') or '?'} {(r.get('stjerner') or '?')}&#9733; "
                  f"| {stop} | {minutter // 60}t{minutter % 60:02d} "
                  f"| [{saelger}]({url}) |")
    return "\n".join(ud) + "\n"


def skriv(mappe: Path, k: dict, ud: list[dict], hjem: list[dict], par: list[dict],
          naer_ud: list[dict], naer_hjem: list[dict], faldet) -> str:
    valuta = k["valuta"]
    nu = time.strftime("%d-%m-%Y %H:%M")
    linjer = [f"## Fly {k['udrejse']['fra']} &rarr; "
              f"{'/'.join(k['udrejse']['til'])} &rarr; {k['hjemrejse']['til']}",
              f"_Søgt {nu}. Priser er pr. person._\n"]

    if par:
        b = par[0]
        inden_for = b["i_alt"] <= k["samlet_budget"]
        if faldet:
            linjer.append(f"### 🔻 Prisfald: {kr(faldet)} {valuta} billigere pr. person\n")
        linjer += [
            f"### {kr(b['pr_person'])} {valuta} pr. person "
            f"&middot; {kr(b['i_alt'])} {valuta} for {k['personer']}",
            f"{'✅ Inden for' if inden_for else '⚠️ Over'} budgettet på "
            f"{kr(k['samlet_budget'])} {valuta}\n",
            f"- **Ud:** {_ben(b['ud'], valuta)}",
            f"- **Hjem:** {_ben(b['hjem'], valuta)}\n",
        ]
    else:
        linjer.append("### Ingen komplet rejse opfylder alle kriterierne lige nu\n")

    linjer += ["### Udrejse", _tabel(ud, valuta), "### Hjemrejse", _tabel(hjem, valuta)]

    naer = [r for r in (list(naer_ud[:3]) + list(naer_hjem[:3]))]
    if naer:
        linjer.append("### Tættest på")
        for r in naer:
            linjer.append(f"- {kr(r['price'])} {valuta} &middot; {dato(r['dato'])} "
                          f"&middot; {r.get('airline') or '?'} &middot; "
                          f"mangler: {r.get('aarsag') or '?'}")
        linjer.append("")

    linjer.append("Hele rapporten med alle afgange ligger i "
                  "`resultater/rejseplan.html`.")
    tekst = "\n".join(linjer)

    (mappe / "resume.md").write_text(tekst, encoding="utf-8")
    (mappe / "status.json").write_text(json.dumps({
        "tidspunkt": nu,
        "prisfald": faldet or 0,
        "billigste_pr_person": par[0]["pr_person"] if par else None,
        "billigste_i_alt": par[0]["i_alt"] if par else None,
        "antal_udrejser": len(ud),
        "antal_hjemrejser": len(hjem),
        "inden_for_budget": bool(par and par[0]["i_alt"] <= k["samlet_budget"]),
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    return tekst
