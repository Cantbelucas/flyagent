"""Google Flights: byg praecise sog-URL'er (tfs-protobuf) og skrab resultaterne."""
from __future__ import annotations

import base64
import random
import re
import urllib.parse
from dataclasses import dataclass
from typing import Sequence

# --------------------------------------------------------------------------
# Minimal protobuf-writer. Google Flights koder hele sogningen i ?tfs=<base64>.
# --------------------------------------------------------------------------


def _varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _tag(field_no: int, wire: int) -> bytes:
    return _varint((field_no << 3) | wire)


def _len_field(field_no: int, payload: bytes) -> bytes:
    return _tag(field_no, 2) + _varint(len(payload)) + payload


def _str_field(field_no: int, s: str) -> bytes:
    return _len_field(field_no, s.encode("utf-8"))


def _int_field(field_no: int, v: int) -> bytes:
    return _tag(field_no, 0) + _varint(v)


SEAT_CLASS = {"economy": 1, "premium": 2, "business": 3, "first": 4}
TRIP_ROUND, TRIP_ONEWAY = 1, 2


def _airport(code: str) -> bytes:
    return _str_field(2, code.upper())


def _leg(day: str, frm: str, to: str) -> bytes:
    # felt 2 = dato, 13 = afrejselufthavn, 14 = ankomstlufthavn
    return _str_field(2, day) + _len_field(13, _airport(frm)) + _len_field(14, _airport(to))


def build_tfs(legs: Sequence[tuple], adults: int = 1,
              seat: str = "economy", trip: int | None = None) -> str:
    """legs = [(YYYY-MM-DD, FROM, TO), ...]"""
    if trip is None:
        trip = TRIP_ROUND if len(legs) > 1 else TRIP_ONEWAY
    blob = b"".join(_len_field(3, _leg(*leg)) for leg in legs)
    blob += b"".join(_int_field(8, 1) for _ in range(adults))   # 1 pr. voksen
    blob += _int_field(9, SEAT_CLASS.get(seat, 1))
    blob += _int_field(19, trip)
    return base64.urlsafe_b64encode(blob).decode().rstrip("=")


def search_url(legs, adults=1, seat="economy", currency="DKK", hl="en", gl="dk") -> str:
    tfs = build_tfs(legs, adults=adults, seat=seat)
    q = urllib.parse.urlencode({"tfs": tfs, "hl": hl, "gl": gl, "curr": currency})
    return f"https://www.google.com/travel/flights?{q}"


def fallback_url(frm, to, out_date, home_date=None, currency="DKK") -> str:
    """Simpel tekstsogning - bruges hvis tfs-linket ikke giver resultater."""
    q = f"flights from {frm} to {to} on {out_date}"
    if home_date:
        q += f" through {home_date}"
    return ("https://www.google.com/travel/flights?" +
            urllib.parse.urlencode({"q": q, "hl": "en", "gl": "dk", "curr": currency}))


# --------------------------------------------------------------------------
# Parsing af et resultatkort
# --------------------------------------------------------------------------

CURRENCY_SYMBOL = {
    "DKK": r"(?:DKK|kr\.?)", "EUR": r"(?:EUR|€)", "USD": r"(?:USD|\$)",
    "GBP": r"(?:GBP|£)", "SEK": r"(?:SEK|kr\.?)", "NOK": r"(?:NOK|kr\.?)",
}

TIME_RE = re.compile(r"^\s*(\d{1,2}:\d{2})\s?(AM|PM)?(\+\d)?\s*$", re.I)
DUR_RE = re.compile(r"^\s*(\d+)\s*hr(?:\s*(\d+)\s*min)?\s*$|^\s*(\d+)\s*min\s*$", re.I)
STOP_RE = re.compile(r"^\s*(?:(nonstop|direkte)|(\d+)\s*stops?)\s*$", re.I)
ROUTE_RE = re.compile(r"^\s*([A-Z]{3})\s*[–\-—]\s*([A-Z]{3})\s*$")
CO2_RE = re.compile(r"(\d[\d.,]*)\s*kg\s*CO2", re.I)
SEPARATOR_RE = re.compile(r"^[\s –\-—]*$")


