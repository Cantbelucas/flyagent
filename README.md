# Flyagent — CPH → Tokyo → hjem

To agenter i samme mappe — og **de laver hver sin rapport**:

| Du kører | Du får | Hvad den gør |
|---|---|---|
| **`SOEG-FLY.bat`** ← brug denne | `resultater/`**`rejseplan.html`** | søger efter præcis dine kriterier i `kriterier.json`: klasse, stop, stjerner, prislofter — og henter købslink til hver afgang |
| `python agent.py …` | `resultater/`**`bredsoegning-CPH-TYO.html`** | billigste returfly i en lang periode, **uanset selskab og klasse**. Kriterierne bruges ikke |

Åbner du den forkerte, står det øverst i rapporten. Den brede har en gul stribe
med "Dine kriterier er ikke brugt her".

## To måder at køre den på

**I skyen (anbefalet)** — GitHub kører agenten to gange om dagen, din computer
må være slukket, og du får en mail når prisen falder. Følg **[GUIDE.md](GUIDE.md)**;
det tager cirka 20 minutter én gang for alle.

**På din egen maskine** — hvis du hellere vil have den lokalt:

## Sådan kommer du i gang (to dobbeltklik)

1. Dobbeltklik **`INSTALLER.bat`** — kun første gang. Den henter det, agenten
   skal bruge (tager 1–2 minutter).
   Har du ikke Python, siger den til: hent det på <https://www.python.org/downloads/>
   og husk fluebenet **"Add Python to PATH"** under installationen.
2. Dobbeltklik **`SOEG-FLY.bat`**. Den søger, skriver resultatet i vinduet og
   åbner rapporten `resultater/rejseplan.html` i din browser.

Luk ikke vinduet undervejs — det tager typisk 1–2 minutter.

## Sådan ændrer du søgningen

Alt står i **`kriterier.json`**. Åbn den i Notesblok, ret tallene, gem, og kør
`SOEG-FLY.bat` igen.

```json
"udrejse": {
  "fra": "CPH",
  "til": ["TYO"],              ← TYO = både Haneda og Narita. Kan også være ["HND"]
  "tidligste_dato": "2026-11-01",
  "seneste_dato": "2026-11-05",
  "kabine": ["premium"],       ← economy / premium / business / first
  "max_stop": 0,               ← 0 = kun direkte, 1 = ét stop tilladt
  "max_pris_pr_person": 10000
}
```

`"kabine": ["business", "premium"]` søger begge dele og viser dem side om side.
`"fra": ["TYO", "OSA"]` på hjemrejsen søger både Tokyo og Osaka.
`"personer"` bruges kun til at regne det samlede beløb ud — priserne, agenten
finder, er altid pr. person.


## Kør den automatisk hver dag

Windows har ikke cron, men det tilsvarende hedder Opgavestyring — og den sætter
agenten selv op:

1. Dobbeltklik **`OPRET-AUTOMATIK.bat`**
2. Skriv et klokkeslæt (tryk bare Enter for 08:00)

Så søger agenten hver dag på det tidspunkt. Den kører i baggrunden og **åbner
kun rapporten, hvis prisen er faldet** siden sidste søgning — ellers hører du
ikke fra den. Computeren skal være tændt på tidspunktet.

- Rapporten opdateres hver gang: `resultater/rejseplan.html`
- Prishistorikken gemmes i `resultater/historik.json`
- Alt hvad den skriver, havner i `resultater/log.txt`

Vil du stoppe det igen: dobbeltklik **`FJERN-AUTOMATIK.bat`**.

Virker det ikke, så højreklik på `OPRET-AUTOMATIK.bat` og vælg "Kør som
administrator" — nogle maskiner kræver det for at oprette en opgave.

## Købslinkene

Når agenten har fundet en afgang, klikker den den frem på Google Flights og
gemmer **selve bookingsiden** — den side hvor billetten faktisk købes, med
sælger, pris og Continue-knap. Knappen i rapporten hedder derfor "Køb hos
British Airways", ikke bare "søg videre".

Samtidig henter den to ting, der er nemme at overse:

