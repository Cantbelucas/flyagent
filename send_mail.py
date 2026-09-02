"""Sender rejseplanen som mail til en eller flere modtagere.

Kaldes af GitHub Actions efter hver soegning. Rapporten vedhaeftes som
rejseplan.html, og de vigtigste tal staar i selve mailen.

Alle indstillinger kommer fra GitHub Secrets - der maa ALDRIG staa
mailadresser eller kodeord i denne fil, for repoet er offentligt:

  MAIL_SERVER   fx smtp.gmail.com
  MAIL_PORT     587 (STARTTLS) eller 465 (SSL)
  MAIL_BRUGER   afsenderens mailadresse
  MAIL_KODE     app-adgangskode (IKKE din normale adgangskode)
  MAIL_TIL      modtagere, adskilt af komma
  MAIL_FRA      valgfri afsender, ellers bruges MAIL_BRUGER
"""
from __future__ import annotations

import json
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path

MAPPE = Path("resultater")


def kr(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def indstillinger() -> dict | None:
    """Henter opsaetningen fra miljoeet. Returnerer None hvis noget mangler."""
    n = {k: os.environ.get(k, "").strip()
         for k in ("MAIL_SERVER", "MAIL_PORT", "MAIL_BRUGER", "MAIL_KODE", "MAIL_TIL")}
    mangler = [k for k, v in n.items() if not v]
    if mangler:
        print(f"Mail er ikke sat op ({', '.join(mangler)} mangler) - springer over.")
        return None
    n["MAIL_FRA"] = os.environ.get("MAIL_FRA", "").strip() or n["MAIL_BRUGER"]
    n["modtagere"] = [a.strip() for a in n["MAIL_TIL"].split(",") if a.strip()]
    if not n["modtagere"]:
        print("MAIL_TIL indeholder ingen adresser - springer over.")
        return None
    return n


def emne(status: dict) -> str:
    faldet, pris = status.get("prisfald") or 0, status.get("billigste_pr_person")
    if faldet:
        return f"Prisfald: {kr(faldet)} kr. billigere - nu {kr(pris)} kr. pr. person"
    if pris:
        return f"Flysoegning: {kr(pris)} kr. pr. person"
    return "Flysoegning: ingen rejse opfylder kriterierne"


def brevtekst(status: dict) -> tuple[str, str]:
    """Bygger en kort tekst- og HTML-udgave af de vigtigste tal."""
    pris = status.get("billigste_pr_person")
    ialt = status.get("billigste_i_alt")
    faldet = status.get("prisfald") or 0
    tid = status.get("tidspunkt", "")

    linjer = [f"Soegt {tid}." if tid else ""]
    if pris:
        linjer.append(f"Billigste rejse: {kr(pris)} kr. pr. person"
                      + (f" ({kr(ialt)} kr. i alt)." if ialt else "."))
        if faldet:
            linjer.append(f"Prisen er faldet {kr(faldet)} kr. siden sidst.")
        linjer.append(f"Fundet {status.get('antal_udrejser', 0)} udrejser og "
                      f"{status.get('antal_hjemrejser', 0)} hjemrejser, der opfylder kravene.")
    else:
        linjer.append("Ingen rejse opfylder kriterierne lige nu.")
    linjer.append("")
    linjer.append("Den fulde rapport med alle afgange og koebslinks er vedhaeftet "
                  "som rejseplan.html - aabn den i en browser.")
    tekst = "\n".join(x for x in linjer if x is not None)

    stor = f"{kr(pris)} kr." if pris else "Ingen rejse fundet"
    fald = (f'<p style="margin:0 0 16px;color:#1a7f37;font-weight:600">'
            f'Prisen er faldet {kr(faldet)} kr. siden sidste soegning.</p>') if faldet else ""
    html = f"""<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
     max-width:520px;color:#1c1c1e;line-height:1.5">
  <p style="margin:0 0 4px;color:#6b6b70;font-size:13px">Flysoegning{f' &middot; {tid}' if tid else ''}</p>
  <p style="margin:0 0 4px;font-size:28px;font-weight:700">{stor}</p>
  <p style="margin:0 0 16px;color:#6b6b70;font-size:14px">pr. person{f' &middot; {kr(ialt)} kr. i alt' if ialt else ''}</p>
  {fald}
  <p style="margin:0 0 16px">Fundet <strong>{status.get('antal_udrejser', 0)}</strong> udrejser og
     <strong>{status.get('antal_hjemrejser', 0)}</strong> hjemrejser, der opfylder kravene.</p>
  <p style="margin:0;padding:12px 14px;background:#f5f5f7;border-radius:8px;font-size:14px">
     Den fulde rapport med alle afgange og koebslinks er vedhaeftet som
     <strong>rejseplan.html</strong> &ndash; aabn den i en browser.</p>
</div>"""
    return tekst, html


def main() -> None:
    status_fil, rapport = MAPPE / "status.json", MAPPE / "rejseplan.html"
    if not status_fil.exists():
        print("Ingen resultater at sende.")
        return

    status = json.loads(status_fil.read_text(encoding="utf-8"))
    altid = os.environ.get("ALTID_BESKED") == "1"
    if not (status.get("prisfald") or 0) and not altid:
        print("Ingen prisfald - ingen mail sendt.")
        return

    n = indstillinger()
    if n is None:
        return

    tekst, html = brevtekst(status)
    besked = EmailMessage()
    besked["Subject"] = emne(status)
    besked["From"] = n["MAIL_FRA"]
    besked["To"] = ", ".join(n["modtagere"])
    besked.set_content(tekst)
    besked.add_alternative(html, subtype="html")

    if rapport.exists():
        besked.add_attachment(rapport.read_bytes(), maintype="text", subtype="html",
                              filename="rejseplan.html")
    else:
        print("rejseplan.html findes ikke - sender mailen uden vedhaeftning.")

    port = int(n["MAIL_PORT"])
    sammenhaeng = ssl.create_default_context()
    try:
        if port == 465:
            with smtplib.SMTP_SSL(n["MAIL_SERVER"], port, context=sammenhaeng, timeout=30) as s:
                s.login(n["MAIL_BRUGER"], n["MAIL_KODE"])
                s.send_message(besked)
        else:
            with smtplib.SMTP(n["MAIL_SERVER"], port, timeout=30) as s:
                s.starttls(context=sammenhaeng)
                s.login(n["MAIL_BRUGER"], n["MAIL_KODE"])
                s.send_message(besked)
    except smtplib.SMTPAuthenticationError:
        print("Mailserveren afviste login. Bruger du en app-adgangskode?", file=sys.stderr)
        raise
    except OSError as fejl:
        print(f"Kunne ikke naa mailserveren: {fejl}", file=sys.stderr)
        raise

    print(f"Mail sendt til {len(n['modtagere'])} modtager(e).")


if __name__ == "__main__":
    main()