def _price_re(currency: str) -> re.Pattern:
    sym = CURRENCY_SYMBOL.get(currency.upper(), re.escape(currency))
    return re.compile(
        r"(?:" + sym + r"\s?([\d][\d.,  ]*\d)|([\d][\d.,  ]*\d)\s?" + sym + r")")


def _to_int(raw: str):
    digits = re.sub(r"[^\d]", "", raw or "")
    return int(digits) if digits else None


@dataclass
class Offer:
    price: int
    currency: str
    airline: str = ""
    depart: str = ""
    arrive: str = ""
    duration_min: int | None = None
    stops: int | None = None
    route: str = ""
    layover: str = ""
    co2_kg: int | None = None
    raw: str = ""

    def as_dict(self) -> dict:
        return dict(self.__dict__)

    def score(self) -> int:
        """Hvor komplet er kortet - bruges naar to kort er samme rejse."""
        return sum(bool(v) for v in (self.airline, self.route, self.layover,
                                     self.duration_min, self.arrive))


# Det samme tilbud findes i to DOM-varianter: en med et element pr. linje, og en
# "flad" skaermlaeser-variant uden linjeskift. Begge skal parses, ellers slipper
# den flade udenom filtrene for stop og pris.
FLAT_TIME_RE = re.compile(r"(\d{1,2}:\d{2}\s?[AP]M)", re.I)
FLAT_ARRIVE_RE = re.compile(r"[–—-]\s*(\d{1,2}:\d{2}\s?[AP]M)(\+\d)?", re.I)
FLAT_DUR_RE = re.compile(r"(\d+)\s*hr(?:\s*(\d+)\s*min)?|(\d+)\s*min", re.I)
FLAT_STOP_RE = re.compile(r"(?:(Nonstop)|(\d{1,2})\s*stops?(?![a-z]))", re.I)
FLAT_ROUTE_RE = re.compile(r"([A-Z]{3})[A-Z][a-z][^–—]*[–—]\s*([A-Z]{3})")
FLAT_DATE_RE = re.compile(r"on\s+\w+,\s*\w+\s*\d{1,2}")
FLAT_LAYOVER_RE = re.compile(
    r"((?:\d+\s*hr\s*)?(?:\d+\s*min\s*)?)(?:layover)?\s*(?:Long layover)?\s*([A-Z]{3})[A-Z][a-z]")


def _parse_flat(text: str, offer: "Offer") -> "Offer":
    """Skaermlaeser-varianten: alt staar i en lang streng, men i fast raekkefolge
    tid - ankomstdato - selskab - varighed - rute - stop - layover - CO2 - pris."""
    times = FLAT_TIME_RE.findall(text)
    if times:
        offer.depart = times[0].upper()
    arr = FLAT_ARRIVE_RE.search(text)
    if arr:
        offer.arrive = arr.group(1).upper() + (arr.group(2) or "")

    dates = list(FLAT_DATE_RE.finditer(text))
    pos = dates[-1].end() if dates else 0        # lige efter ankomstdatoen

    dur = FLAT_DUR_RE.search(text, pos)
    if dur:
        offer.duration_min = (int(dur.group(3)) if dur.group(3)
                              else int(dur.group(1)) * 60 + int(dur.group(2) or 0))
        offer.airline = re.sub(r"Operated by.*$", "", text[pos:dur.start()]).strip(" ,")[:60]
        pos = dur.end()

    route = FLAT_ROUTE_RE.search(text, pos)
    if route:
        offer.route = f"{route.group(1)}-{route.group(2)}"
        pos = route.end()

    stop = FLAT_STOP_RE.search(text, pos)
    if stop:
        offer.stops = 0 if stop.group(1) else int(stop.group(2))
        if offer.stops:
            lay = FLAT_LAYOVER_RE.search(text, stop.end())
            if lay:
                offer.layover = f"{lay.group(1).strip()} {lay.group(2)}".strip()

    co2 = CO2_RE.search(text)
    if co2:
        offer.co2_kg = _to_int(co2.group(1))
    return offer