- **Hvem der sælger.** Tit er der flere: selskabet selv, lastminute.com,
  martiGO — med hver sin pris. Alle står under knappen.
- **Hvilken kabine hvert ben er i.** "Premium economy" fra en søgning betyder
  ofte *Economy + Premium Economy*, altså kun premium på den lange strækning.
  Det står nu direkte i klasse-kolonnen.

Ved siden af ligger Skyscanner, Momondo og Kayak med samme rute, dato og kabine,
hvis du vil sammenligne. (Kiwi er fjernet — deres link landede på forsiden i
stedet for på søgningen.)

## Stjernerne på selskaberne

**`flyselskaber.json`** afgør, hvem der er gode nok. Stjernerne er en kurateret
liste bygget på Skytrax' offentlige stjernerating — ikke et live-tal fra Google
eller Trustpilot, for ingen af dem udstiller flyselskabsratings maskinelt. Er du
uenig i en vurdering, så ret tallet i filen og kør igen.

Selskaber, agenten ikke kender, bliver ikke smidt væk i det stille — de samles
under "Selskaber jeg ikke kender" nederst i rapporten, så du selv kan slå dem op
og skrive dem ind.

## Hvad rapporten viser

- **Bedste samlede rejse** — udrejse + hjemrejse, pris pr. person og i alt, med
  et købslink direkte til bookingsiden for netop den afgang.
- **Alle afgange, der opfylder kravene** — for hvert ben.
- **Tættest på** — de afgange, der kun mangler én ting, med det, der skiller,
  skrevet ud ("2.400 DKK over prisloftet", "22t rejsetid"). Det er her, du kan
  se, hvad et enkelt krav koster dig.
- **Hvad blev valgt fra** — hvorfor resten røg ud.

## Den brede prisjæger

Skal du bare finde det billigste returfly i en lang periode, uanset klasse:

```bash
python agent.py --from CPH --to TYO --start 2026-11-01 --end 2027-01-31 --nights 10-16 --step 3 --max-stops 1
```

Se alle flag med `python agent.py --help`. `--watch 120` gentager søgningen hver
2. time og råber op, når prisen falder.

## Filerne

| Fil | Hvad den gør |
|---|---|
| `soeg.py` | rejseagenten: bygger søgninger ud fra kriterierne og bedømmer hvert tilbud |
| `agent.py` | den brede prisjæger over en hel periode |
| `gflights.py` | bygger Google Flights' `tfs`-URL og skraber/parser resultatkortene |
| `flyselskaber.py` | slår selskabernes stjerner op — også når Google skriver "FinnairJAL" i ét ord |
| `links.py` | dybe links til Skyscanner, Momondo og Kayak |
| `rejserapport.py`, `report.py` | HTML-rapporterne |
| `resultater/` | `rejseplan.html` (kriterier) og `bredsoegning-*.html` (bred prisjagt), plus `rejseplan.json` (rådata), `historik.json` (prisudvikling) og `log.txt` (de automatiske kørsler) |
| `OPRET-AUTOMATIK.bat` / `FJERN-AUTOMATIK.bat` | slår den daglige søgning til og fra |
| `KOER-STILLE.bat` | den automatiske kørsel — den du ikke selv skal klikke på |
| `GUIDE.md` | trin for trin: sæt agenten op i skyen, så den kører uden din computer |
| `.github/workflows/flysoegning.yml` | skemaet GitHub kører efter (to gange dagligt) |
| `resume.py`, `ci_besked.py` | laver resuméet og sender mailen ved prisfald |

## Værd at vide

Priserne er Google Flights' totalpris for **én** person på en **enkeltbillet** —
ud og hjem købes hver for sig, og det er netop dét, der gør det muligt at flyve
premium economy ud og business hjem, og hjem fra en anden by. Enkeltbilletter er
tit dyrere end en returbillet, så tjek også en almindelig returpris, hvis du
ender med samme selskab begge veje.

Priserne ændrer sig løbende — linket er springbrættet, ikke en garanti. Og
Google kan lave om på deres HTML når som helst; kommer der pludselig ingen
resultater, er det næsten altid dét, der er sket.
