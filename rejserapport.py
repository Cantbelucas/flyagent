"""HTML-rapporten: hvad opfylder kriterierne, hvad koster det, og hvor køber man."""
from __future__ import annotations

import html
from datetime import date, datetime
from pathlib import Path

UGEDAG = ["man", "tir", "ons", "tor", "fre", "lør", "søn"]
MAANED = ["jan", "feb", "mar", "apr", "maj", "jun",
          "jul", "aug", "sep", "okt", "nov", "dec"]
KABINE = {"economy": "Economy", "premium": "Premium economy",
          "business": "Business", "first": "First class"}


def kr(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def dato(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{UGEDAG[d.weekday()]}. {d.day}. {MAANED[d.month - 1]}"


def tid(minutter) -> str:
    if not minutter:
        return "-"
    return f"{minutter // 60}t {minutter % 60:02d}m"


def stop(r: dict) -> str:
    if r.get("stops") is None:
        return "-"
    if r["stops"] == 0:
        return "Direkte"
    lay = f" via {r['layover']}" if r.get("layover") else ""
    return f"{r['stops']} stop{lay}"


def stjerner(n) -> str:
    if not n:
        return '<span class="dim">?</span>'
    return f'<span class="star">{"&#9733;" * int(n)}</span>'


def kabine_note(r: dict) -> str:
    """Google saelger tit "premium economy" hvor kun det ene ben er premium."""
    detalje = r.get("kabine_detalje") or ""
    if not detalje or detalje.lower() == (r.get("kabine_navn") or "").lower():
        return ""
    return f'<br><span class="dim">{html.escape(detalje)}</span>'


def knapper(r: dict, valuta: str = "DKK") -> str:
    """Forst det rigtige kobslink (Googles bookingside for netop denne afgang),
    derefter selskabets egen side og sammenligningssiderne."""
    ud = []
    saelgere = r.get("saelgere") or []
    if r.get("koeb_url"):
        tekst = (f'Køb hos {saelgere[0]["navn"]}' if saelgere else 'Åbn bookingsiden')
        ud.append(f'<a class="btn primary" href="{html.escape(r["koeb_url"])}" '
                  f'target="_blank" rel="noopener">{html.escape(tekst)}</a>')
    else:
        ud.append(f'<a class="btn primary" href="{html.escape(r["google"])}" '
                  f'target="_blank" rel="noopener">Find på Google Flights</a>')

    if r.get("booking"):
        navn = (r.get("selskaber") or ["selskabet"])[0]
        ud.append(f'<a class="btn" href="{html.escape(r["booking"])}" target="_blank" '
                  f'rel="noopener">{html.escape(navn)}.com</a>')
    for navn, url in list(r.get("links", {}).items())[:2]:
        ud.append(f'<a class="btn" href="{html.escape(url)}" target="_blank" '
                  f'rel="noopener">{html.escape(navn)}</a>')

    if len(saelgere) > 1:
        andre = " &middot; ".join(
            f"{html.escape(s['navn'])} {kr(s['pris'])}" for s in saelgere[1:] if s["pris"])
        if andre:
            ud.append(f'<div class="saelgere">Også hos {andre} {valuta}</div>')
    return "".join(ud)


def raekke(r: dict, valuta: str) -> str:
    return f"""<tr>
<td class="pris">{kr(r['price'])}<span class="dim"> {valuta}</span></td>
<td>{dato(r['dato'])}<span class="dim"> {r['fra']}&#8594;{r['til']}</span></td>
<td>{html.escape(r.get('airline') or '?')}<br>{stjerner(r.get('stjerner'))}</td>
<td>{html.escape(r.get('kabine_navn', ''))}{kabine_note(r)}</td>
<td>{stop(r)}</td>
<td>{tid(r.get('duration_min'))}<span class="dim"> {html.escape(r.get('depart') or '')}</span></td>
<td class="knapper">{knapper(r, valuta)}</td>
</tr>"""


def tabel(raekker: list[dict], valuta: str, tom: str) -> str:
    if not raekker:
        return f'<p class="tom">{html.escape(tom)}</p>'
    body = "".join(raekke(r, valuta) for r in raekker)
    return f"""<div class="scroll"><table>
<thead><tr><th>Pris pr. person</th><th>Dato</th><th>Selskab</th><th>Klasse</th>
<th>Stop</th><th>Rejsetid</th><th>Book</th></tr></thead>
<tbody>{body}</tbody></table></div>"""


def naer_tabel(raekker: list[dict], valuta: str) -> str:
    """De afgange der kun mangler lidt – med det, der skiller, skrevet ud."""
    if not raekker:
        return ""
    body = "".join(f"""<tr>
<td class="pris">{kr(r['price'])}<span class="dim"> {valuta}</span></td>
<td>{dato(r['dato'])}<span class="dim"> {r['fra']}&#8594;{r['til']}</span></td>
<td>{html.escape(r.get('airline') or '?')}<br>{stjerner(r.get('stjerner'))}</td>
<td>{html.escape(r.get('kabine_navn',''))}{kabine_note(r)}</td>
<td>{stop(r)}</td>
<td>{tid(r.get('duration_min'))}</td>
<td class="mangler-celle">{"".join(f'<span class="mangel">{html.escape(f)}</span>' for f in r['fejl'])}</td>
<td class="knapper">{knapper(r, valuta)}</td>
</tr>""" for r in raekker)
    return f"""<h3>Tættest på</h3>
<p class="dim">Opfylder alt undtagen det, der står i kolonnen &raquo;mangler&laquo;.
Selskaber under stjernekravet er ikke med her.</p>
<div class="scroll"><table>
<thead><tr><th>Pris pr. person</th><th>Dato</th><th>Selskab</th><th>Klasse</th>
<th>Stop</th><th>Rejsetid</th><th>Mangler</th><th>Book</th></tr></thead>
<tbody>{body}</tbody></table></div>"""


def hero(par: list[dict], k: dict) -> str:
    if not par:
        return ('<div class="hero mangler"><h2>Ingen komplet rejse fundet</h2>'
                '<p>Ingen kombination opfylder alle kriterierne. Kig i tabellerne '
                'nedenfor og i afsnittet om fravalgte afgange – som regel er det '
                'prisloftet eller kravet om direkte fly, der står i vejen.</p></div>')
    b = par[0]
    v = k["valuta"]
    inden_for = b["i_alt"] <= k["samlet_budget"]
    return f"""<div class="hero">
  <div class="hero-top">
    <div><span class="label">Bedste samlede rejse</span>
      <h2>{kr(b['pr_person'])} {v} <span class="dim">pr. person</span></h2>
      <p class="{'ok' if inden_for else 'over'}">{kr(b['i_alt'])} {v} for {k['personer']} personer
      &middot; {'inden for' if inden_for else 'over'} budgettet på {kr(k['samlet_budget'])} {v}</p>
    </div>
  </div>
  <div class="ben">
    {ben_kort('Udrejse', b['ud'], v)}
    {ben_kort('Hjemrejse', b['hjem'], v)}
  </div>
</div>"""


def ben_kort(titel: str, r: dict, valuta: str) -> str:
    return f"""<div class="kort">
  <span class="label">{titel}</span>
  <div class="rute">{r['fra']} &#8594; {r['til']}</div>
  <div class="detalje">{dato(r['dato'])} &middot; {html.escape(r.get('airline') or '?')}
    {stjerner(r.get('stjerner'))}</div>
  <div class="detalje">{html.escape(r.get('kabine_detalje') or r.get('kabine_navn',''))} &middot; {stop(r)} &middot; {tid(r.get('duration_min'))}</div>
  <div class="detalje dim">{html.escape(r.get('bagage') or '')}</div>
  <div class="kort-pris">{kr(r['price'])} {valuta}</div>
  <div class="knapper">{knapper(r, valuta)}</div>
</div>"""


def fravalgte(alle: list[dict]) -> str:
    afvist: dict[str, int] = {}
    ukendte: dict[str, int] = {}
    for r in alle:
        if r["status"] == "afvist" and r.get("aarsag"):
            afvist[r["aarsag"]] = afvist.get(r["aarsag"], 0) + 1
        elif r["status"] == "ukendt":
            navn = r.get("airline") or "(uden selskab)"
            ukendte[navn] = ukendte.get(navn, 0) + 1

    dele = []
    if afvist:
        rows = "".join(f"<li>{html.escape(a)} <span class='dim'>&times;{n}</span></li>"
                       for a, n in sorted(afvist.items(), key=lambda kv: -kv[1])[:12])
        dele.append(f"<h3>Fravalgt fordi</h3><ul class='liste'>{rows}</ul>")
    if ukendte:
        rows = "".join(f"<li>{html.escape(a)} <span class='dim'>&times;{n}</span></li>"
                       for a, n in sorted(ukendte.items(), key=lambda kv: -kv[1])[:12])
        dele.append("<h3>Selskaber jeg ikke kender</h3>"
                    "<p class='dim'>De er ikke med i listerne ovenfor. Slå dem op, "
                    "og skriv dem ind i <code>flyselskaber.json</code>, hvis de skal tælle med.</p>"
                    f"<ul class='liste'>{rows}</ul>")
    return "".join(dele)


def skriv(sti: Path, k: dict, ud: list[dict], hjem: list[dict], par: list[dict],
          alle: list[dict], naer_ud: list[dict] = (), naer_hjem: list[dict] = ()) -> None:
    v = k["valuta"]
    u_krav, h_krav = k["udrejse"], k["hjemrejse"]

    kombi = ""
    if len(par) > 1:
        rows = "".join(f"""<tr>
<td class="pris">{kr(p['pr_person'])}<span class="dim"> {v}</span></td>
<td class="pris">{kr(p['i_alt'])}<span class="dim"> for {k['personer']}</span></td>
<td>{dato(p['ud']['dato'])} {html.escape(p['ud'].get('airline') or '')}
  <span class="dim">{html.escape(p['ud'].get('kabine_navn',''))}</span></td>
<td>{dato(p['hjem']['dato'])} {html.escape(p['hjem'].get('airline') or '')}
  <span class="dim">{p['hjem']['fra']} &middot; {html.escape(p['hjem'].get('kabine_navn',''))}</span></td>
</tr>""" for p in par[:15])
        kombi = f"""<h2>Andre kombinationer</h2><div class="scroll"><table>
<thead><tr><th>Pr. person</th><th>I alt</th><th>Udrejse</th><th>Hjemrejse</th></tr></thead>
<tbody>{rows}</tbody></table></div>"""

    doc = f"""<!doctype html><html lang="da"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rejseplan {html.escape(u_krav['fra'])} &#8594; {html.escape('/'.join(u_krav['til']))}</title>
<style>
 :root {{ color-scheme:light dark; --bg:#fbfbfa; --fg:#1a1a19; --dim:#75736e; --line:#e5e3de;
   --card:#fff; --accent:#2f5bd8; --ok:#0d8a4a; --over:#c0392b; --star:#e0a30b; }}
 @media (prefers-color-scheme:dark) {{ :root {{ --bg:#141412; --fg:#ecebe6; --dim:#97948c;
   --line:#2c2b27; --card:#1c1c19; --accent:#8ea8ff; --ok:#4ec27f; --over:#f0705f; --star:#f0bc3c; }} }}
 * {{ box-sizing:border-box; }}
 body {{ margin:0; padding:36px 20px 72px; background:var(--bg); color:var(--fg);
   font:15px/1.55 ui-sans-serif,-apple-system,"Segoe UI",Roboto,sans-serif; }}
 .wrap {{ max-width:1120px; margin:0 auto; }}
 h1 {{ font-size:27px; margin:0 0 4px; letter-spacing:-.02em; }}
 h2 {{ font-size:19px; margin:38px 0 12px; letter-spacing:-.01em; }}
 h3 {{ font-size:14px; margin:20px 0 8px; }}
 .undertekst {{ color:var(--dim); font-size:13px; margin-bottom:26px; }}
 .dim {{ color:var(--dim); font-weight:400; }}
 .star {{ color:var(--star); letter-spacing:1px; font-size:12px; }}
 .hero {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:22px; }}
 .hero.mangler h2 {{ margin-top:0; }}
 .label {{ font-size:11px; text-transform:uppercase; letter-spacing:.09em; color:var(--dim); }}
 .hero h2 {{ margin:2px 0 4px; font-size:30px; }}
 .hero .ok {{ color:var(--ok); margin:0; font-size:14px; }}
 .hero .over {{ color:var(--over); margin:0; font-size:14px; }}
 .ben {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:14px; margin-top:20px; }}
 .kort {{ border:1px solid var(--line); border-radius:11px; padding:15px; }}
 .rute {{ font-size:20px; font-weight:600; letter-spacing:-.01em; margin:2px 0 6px; }}
 .detalje {{ font-size:13px; color:var(--fg); }}
 .kort-pris {{ font-size:17px; font-weight:650; margin:10px 0 12px; }}
 .btn {{ display:inline-block; margin:0 6px 6px 0; padding:6px 11px; border-radius:8px;
   border:1px solid var(--line); color:var(--accent); text-decoration:none; font-size:12.5px; }}
 .btn:hover {{ border-color:var(--accent); }}
 .btn.primary {{ background:var(--accent); color:#fff; border-color:var(--accent); font-weight:600; }}
 .scroll {{ overflow-x:auto; border:1px solid var(--line); border-radius:12px; background:var(--card); }}
 table {{ border-collapse:collapse; width:100%; font-size:13.5px; }}
 th {{ text-align:left; font-size:11px; text-transform:uppercase; letter-spacing:.07em;
   color:var(--dim); padding:12px 14px; border-bottom:1px solid var(--line); white-space:nowrap; }}
 td {{ padding:12px 14px; border-bottom:1px solid var(--line); vertical-align:top; }}
 tr:last-child td {{ border-bottom:0; }}
 .pris {{ font-weight:650; font-variant-numeric:tabular-nums; white-space:nowrap; }}
 .knapper {{ min-width:250px; }}
 .saelgere {{ font-size:11.5px; color:var(--dim); margin-top:4px; }}
 .mangler-celle {{ max-width:230px; }}
 .mangel {{ display:inline-block; background:var(--bg); border:1px solid var(--line);
   border-radius:6px; padding:2px 7px; margin:0 4px 4px 0; font-size:12px; color:var(--over); }}
 .tom {{ color:var(--dim); background:var(--card); border:1px dashed var(--line);
   border-radius:12px; padding:18px; }}
 .liste {{ margin:0; padding-left:18px; color:var(--fg); font-size:13.5px; }}
 .liste li {{ margin:3px 0; }}
 code {{ background:var(--card); border:1px solid var(--line); border-radius:5px; padding:1px 5px; font-size:12.5px; }}
 .banner {{ background:var(--card); border:1px solid var(--line); border-radius:10px;
   padding:10px 14px; font-size:12.5px; color:var(--dim); margin-bottom:20px; }}
 footer {{ color:var(--dim); font-size:12.5px; margin-top:34px; border-top:1px solid var(--line); padding-top:14px; }}
</style></head><body><div class="wrap">
<div class="banner">Rejseplan efter dine kriterier i <code>kriterier.json</code>
  &mdash; lavet med <code>SOEG-FLY.bat</code>.</div>

<h1>{html.escape(u_krav['fra'])} &#8594; {html.escape('/'.join(u_krav['til']))} &#8594; {html.escape(h_krav['til'])}</h1>
<div class="undertekst">
  Ud {dato(u_krav['tidligste_dato'])}&#8211;{dato(u_krav['seneste_dato'])} &middot;
  hjem {dato(h_krav['tidligste_dato'])}&#8211;{dato(h_krav['seneste_dato'])} fra
  {html.escape('/'.join(h_krav['fra']))} &middot; mindst {k['min_stjerner']} stjerner &middot;
  {k['personer']} personer &middot; hentet {datetime.now().strftime('%d-%m-%Y %H:%M')}
</div>

{hero(par, k)}

<h2>Udrejse &ndash; {html.escape(', '.join(KABINE.get(x, x) for x in u_krav['kabine']))},
  {'direkte' if u_krav['max_stop'] == 0 else f"max {u_krav['max_stop']} stop"},
  max {kr(u_krav['max_pris_pr_person'])} {v}</h2>
{tabel(ud[:12], v, "Ingen afgange opfyldte alle kravene på én gang.")}
{naer_tabel(list(naer_ud), v)}

<h2>Hjemrejse &ndash; {html.escape(', '.join(KABINE.get(x, x) for x in h_krav['kabine']))},
  max {h_krav['max_stop']} stop, max {h_krav['max_rejsetid_timer']} timer,
  max {kr(h_krav['max_pris_pr_person'])} {v}</h2>
{tabel(hjem[:12], v, "Ingen afgange opfyldte alle kravene på én gang.")}
{naer_tabel(list(naer_hjem), v)}

{kombi}

<h2>Hvad blev valgt fra</h2>
{fravalgte(alle) or '<p class="dim">Ingenting blev valgt fra.</p>'}

<footer>Priserne er Google Flights' totalpris for <b>én</b> person og kan ændre sig,
inden du når at booke. Stjernerne kommer fra din egen liste i
<code>flyselskaber.json</code>. Udrejse og hjemrejse er to enkeltbilletter &ndash;
det er derfor, du kan flyve hjem fra en anden by.</footer>
</div></body></html>"""
    sti.write_text(doc, encoding="utf-8")
