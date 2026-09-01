"""Skriver resultater til JSON, CSV og en selvstaendig HTML-rapport."""
from __future__ import annotations

import csv
import html
import json
from datetime import datetime
from pathlib import Path

CSV_COLUMNS = ["price", "currency", "out_date", "home_date", "nights", "airline",
               "stops", "duration_min", "route", "layover", "co2_kg",
               "depart", "arrive", "google"]


def write_json(rows: list[dict], path: Path, meta: dict) -> None:
    path.write_text(json.dumps({"meta": meta, "results": rows}, indent=2,
                               ensure_ascii=False), encoding="utf-8")


def write_csv(rows: list[dict], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def dk(n) -> str:
    """1234567 -> 1.234.567 (dansk tusindtalsseparator)."""
    return f"{n:,}".replace(",", ".")


def _fmt_duration(minutes) -> str:
    if not minutes:
        return "-"
    return f"{minutes // 60}t {minutes % 60:02d}m"


def _stops_label(stops) -> str:
    if stops is None:
        return "-"
    return "Direkte" if stops == 0 else f"{stops} stop"


def write_html(rows: list[dict], path: Path, meta: dict) -> None:
    if not rows:
        path.write_text("<p>Ingen resultater.</p>", encoding="utf-8")
        return

    prices = [r["price"] for r in rows]
    lo, hi = min(prices), max(prices)
    cur = rows[0]["currency"]

    def heat(p: int) -> str:
        t = 0 if hi == lo else (p - lo) / (hi - lo)
        return f"hsl({int(140 - 140 * t)} 62% 42%)"

    body = []
    for i, r in enumerate(rows, 1):
        sites = "".join(
            f'<a href="{html.escape(u)}" target="_blank" rel="noopener">{html.escape(n)}</a>'
            for n, u in r.get("links", {}).items())
        body.append(f"""<tr>
  <td class="num">{i}</td>
  <td class="price" style="color:{heat(r['price'])}">{dk(r['price'])}</td>
  <td>{html.escape(r['out_date'])}<span class="sub"> &rarr; {html.escape(r.get('home_date') or '')}</span></td>
  <td class="num">{r.get('nights') or '-'}</td>
  <td>{html.escape(r.get('airline') or '-')}</td>
  <td>{_stops_label(r.get('stops'))}<span class="sub">{html.escape(' ' + (r.get('layover') or ''))}</span></td>
  <td>{_fmt_duration(r.get('duration_min'))}</td>
  <td>{html.escape(r.get('route') or '-')}</td>
  <td class="links"><a class="primary" href="{html.escape(r['google'])}" target="_blank" rel="noopener">Google Flights</a>{sites}</td>
</tr>""")

    generated = datetime.now().strftime("%d-%m-%Y %H:%M")
    doc = f"""<!doctype html><html lang="da"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bred prisjagt {html.escape(meta['origin'])} &rarr; {html.escape(meta['destination'])}</title>
<style>
 :root {{ color-scheme: light dark; --bg:#fbfbfa; --fg:#1a1a19; --mut:#6b6b68;
          --line:#e6e4e0; --card:#fff; --accent:#3b5bdb; }}
 @media (prefers-color-scheme: dark) {{
   :root {{ --bg:#151513; --fg:#eceae5; --mut:#9a978f; --line:#2c2b28; --card:#1d1d1a; --accent:#8fa5ff; }} }}
 * {{ box-sizing:border-box; }}
 body {{ margin:0; padding:32px 20px 64px; background:var(--bg); color:var(--fg);
         font:15px/1.5 ui-sans-serif,-apple-system,Segoe UI,Roboto,sans-serif; }}
 .wrap {{ max-width:1180px; margin:0 auto; }}
 h1 {{ font-size:26px; margin:0 0 4px; letter-spacing:-.02em; }}
 .meta {{ color:var(--mut); font-size:13px; margin-bottom:24px; }}
 .stats {{ display:flex; gap:12px; flex-wrap:wrap; margin-bottom:24px; }}
 .stat {{ background:var(--card); border:1px solid var(--line); border-radius:10px;
          padding:12px 16px; min-width:150px; }}
 .stat b {{ display:block; font-size:22px; letter-spacing:-.02em; }}
 .stat span {{ color:var(--mut); font-size:12px; text-transform:uppercase; letter-spacing:.06em; }}
 .scroll {{ overflow-x:auto; border:1px solid var(--line); border-radius:12px; background:var(--card); }}
 table {{ border-collapse:collapse; width:100%; font-size:14px; }}
 th {{ text-align:left; font-size:11px; text-transform:uppercase; letter-spacing:.07em;
       color:var(--mut); padding:12px 14px; border-bottom:1px solid var(--line); white-space:nowrap; }}
 td {{ padding:11px 14px; border-bottom:1px solid var(--line); vertical-align:top; white-space:nowrap; }}
 tr:last-child td {{ border-bottom:0; }}
 .num {{ text-align:right; color:var(--mut); }}
 .price {{ font-weight:650; font-variant-numeric:tabular-nums; }}
 .sub {{ color:var(--mut); font-size:12px; }}
 .links a {{ display:inline-block; margin-right:8px; color:var(--accent); text-decoration:none;
             font-size:12px; border-bottom:1px solid transparent; }}
 .links a:hover {{ border-bottom-color:currentColor; }}
 .links a.primary {{ font-weight:600; }}
 footer {{ color:var(--mut); font-size:12px; margin-top:20px; }}
 .banner {{ background:#fff4e0; border:1px solid #e8c88a; color:#6b4a10;
   border-radius:10px; padding:11px 14px; font-size:13px; margin-bottom:20px; }}
 @media (prefers-color-scheme:dark) {{
   .banner {{ background:#2a2214; border-color:#5a4620; color:#e8c88a; }} }}
 .banner code {{ background:transparent; font-size:12.5px; }}
</style></head><body><div class="wrap">
<div class="banner">
  <b>Bred prisjagt</b> &mdash; billigste returfly uanset selskab og klasse.
  <b>Dine kriterier er ikke brugt her.</b>
  Rapporten der f&oslash;lger kriterierne hedder <code>rejseplan.html</code>
  og laves ved at dobbeltklikke p&aring; <code>SOEG-FLY.bat</code>.
</div>
<h1>{html.escape(meta['origin'])} &rarr; {html.escape(meta['destination'])}</h1>
<div class="meta">{html.escape(meta['window'])} &middot; {meta['queries']} sogninger &middot; hentet {generated}</div>
<div class="stats">
  <div class="stat"><span>Billigst</span><b>{dk(lo)} {cur}</b></div>
  <div class="stat"><span>Median</span><b>{dk(sorted(prices)[len(prices)//2])} {cur}</b></div>
  <div class="stat"><span>Fundne tilbud</span><b>{len(rows)}</b></div>
</div>
<div class="scroll"><table>
<thead><tr><th>#</th><th>Pris</th><th>Ud &rarr; hjem</th><th>Naetter</th><th>Selskab</th>
<th>Stop</th><th>Varighed</th><th>Rute</th><th>Book</th></tr></thead>
<tbody>{''.join(body)}</tbody></table></div>
<footer>Priser er Google Flights' totalpris pr. person. Klik et link for at booke - priserne kan naa at aendre sig.</footer>
</div></body></html>"""
    path.write_text(doc, encoding="utf-8")
