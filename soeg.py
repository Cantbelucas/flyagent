"""Rejseagent der søger efter præcis de fly, der står i kriterier.json.

Udrejse og hjemrejse søges som to enkeltbilletter, så du kan flyve premium
economy ud, business hjem – og komme hjem fra en anden by, end du fløj til.

Køres normalt bare ved at dobbeltklikke på SOEG-FLY.bat.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import flyselskaber
import gflights as g
import links as booking
import rejserapport
import resume

HER = Path(__file__).parent
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

KABINE_NAVN = {"economy": "Economy", "premium": "Premium economy",
               "business": "Business", "first": "First"}


# --------------------------------------------------------------------------
# Opgaver ud fra kriterierne
# --------------------------------------------------------------------------

def datoer(fra: str, til: str) -> list[str]:
    d, slut = date.fromisoformat(fra), date.fromisoformat(til)
    i_dag = date.today()
    ud = []
    while d <= slut:
        if d >= i_dag:
            ud.append(d.isoformat())
        d += timedelta(days=1)
    return ud


def byg_opgaver(k: dict) -> list[dict]:
    opgaver = []
    for ben, spec in (("ud", k["udrejse"]), ("hjem", k["hjemrejse"])):
        afgange = [spec["fra"]] if isinstance(spec["fra"], str) else spec["fra"]
        maal = [spec["til"]] if isinstance(spec["til"], str) else spec["til"]
        kabiner = spec["kabine"] if isinstance(spec["kabine"], list) else [spec["kabine"]]
        for dag in datoer(spec["tidligste_dato"], spec["seneste_dato"]):
            for a in afgange:
                for b in maal:
                    for kabine in kabiner:
                        opgaver.append({"ben": ben, "dato": dag, "fra": a, "til": b,
                                        "kabine": kabine, "krav": spec})
    return opgaver


# --------------------------------------------------------------------------
# Selve soegningen
# --------------------------------------------------------------------------

def bedoem(o, opg: dict, k: dict, db) -> dict:
    """Maaler et tilbud op mod kriterierne. Returnerer raekken med en status."""
    krav = opg["krav"]
    dom = flyselskaber.vurder(o.airline, db, k["min_stjerner"])
    timer = krav.get("max_rejsetid_timer")

    fejl = []
    if krav.get("max_stop") is not None and o.stops is not None and o.stops > krav["max_stop"]:
        fejl.append("kun direkte ønsket" if krav["max_stop"] == 0
                    else f"{o.stops} stop (max {krav['max_stop']})")
    if o.price > krav["max_pris_pr_person"]:
        over = o.price - krav["max_pris_pr_person"]
        fejl.append(f"{over:,} {k['valuta']} over prisloftet".replace(",", "."))
    if timer and o.duration_min and o.duration_min > timer * 60:
        fejl.append(f"{o.duration_min // 60}t rejsetid (max {timer}t)")
    stjerne_fejl = dom["status"] == "afvist"
    if stjerne_fejl:
        fejl.append(dom["note"])

    if fejl:
        status = "afvist"
    elif dom["status"] == "ukendt":
        status = "ukendt"
    else:
        status = "ok"

    return o.as_dict() | {
        "ben": opg["ben"], "dato": opg["dato"], "fra": opg["fra"], "til": opg["til"],
        "kabine": opg["kabine"], "kabine_navn": KABINE_NAVN.get(opg["kabine"], opg["kabine"]),
        "status": status, "fejl": fejl, "stjerne_fejl": stjerne_fejl,
        "aarsag": "; ".join(fejl) or dom["note"],
        "stjerner": dom["stjerner"], "selskaber": dom["selskaber"],
        "booking": dom["booking"],
    }


async def koer_opgave(ctx, opg, k, db, sem, idx, i_alt) -> list[dict]:
    url = g.search_url([(opg["dato"], opg["fra"], opg["til"])],
                       adults=1, seat=opg["kabine"], currency=k["valuta"])
    async with sem:
        tilbud = []
        for forsog in (1, 2):
            try:
                tilbud = await g.fetch_offers(ctx, url, k["valuta"], limit=12)
                break
            except Exception as exc:
                if forsog == 2:
                    print(f"  [{idx}/{i_alt}] {opg['dato']} {opg['fra']}-{opg['til']}: "
                          f"fejlede ({type(exc).__name__})")
                    return []
                await asyncio.sleep(3)

    linker = booking.booking_links(opg["fra"], opg["til"], opg["dato"], None, 1,
                                   k["valuta"], opg["kabine"])
    raekker = [bedoem(o, opg, k, db) | {"google": url, "links": linker} for o in tilbud]

    gode = [r for r in raekker if r["status"] == "ok"]
    if gode:
        b = min(gode, key=lambda r: r["price"])
        pris = f"{b['price']:,}".replace(",", ".")
        print(f"  [{idx}/{i_alt}] {opg['dato']} {opg['fra']}-{opg['til']} "
              f"{KABINE_NAVN[opg['kabine']]:<15} -> {pris} {k['valuta']} ({b['airline']})")
    else:
        print(f"  [{idx}/{i_alt}] {opg['dato']} {opg['fra']}-{opg['til']} "
              f"{KABINE_NAVN[opg['kabine']]:<15} -> intet der opfylder kravene "
              f"({len(raekker)} tilbud set)")
    return raekker


async def soeg(k: dict, opgaver: list[dict], db) -> list[dict]:
    from playwright.async_api import async_playwright

    sem = asyncio.Semaphore(max(1, k.get("parallelle_soegninger", 3)))
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(locale="en-US", user_agent=UA,
                                        viewport={"width": 1400, "height": 1000})
        try:
            resultater = await asyncio.gather(*[
                koer_opgave(ctx, opg, k, db, sem, i, len(opgaver))
                for i, opg in enumerate(opgaver, 1)])
        finally:
            await browser.close()
    return [r for gruppe in resultater for r in gruppe]


# --------------------------------------------------------------------------
# Sammensaetning og udskrift
# --------------------------------------------------------------------------

def bedste(raekker: list[dict], ben: str, status=("ok",)) -> list[dict]:
    ude = [r for r in raekker if r["ben"] == ben and r["status"] in status]
    # Samme afgang kan optraede paa flere soegninger - behold en pr. pris/tid.
    unik = {}
    for r in ude:
        noegle = (r["dato"], r["price"], r["depart"], r["kabine"])
        unik.setdefault(noegle, r)
    return sorted(unik.values(), key=lambda r: (r["price"], r["duration_min"] or 9999))


def _saelgerpris(r: dict):
    """Den laveste pris en rigtig sælger tager - hvis vi har været på bookingsiden."""
    priser = [x["pris"] for x in (r.get("saelgere") or [])
              if isinstance(x, dict) and x.get("pris")]
    return min(priser) if priser else None


def verificer(raekker: list[dict], k: dict) -> list[dict]:
    """Retter kortprisen til den pris, sælgeren faktisk tager.

    Googles søgeresultat viser af og til en pris, der ikke holder på
    bookingsiden - vi har målt afvigelser på 89 %. Har vi først været inde
    på bookingsiden, er dét den rigtige pris, så den vinder. Bliver
    afgangen for dyr, ryger den ud af kriterierne igen.

    Returnerer de rækker, hvor prisen blev ændret.
    """
    aendret = []
    for r in raekker:
        if r.get("pris_verificeret"):
            continue
        ny_pris = _saelgerpris(r)
        if ny_pris is None:
            continue
        r["pris_verificeret"] = True
        gammel = int(r["price"])
        if ny_pris == gammel:
            continue
        r["pris_kort"], r["price"] = gammel, ny_pris

        loft = k["udrejse" if r["ben"] == "ud" else "hjemrejse"]["max_pris_pr_person"]
        if ny_pris > loft and r["status"] == "ok":
            over = f"{ny_pris - loft:,}".replace(",", ".")
            r["fejl"] = list(r["fejl"]) + [f"{over} {k['valuta']} over prisloftet"]
            r["status"] = "afvist"
            r["aarsag"] = "; ".join(r["fejl"])
            # Kun her har den rigtige pris vaeltet afgangen. De ovrige var
            # allerede afvist paa stop, rejsetid eller stjerner.
            r["pris_afvist"] = True
        aendret.append(r)
    return aendret


def naermest(raekker: list[dict], ben: str, antal: int = 8) -> list[dict]:
    """De afgange der var tættest på – dem der kun fejler på én ting.
    Selskaber under stjernekravet kommer ikke med; det krav laver vi ikke om på."""
    kandidater = [r for r in raekker
                  if r["ben"] == ben and r["status"] == "afvist" and not r["stjerne_fejl"]]
    unik = {}
    for r in kandidater:
        noegle = (r["dato"], r["price"], r["depart"], r["kabine"])
        if noegle not in unik:
            unik[noegle] = r

    # Vis de bedste fra hver kabine, saa business ikke forsvinder bag billigere
    # premium economy - det var trods alt business, du helst ville hjem paa.
    pr_kabine: dict[str, list[dict]] = {}
    for r in sorted(unik.values(), key=lambda r: (len(r["fejl"]), r["price"])):
        pr_kabine.setdefault(r["kabine"], []).append(r)
    valgte = [r for raekker in pr_kabine.values() for r in raekker[:antal // 2 or 1]]
    return sorted(valgte, key=lambda r: (len(r["fejl"]), r["price"]))[:antal]


def kombiner(ud: list[dict], hjem: list[dict], k: dict) -> list[dict]:
    par = []
    for u in ud[:12]:
        for h in hjem[:12]:
            if date.fromisoformat(h["dato"]) <= date.fromisoformat(u["dato"]):
                continue
            pr_person = u["price"] + h["price"]
            par.append({"ud": u, "hjem": h, "pr_person": pr_person,
                        "i_alt": pr_person * k["personer"]})
    par.sort(key=lambda p: (p["pr_person"], -(p["hjem"]["kabine"] == "business")))
    return par


def linje(r: dict, valuta: str) -> str:
    pris = f"{r['price']:,}".replace(",", ".")
    stop = "direkte" if r["stops"] == 0 else f"{r['stops']} stop"
    tid = f"{r['duration_min'] // 60}t{r['duration_min'] % 60:02d}" if r["duration_min"] else "-"
    return (f"{pris:>8} {valuta}  {r['dato']}  {r['fra']}-{r['til']}  "
            f"{(r['airline'] or '?')[:26]:<26} {str(r['stjerner'] or '?')}*  "
            f"{stop:<8} {tid:<7} {r['kabine_navn']}")


def afsnit(titel: str, krav: dict, valuta: str, traef: list[dict],
           naer: list[dict]) -> None:
    loft = f"{krav['max_pris_pr_person']:,}".replace(",", ".")
    stop_krav = "direkte" if krav["max_stop"] == 0 else f"max {krav['max_stop']} stop"
    print("\n" + "=" * 78)
    print(f"{titel}  ({krav['tidligste_dato']} til {krav['seneste_dato']}, "
          f"{stop_krav}, max {loft} {valuta})")
    print("=" * 78)
    for r in traef[:10]:
        print("  " + linje(r, valuta))
    if not traef:
        print("  Ingen afgange opfylder alle kravene på én gang.")
    if naer:
        print("\n  Tættest på:")
        for r in naer:
            print("  " + linje(r, valuta) + f"   <- {r['aarsag']}")


async def hent_koebslinks(k: dict, raekker: list[dict]) -> None:
    """Klikker hver afgang frem paa Google Flights og gemmer selve bookingsiden
    - den side hvor billetten faktisk kobes, med saelger og pris."""
    from playwright.async_api import async_playwright

    if not raekker:
        return
    print(f"\nHenter kobslinks for {len(raekker)} afgange ...")
    sem = asyncio.Semaphore(max(1, k.get("parallelle_soegninger", 3)))

    async def en(r: dict) -> None:
        async with sem:
            info = await g.booking_info(ctx, r["google"], r["price"],
                                        r.get("depart", ""), k["valuta"])
        if not info:
            return
        r["koeb_url"] = info["url"]
        r["saelgere"] = info["saelgere"]
        r["kabine_detalje"] = info["kabine_detalje"]
        r["bagage"] = info["bagage"]
        saelger = info["saelgere"][0]["navn"] if info["saelgere"] else "ukendt saelger"
        pris = f"{r['price']:,}".replace(",", ".")
        print(f"  {pris} {k['valuta']} {r['dato']} {r['fra']}-{r['til']} "
              f"-> kobes hos {saelger}"
              + (f" ({info['kabine_detalje']})" if info["kabine_detalje"] else ""))

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(locale="en-US", user_agent=UA,
                                        viewport={"width": 1400, "height": 1000})
        try:
            await asyncio.gather(*[en(r) for r in raekker])
        finally:
            await browser.close()


def udskriv(k: dict, ud: list[dict], hjem: list[dict], naer_ud: list[dict],
            naer_hjem: list[dict]) -> list[dict]:
    valuta = k["valuta"]

    afsnit(f"UDREJSE  {k['udrejse']['fra']} -> {'/'.join(k['udrejse']['til'])}",
           k["udrejse"], valuta, ud, naer_ud if not ud else naer_ud[:3])
    afsnit(f"HJEMREJSE  {'/'.join(k['hjemrejse']['fra'])} -> {k['hjemrejse']['til']}",
           k["hjemrejse"], valuta, hjem, naer_hjem if not hjem else naer_hjem[:3])

    par = kombiner(ud, hjem, k)
    if par:
        b = par[0]
        i_alt = f"{b['i_alt']:,}".replace(",", ".")
        pr_p = f"{b['pr_person']:,}".replace(",", ".")
        budget = f"{k['samlet_budget']:,}".replace(",", ".")
        indenfor = "inden for" if b["i_alt"] <= k["samlet_budget"] else "OVER"
        print("\n" + "=" * 78)
        print(f"BEDSTE SAMLEDE REJSE for {k['personer']} personer")
        print("=" * 78)
        print("  Ud   " + linje(b["ud"], valuta))
        print("  Hjem " + linje(b["hjem"], valuta))
        print(f"\n  {pr_p} {valuta} pr. person  =  {i_alt} {valuta} for {k['personer']} "
              f"({indenfor} budgettet paa {budget} {valuta})")
        for navn, r in (("udrejsen  ", b["ud"]), ("hjemrejsen", b["hjem"])):
            print(f"\n  Køb {navn}: {r.get('koeb_url') or r['google']}")
            if r.get("saelgere"):
                s = ", ".join(f"{x['navn']} {x['pris']:,}".replace(",", ".")
                              for x in r["saelgere"] if x["pris"])
                print(f"      sælges af: {s}")
            if r.get("kabine_detalje"):
                print(f"      kabine pr. ben: {r['kabine_detalje']}")
    return par


# --------------------------------------------------------------------------

def historik(mappe: Path, k: dict, par: list[dict], ud: list[dict],
             hjem: list[dict]) -> int | None:
    """Gemmer dagens billigste og fortaeller, hvad der er sket siden sidst.
    Returnerer prisfaldet pr. person, hvis der er et."""
    sti = mappe / "historik.json"
    tidligere = []
    if sti.exists():
        try:
            tidligere = json.loads(sti.read_text(encoding="utf-8"))
        except Exception:
            tidligere = []

    nu = {
        "tidspunkt": time.strftime("%Y-%m-%d %H:%M"),
        "billigste_ud": ud[0]["price"] if ud else None,
        "billigste_hjem": hjem[0]["price"] if hjem else None,
        "billigste_samlet_pr_person": par[0]["pr_person"] if par else None,
    }
    tidligere.append(nu)
    sti.write_text(json.dumps(tidligere[-200:], indent=2, ensure_ascii=False),
                   encoding="utf-8")

    foer = next((h["billigste_samlet_pr_person"] for h in reversed(tidligere[:-1])
                 if h.get("billigste_samlet_pr_person")), None)
    if foer and nu["billigste_samlet_pr_person"]:
        diff = nu["billigste_samlet_pr_person"] - foer
        if diff < 0:
            print(f"\n*** PRISFALD: {abs(diff):,} {k['valuta']} pr. person "
                  f"billigere end sidste søgning ***".replace(",", "."))
            return abs(diff)
        if diff > 0:
            print(f"\nSteget {diff:,} {k['valuta']} pr. person siden sidste søgning."
                  .replace(",", "."))
    return None


def main(argv=None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    stille = "--stille" in argv                  # bruges af den daglige automatik

    k = json.loads((HER / "kriterier.json").read_text(encoding="utf-8"))
    db = flyselskaber.load(HER / "flyselskaber.json")
    opgaver = byg_opgaver(k)
    if not opgaver:
        sys.exit("Ingen datoer at søge på – tjek datoerne i kriterier.json.")

    print(f"[{time.strftime('%d-%m-%Y %H:%M')}] Søger {len(opgaver)} kombinationer "
          f"af dato, rute og kabine.")
    print(f"Kun selskaber med mindst {k['min_stjerner']} stjerner tæller med.")
    print(f"Det tager ca. {len(opgaver) * 9 // max(1, k['parallelle_soegninger']) // 60 + 1} minutter.\n")

    start = time.time()
    raekker = asyncio.run(soeg(k, opgaver, db))
    print(f"\nFærdig på {time.time() - start:.0f} sekunder – {len(raekker)} tilbud gennemgået.")

    ud, hjem = bedste(raekker, "ud"), bedste(raekker, "hjem")
    naer_ud, naer_hjem = naermest(raekker, "ud"), naermest(raekker, "hjem")

    antal = k.get("hent_koebslinks", 6)
    if antal:
        # To runder: foerst de bedste efter kortprisen, saa - hvis en pris blev
        # rettet - de kandidater der derved rykkede op. Uden anden runde ville
        # den nye topafgang staa med en uverificeret pris.
        for runde in (1, 2):
            grupper = ((ud[:antal], hjem[:antal], naer_ud[:3], naer_hjem[:3]) if runde == 1
                       else (ud[:antal], hjem[:antal]))
            vaelg, set_id = [], set()
            for gruppe in grupper:
                for r in gruppe:
                    if id(r) not in set_id and not r.get("pris_verificeret"):
                        set_id.add(id(r))
                        vaelg.append(r)
            if not vaelg:
                break
            asyncio.run(hent_koebslinks(k, vaelg))

            rettet = verificer(raekker, k)
            if not rettet:
                break
            print(f"\n{len(rettet)} pris(er) holdt ikke paa bookingsiden:")
            for r in sorted(rettet, key=lambda x: -(x["price"] / x["pris_kort"])):
                kort = f"{r['pris_kort']:,}".replace(",", ".")
                rigtig = f"{r['price']:,}".replace(",", ".")
                ude = "  - opfylder ikke laengere kravene" if r.get("pris_afvist") else ""
                print(f"  {r['dato']} {r['fra']}-{r['til']}: {kort} -> {rigtig} "
                      f"{k['valuta']} ({r['price'] / r['pris_kort']:.2f}x){ude}")
            ud, hjem = bedste(raekker, "ud"), bedste(raekker, "hjem")
            naer_ud, naer_hjem = naermest(raekker, "ud"), naermest(raekker, "hjem")

    par = udskriv(k, ud, hjem, naer_ud, naer_hjem)

    mappe = HER / "resultater"
    mappe.mkdir(exist_ok=True)
    rapport = mappe / "rejseplan.html"
    rejserapport.skriv(rapport, k, ud, hjem, par, raekker, naer_ud, naer_hjem)
    (mappe / "rejseplan.json").write_text(
        json.dumps({"kriterier": k, "alle_tilbud": raekker}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    print(f"\nRapport: {rapport}")

    faldet = historik(mappe, k, par, ud, hjem)
    resume.skriv(mappe, k, ud, hjem, par, naer_ud, naer_hjem, faldet)

    # Naar agenten koerer i skyen (GitHub Actions) er der ingen browser at aabne i.
    if sys.platform == "win32" and (not stille or faldet):
        try:
            os.startfile(rapport)
        except Exception:
            pass


if __name__ == "__main__":
    main()