def parse_card(text: str, currency: str):
    """Google Flights-kort ser saadan ud (en linje pr. element):
        11:10 AM / – / 12:45 PM+1 / Etihad / 18 hr 35 min / CPH–NRT /
        1 stop / 2 hr AUH / 902 kg CO2e / DKK 7,847 / round trip
    """
    # Google blander almindelige mellemrum med haarde og smalle - ellers ser
    # "6:25 PM" og "6:25 PM" ud som to forskellige afgange.
    text = text.replace(" ", " ").replace("\xa0", " ")

    price_m = _price_re(currency).search(text)
    if not price_m:
        return None
    price = _to_int(price_m.group(1) or price_m.group(2))
    if price is None or price < 200:        # "1 stop", "2 hr" osv. er ikke priser
        return None

    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if len(lines) < 4:
        return _parse_flat(text, Offer(price=price, currency=currency.upper(),
                                       raw=text[:300]))
    offer = Offer(price=price, currency=currency.upper(), raw=" | ".join(lines[:12]))

    time_idx = []
    for i, line in enumerate(lines):
        m = TIME_RE.match(line)
        if m:
            time_idx.append(i)
            stamp = m.group(1) + (" " + m.group(2).upper() if m.group(2) else "") + (m.group(3) or "")
            if not offer.depart:
                offer.depart = stamp
            elif not offer.arrive:
                offer.arrive = stamp

        m = DUR_RE.match(line)
        if m and offer.duration_min is None:
            if m.group(3):
                offer.duration_min = int(m.group(3))
            else:
                offer.duration_min = int(m.group(1)) * 60 + int(m.group(2) or 0)

        m = STOP_RE.match(line)
        if m and offer.stops is None:
            offer.stops = 0 if m.group(1) else int(m.group(2))
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if offer.stops and nxt and not _price_re(currency).search(nxt):
                offer.layover = nxt[:60]

        m = ROUTE_RE.match(line)
        if m and not offer.route:
            offer.route = f"{m.group(1)}-{m.group(2)}"

        m = CO2_RE.search(line)
        if m and offer.co2_kg is None:
            offer.co2_kg = _to_int(m.group(1))

    # Selskabet staar paa forste "almindelige" linje efter sidste tidspunkt.
    if time_idx:
        for line in lines[time_idx[-1] + 1:]:
            if SEPARATOR_RE.match(line) or any(
                    r.match(line) for r in (TIME_RE, DUR_RE, STOP_RE, ROUTE_RE)):
                continue
            if _price_re(currency).search(line) or CO2_RE.search(line):
                break
            offer.airline = re.sub(r"Operated by.*$", "", line).strip(" ,")[:60]
            break
    return offer


# --------------------------------------------------------------------------
# Browserdelen
# --------------------------------------------------------------------------

CONSENT_BUTTONS = [
    'button:has-text("Reject all")',
    'button:has-text("Afvis alle")',
    'button[aria-label*="Reject all"]',
    'form[action*="consent"] button',
]

EXTRACT_JS = """() => {
  const out = [];
  for (const li of document.querySelectorAll('li')) {
    if (li.querySelector('li')) continue;            // kun blade i listen
    const t = (li.innerText || '').trim();
    if (t.length > 25 && t.length < 900) out.push(t);
  }
  return out.slice(0, 120);
}"""


async def dismiss_consent(page) -> None:
    """Afvis alle valgfrie cookies, hvis samtykkesiden dukker op."""
    for sel in CONSENT_BUTTONS:
        try:
            btn = page.locator(sel).first
            if await btn.count() and await btn.is_visible():
                await btn.click(timeout=4000)
                await page.wait_for_load_state("domcontentloaded", timeout=15000)
                return
        except Exception:
            continue


async def fetch_offers(context, url: str, currency: str = "DKK",
                       limit: int = 8, timeout_ms: int = 45000):
    """Aabner en sogning og returnerer de billigste tilbud paa siden."""
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        await dismiss_consent(page)
        sym = CURRENCY_SYMBOL.get(currency.upper(), currency)
        try:
            await page.wait_for_function(
                "() => new RegExp(" + repr(sym) + ").test(document.body.innerText)",
                timeout=timeout_ms)
        except Exception:
            pass
        await page.wait_for_timeout(1800 + random.randint(0, 900))
        cards = await page.evaluate(EXTRACT_JS)
    finally:
        await page.close()

    best: dict = {}
    for text in cards:
        offer = parse_card(text, currency)
        if not offer:
            continue
        # Samme rejse optraeder tit i flere DOM-lag - behold det rigeste kort.
        key = (offer.price, offer.depart, offer.duration_min)
        if key not in best or offer.score() > best[key].score():
            best[key] = offer
    offers = sorted(best.values(), key=lambda o: o.price)
    return offers[:limit]


