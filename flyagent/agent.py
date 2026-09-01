"""Flight-agent: scanner en hel datoperiode paa Google Flights og finder de
billigste fly - fx Kobenhavn -> Tokyo - og giver dig links til at booke.

    python agent.py --from CPH --to TYO --start 2026-10-01 --end 2026-12-15 \
                    --nights 10-16 --step 3 --max-stops 1
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import gflights as g
import links as booking
import report

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


# --------------------------------------------------------------------------
# Argumenter
# --------------------------------------------------------------------------

def parse_nights(spec: str) -> list[int]:
    """'10-16' -> [10..16],  '7,14,21' -> [7,14,21],  '12' -> [12]"""
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = (int(x) for x in part.split("-", 1))
            out.extend(range(lo, hi + 1))
        else:
            out.append(int(part))
    return sorted(set(out))


def build_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Find billige fly og links til at booke dem.")
    p.add_argument("--from", dest="origin", default="CPH", help="afrejse (IATA), fx CPH")
    p.add_argument("--to", dest="destination", default="TYO",
                   help="destination (IATA), fx TYO = hele Tokyo, HND, NRT")
    p.add_argument("--start", required=True, help="tidligste afrejsedato YYYY-MM-DD")
    p.add_argument("--end", required=True, help="seneste afrejsedato YYYY-MM-DD")
    p.add_argument("--nights", default="10-14", help="antal naetter, fx '10-16' eller '7,14'")
    p.add_argument("--step", type=int, default=3, help="dage mellem hver afrejsedato (default 3)")
    p.add_argument("--one-way", action="store_true", help="kun udrejse")
    p.add_argument("--adults", type=int, default=1)
    p.add_argument("--seat", default="economy",
                   choices=["economy", "premium", "business", "first"])
    p.add_argument("--max-stops", type=int, default=None, help="fx 0 = kun direkte, 1 = max 1 stop")
    p.add_argument("--max-price", type=int, default=None, help="ignorer alt over denne pris")
    p.add_argument("--currency", default="DKK")
    p.add_argument("--per-search", type=int, default=4, help="tilbud der gemmes pr. sogning")
    p.add_argument("--top", type=int, default=25, help="raekker i terminal-tabellen")
    p.add_argument("--concurrency", type=int, default=3, help="parallelle faneblade")
    p.add_argument("--out", default="resultater", help="mappe til rapporterne")
    p.add_argument("--headful", action="store_true", help="vis browseren (til fejlsogning)")
    p.add_argument("--watch", type=int, default=0,
                   help="gentag scanningen hvert N. minut og meld prisfald")
    return p.parse_args(argv)


def build_queries(a: argparse.Namespace) -> list[dict]:
    start, end = date.fromisoformat(a.start), date.fromisoformat(a.end)
    if end < start:
        sys.exit("--end ligger for --start")
    today = date.today()
    nights = [0] if a.one_way else parse_nights(a.nights)

    queries, day = [], start
    while day <= end:
        if day >= today:
            for n in nights:
                home = None if a.one_way else day + timedelta(days=n)
                queries.append({
                    "out_date": day.isoformat(),
                    "home_date": home.isoformat() if home else None,
                    "nights": None if a.one_way else n,
                })
        day += timedelta(days=max(1, a.step))
    return queries


# --------------------------------------------------------------------------
# Selve scanningen
# --------------------------------------------------------------------------

async def run_query(context, q: dict, a: argparse.Namespace, sem: asyncio.Semaphore,
                    idx: int, total: int) -> list[dict]:
    legs = [(q["out_date"], a.origin, a.destination)]
    if q["home_date"]:
        legs.append((q["home_date"], a.destination, a.origin))
    url = g.search_url(legs, adults=a.adults, seat=a.seat, currency=a.currency)

    async with sem:
        offers = []
        for attempt in (1, 2):
            try:
                offers = await g.fetch_offers(context, url, a.currency, limit=a.per_search)
                break
            except Exception as exc:                       # netvaerk/timeout - prov igen
                if attempt == 2:
                    print(f"  [{idx}/{total}] {q['out_date']}: fejlede ({type(exc).__name__})")
                    return []
                await asyncio.sleep(3)

    rows = []
    for o in offers:
        if a.max_stops is not None and o.stops is not None and o.stops > a.max_stops:
            continue
        if a.max_price is not None and o.price > a.max_price:
            continue
        row = o.as_dict() | {
            "out_date": q["out_date"], "home_date": q["home_date"], "nights": q["nights"],
            "google": url,
            "links": booking.booking_links(a.origin, a.destination, q["out_date"],
                                           q["home_date"], a.adults, a.currency),
        }
        rows.append(row)

    if rows:
        best = rows[0]
        label = f"{best['price']:,}".replace(",", ".")
        extra = best["airline"] or "?"
        print(f"  [{idx}/{total}] {q['out_date']} -> {q['home_date'] or 'one-way'}"
              f"   billigst {label} {a.currency}  ({extra})")
    else:
        print(f"  [{idx}/{total}] {q['out_date']}: ingen traef")
    return rows


async def scan(a: argparse.Namespace, queries: list[dict]) -> list[dict]:
    from playwright.async_api import async_playwright

    sem = asyncio.Semaphore(max(1, a.concurrency))
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not a.headful)
        context = await browser.new_context(locale="en-US", user_agent=UA,
                                            viewport={"width": 1400, "height": 1000})
        try:
            tasks = [run_query(context, q, a, sem, i, len(queries))
                     for i, q in enumerate(queries, 1)]
            batches = await asyncio.gather(*tasks)
        finally:
            await browser.close()

    rows = [r for batch in batches for r in batch]
    rows.sort(key=lambda r: (r["price"], r["duration_min"] or 9999))
    return rows


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

def print_table(rows: list[dict], a: argparse.Namespace) -> None:
    if not rows:
        print("\nIngen resultater. Prov en bredere periode eller floj max-stops/max-price.")
        return
    print(f"\n{'PRIS':>10}  {'UD':<10} {'HJEM':<10} {'N':>3}  {'SELSKAB':<22} "
          f"{'STOP':<8} {'TID':<8} RUTE")
    print("-" * 96)
    for r in rows[:a.top]:
        dur = f"{r['duration_min'] // 60}t{r['duration_min'] % 60:02d}" if r["duration_min"] else "-"
        stops = "-" if r["stops"] is None else ("direkte" if r["stops"] == 0 else f"{r['stops']} stop")
        price = f"{r['price']:,}".replace(",", ".")
        print(f"{price:>10}  {r['out_date']:<10} {(r['home_date'] or '-'):<10} "
              f"{str(r['nights'] or '-'):>3}  {(r['airline'] or '?')[:22]:<22} "
              f"{stops:<8} {dur:<8} {r['route'] or '-'}")

    best = rows[0]
    print("\nBilligst fundet:")
    print(f"  {best['price']:,}".replace(",", ".") + f" {best['currency']}  "
          f"{best['out_date']} -> {best['home_date'] or 'one-way'}  ({best['airline'] or '?'})")
    print(f"  Google Flights : {best['google']}")
    for name, url in best["links"].items():
        print(f"  {name:<15}: {url}")


def save(rows: list[dict], a: argparse.Namespace, queries: list[dict]) -> Path:
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    meta = {
        "origin": a.origin.upper(), "destination": a.destination.upper(),
        "window": f"{a.start} til {a.end}, {'one-way' if a.one_way else a.nights + ' naetter'}",
        "queries": len(queries), "currency": a.currency,
        "scanned_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    stem = f"bredsoegning-{a.origin.upper()}-{a.destination.upper()}"
    report.write_json(rows, out / f"{stem}.json", meta)
    report.write_csv(rows, out / f"{stem}.csv")
    html_path = out / f"{stem}.html"
    report.write_html(rows, html_path, meta)
    print(f"\nGemt: {out / (stem + '.json')}\n      {out / (stem + '.csv')}"
          f"\n      {html_path}   <- aabn denne i browseren")
    return html_path


def previous_best(a: argparse.Namespace) -> int | None:
    path = Path(a.out) / f"bredsoegning-{a.origin.upper()}-{a.destination.upper()}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return min(r["price"] for r in data["results"]) if data.get("results") else None
    except Exception:
        return None


# --------------------------------------------------------------------------

async def one_pass(a: argparse.Namespace) -> list[dict]:
    queries = build_queries(a)
    if not queries:
        sys.exit("Ingen datoer at soge paa - tjek --start/--end.")
    print(f"Soger {a.origin.upper()} -> {a.destination.upper()}: {len(queries)} "
          f"kombinationer ({a.start} .. {a.end}), ca. "
          f"{len(queries) * 9 // max(1, a.concurrency) // 60 + 1} min.\n")

    before = previous_best(a)
    started = time.time()
    rows = await scan(a, queries)
    print(f"\nFaerdig paa {time.time() - started:.0f}s - {len(rows)} tilbud.")

    print_table(rows, a)
    save(rows, a, queries)

    if rows and before:
        diff = rows[0]["price"] - before
        if diff < 0:
            print(f"\n*** PRISFALD: {abs(diff):,}".replace(",", ".")
                  + f" {a.currency} billigere end sidste scanning ***")
        elif diff > 0:
            print(f"\nSteget {diff:,} {a.currency} siden sidste scanning.".replace(",", "."))
    return rows


def main() -> None:
    a = build_args()
    if a.watch:
        while True:
            asyncio.run(one_pass(a))
            print(f"\nVenter {a.watch} min ... (Ctrl+C for at stoppe)\n")
            time.sleep(a.watch * 60)
    else:
        asyncio.run(one_pass(a))


if __name__ == "__main__":
    main()
