"""Dybe links til sammenligningssiderne - samme rute, datoer og kabine.

Det rigtige kobslink kommer fra Google Flights' egen bookingside (se
gflights.booking_info). Det her er sammenligning ved siden af.
"""
from __future__ import annotations

import urllib.parse
from datetime import date

# Google/IATA-metrokoder som Skyscanner staver anderledes.
SKYSCANNER_ALIAS = {"TYO": "tyoa", "NYC": "nyca", "LON": "lond", "PAR": "pari",
                    "MIL": "mila", "ROM": "roma", "OSA": "osaa", "SEL": "selc"}

SKYSCANNER_KABINE = {"economy": "economy", "premium": "premiumeconomy",
                     "business": "business", "first": "first"}
# Momondo og Kayak tager kabinen som et ekstra led i stien.
STI_KABINE = {"economy": "", "premium": "/premium",
              "business": "/business", "first": "/first"}


def _sky(code: str) -> str:
    return SKYSCANNER_ALIAS.get(code.upper(), code.lower())


def _yymmdd(d: str) -> str:
    return date.fromisoformat(d).strftime("%y%m%d")


def booking_links(frm: str, to: str, out_date: str, home_date: str | None = None,
                  adults: int = 1, currency: str = "DKK",
                  kabine: str = "economy") -> dict:
    """Returnerer {navn: url} for de sider, man kan sammenligne priser paa."""
    frm, to = frm.upper(), to.upper()

    ben = f"{_sky(frm)}/{_sky(to)}/{_yymmdd(out_date)}"
    if home_date:
        ben += f"/{_yymmdd(home_date)}"
    sky = urllib.parse.urlencode({
        "adults": adults, "currency": currency, "preferdirects": "false",
        "cabinclass": SKYSCANNER_KABINE.get(kabine, "economy")})

    datoer = f"{out_date}/{home_date}" if home_date else out_date
    sti = STI_KABINE.get(kabine, "")

    return {
        "Skyscanner": f"https://www.skyscanner.dk/transport/fly/{ben}/?{sky}",
        "Momondo": f"https://www.momondo.dk/flight-search/{frm}-{to}/{datoer}{sti}?sort=price_a",
        "Kayak": f"https://www.kayak.dk/flights/{frm}-{to}/{datoer}{sti}?sort=price_a&adults={adults}",
    }
