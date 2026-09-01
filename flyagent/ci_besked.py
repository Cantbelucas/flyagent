"""Kaldes af GitHub Actions efter hver soegning.

Opretter en "issue" i dit repo, som GitHub sender dig som mail. Det sker kun,
naar prisen er faldet - ellers hoerer du ikke fra agenten.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

MAPPE = Path("resultater")


def kr(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def main() -> None:
    status_fil, resume_fil = MAPPE / "status.json", MAPPE / "resume.md"
    if not status_fil.exists() or not resume_fil.exists():
        print("Ingen resultater at sende besked om.")
        return

    status = json.loads(status_fil.read_text(encoding="utf-8"))
    altid = os.environ.get("ALTID_BESKED") == "1"
    faldet = status.get("prisfald") or 0

    if not faldet and not altid:
        pris = status.get("billigste_pr_person")
        print(f"Ingen prisfald ({kr(pris) if pris else 'ingen rejse fundet'}) "
              f"- ingen besked sendt.")
        return

    pris = status.get("billigste_pr_person")
    if faldet:
        titel = f"Prisfald: {kr(faldet)} kr. billigere - nu {kr(pris)} kr. pr. person"
    elif pris:
        titel = f"Flysoegning: {kr(pris)} kr. pr. person"
    else:
        titel = "Flysoegning: ingen rejse opfylder kriterierne"

    try:
        subprocess.run(["gh", "issue", "create", "--title", titel,
                        "--body-file", str(resume_fil)], check=True)
        print(f"Besked sendt: {titel}")
    except FileNotFoundError:
        print("gh-kommandoen findes ikke - besked ikke sendt.", file=sys.stderr)
    except subprocess.CalledProcessError as exc:
        print(f"Kunne ikke oprette besked (kode {exc.returncode}).", file=sys.stderr)


if __name__ == "__main__":
    main()