# --------------------------------------------------------------------------
# Koebslinket: klik afgangen frem, saa Google viser bookingsiden med saelgere
# --------------------------------------------------------------------------

VAELG_JS = """(args) => {
  const [pris, tid] = args;
  const kort = [...document.querySelectorAll('[aria-label*="Select flight"]')];
  const traef = kort.find(e => {
    const l = e.getAttribute('aria-label') || '';
    return l.includes('From ' + pris) && (!tid || l.includes('at ' + tid));
  });
  if (!traef) return false;
  traef.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
  return true;
}"""

SAELGER_RE = re.compile(r"Book with ([^\n]+)")
KABINE_LINJE_RE = re.compile(
    r"^((?:Economy|Premium Economy|Business|First)(?:\s*\+\s*"
    r"(?:Economy|Premium Economy|Business|First))*)$", re.M)
BAGAGE_RE = re.compile(r"^(\d+ free (?:carry-on|checked bag)[^\n]*)$", re.M | re.I)


def _fare_pris(blok: str, prisre: re.Pattern):
    """Et selskab viser tit flere billettyper under sig - ogsaa nogle der IKKE
    er den kabine, du sogte ("Not included: Business", "Continue anyway").
    Vi tager den, Google selv kalder den billigste der matcher sogningen."""
    fund = [(m.start(), _to_int(m.group(1) or m.group(2))) for m in prisre.finditer(blok)]
    fund = [(p, v) for p, v in fund if v]
    if not fund:
        return None
    gyldige = []
    for i, (pos, vaerdi) in enumerate(fund):
        slut = fund[i + 1][0] if i + 1 < len(fund) else len(blok)
        vindue = blok[pos:slut]
        if "Not included" in vindue or "Continue anyway" in vindue:
            continue
        gyldige.append((vaerdi, "matching your search" in vindue))
    for vaerdi, matcher in gyldige:
        if matcher:
            return vaerdi
    return gyldige[0][0] if gyldige else fund[0][1]


def _saelgere(tekst: str, currency: str) -> list[dict]:
    """"Book with British AirwaysAirline / DKK 10,533" -> [{navn, pris, er_selskabet}]"""
    afsnit = tekst.split("Booking options", 1)
    if len(afsnit) < 2:
        return []
    prisre = _price_re(currency)
    ud = []
    for blok in afsnit[1].split("Book with ")[1:]:
        navn = blok.split("\n", 1)[0].strip()
        er_selskabet = navn.endswith("Airline")
        navn = re.sub(r"Airline$", "", navn).strip()
        ud.append({"navn": navn[:40], "er_selskabet": er_selskabet,
                   "pris": _fare_pris(blok[:1200], prisre)})
    return ud[:5]


async def booking_info(context, search_url: str, price: int, depart: str = "",
                       currency: str = "DKK", timeout_ms: int = 45000) -> dict | None:
    """Aabner afgangen paa Google Flights og henter selve bookingsiden:
    linket man koeber paa, hvem der saelger, og hvilken kabine hvert ben er i."""
    page = await context.new_page()
    try:
        await page.goto(search_url, wait_until="domcontentloaded", timeout=timeout_ms)
        await dismiss_consent(page)
        try:
            await page.wait_for_function(
                "() => document.querySelectorAll('[aria-label*=\"Select flight\"]').length > 0",
                timeout=timeout_ms)
        except Exception:
            return None
        tid = (depart or "").replace("+1", "").replace("+2", "").strip()
        if not await page.evaluate(VAELG_JS, [str(price), tid]):
            return None

        await page.wait_for_url("**/booking**", timeout=25000)
        tekst = ""
        for _ in range(8):                       # saelgerne kommer lidt efter siden
            await page.wait_for_timeout(2500)
            tekst = await page.evaluate("() => document.body.innerText")
            if "Book with" in tekst:
                break

        kabine = KABINE_LINJE_RE.search(tekst)
        bagage = BAGAGE_RE.findall(tekst)
        return {
            "url": page.url,
            "saelgere": _saelgere(tekst, currency),
            "kabine_detalje": kabine.group(1) if kabine else "",
            "bagage": ", ".join(bagage[:2]),
        }
    except Exception:
        return None
    finally:
        await page.close()
