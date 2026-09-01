# Sæt flyagenten op i skyen

Når du er færdig med denne guide, søger agenten **to gange om dagen** på
GitHubs servere. Din egen computer må gerne være slukket. Du får en **mail**,
når prisen falder — ellers hører du ikke fra den.

Det koster ingenting, og du skal ikke installere noget på din maskine.
Regn med **20 minutter** første gang.

---

## Trin 1 — Lav en GitHub-konto

Gå til <https://github.com/signup> og opret en konto, hvis du ikke har en.
Brug den mailadresse, du gerne vil have beskederne på.

Bekræft mailen. Det er vigtigt — det er den vej, beskederne kommer.

---

## Trin 2 — Lav et sted at lægge agenten

1. Klik på **+** øverst til højre → **New repository**
2. **Repository name:** `flyagent`
3. Vælg **Public**

   > Hvorfor offentlig? Fordi den gratis udgave af GitHub kun kan vise
   > HTML-rapporten på nettet fra et offentligt sted. Der ligger ingen
   > personlige oplysninger i agenten — kun flypriser. Vil du hellere have
   > det privat, så vælg Private; så virker alt undtagen web-visningen af
   > rapporten, og du får stadig mails og kan hente rapporten som fil.

4. Sæt **ikke** flueben i "Add a README file"
5. Klik **Create repository**

---

## Trin 3 — Læg filerne op

1. Pak `flyagent.zip` ud på dit skrivebord. Du får en mappe med filerne i.
2. På GitHub-siden, du lige lavede, klik linket **uploading an existing file**
   (eller gå til **Add file** → **Upload files**).
3. Åbn den udpakkede mappe, **markér alt indeni** (Ctrl+A) og træk det ind i
   browservinduet. Vent til alle filer står på listen.
4. Klik den grønne **Commit changes**.

### Tjek at den vigtigste fil kom med

Filen `.github/workflows/flysoegning.yml` er den, der får agenten til at køre
af sig selv — og Windows skjuler nogle gange mapper, der starter med et punktum.

Kig på filisten i dit repo. Ser du en mappe ved navn **`.github`**? Så er alt
godt, gå videre til trin 4.

**Ser du den ikke**, laver du den selv:

1. **Add file** → **Create new file**
2. Skriv præcis dette i navnefeltet:
   `.github/workflows/flysoegning.yml`
   (skråstregerne laver mapperne automatisk)
3. Åbn filen `flysoegning.yml` fra den udpakkede mappe i Notesblok, markér alt,
   kopiér, og sæt det ind i det store felt på GitHub.
   Filen ligger i den udpakkede mappe under `.github\workflows\`.
4. **Commit changes**

---

## Trin 4 — Tænd for automatikken

1. Klik fanen **Actions** øverst i dit repo
2. Står der *"Workflows aren't being run on this forked repository"* eller en
   grøn knap **I understand my workflows, go ahead and enable them** — klik den.
3. Klik **Flysoegning** i listen til venstre
4. Klik **Run workflow** → **Run workflow** (den grønne knap)

Nu kører den første søgning. Det tager 5–10 minutter, fordi serveren først skal
installere en browser. Opdater siden og se den gule prik blive til et grønt flueben.

Bagefter kører den **helt af sig selv kl. 07 og kl. 17** dansk tid
(08 og 18 om sommeren — GitHub regner i UTC).

---

## Trin 5 — Se resultatet

Der er tre måder, og du behøver kun den, du bedst kan lide:

### Mailen
Når prisen falder, laver agenten en "issue" i dit repo, og GitHub sender den til
din mail. Den indeholder priserne og et **direkte købslink** til hver afgang.

Vil du prøve det med det samme: kør workflowet manuelt som i trin 4 — så sender
den altid en besked, også uden prisfald.

### Rapporten på nettet (kun offentlige repos)
1. **Settings** → **Pages** i venstre menu
2. Under **Source** vælg **Deploy from a branch**
3. Vælg gren **main** og mappe **/ (root)** → **Save**
4. Vent et par minutter. Så ligger rapporten her:
   `https://DIT-BRUGERNAVN.github.io/flyagent/resultater/rejseplan.html`

Gem den adresse på telefonen. Den viser altid den nyeste søgning.

### Filen direkte
Actions-fanen → klik den seneste kørsel → nederst under **Artifacts** ligger
`rejseplan` som en zip, du kan hente og åbne.

---

## Sådan ændrer du søgningen

Alle dine krav står i **`kriterier.json`**. Ret den direkte på GitHub:

1. Klik filen `kriterier.json` i dit repo
2. Klik blyants-ikonet (**Edit this file**) øverst til højre
3. Ret tallene
4. **Commit changes** nederst

Næste kørsel bruger de nye krav. Vil du se det med det samme, kører du bare
workflowet manuelt (trin 4).

De vigtigste knapper:

| Felt | Betydning |
|---|---|
| `tidligste_dato` / `seneste_dato` | perioden agenten leder i |
| `kabine` | `economy`, `premium`, `business`, `first` — flere ad gangen er ok |
| `max_stop` | `0` = kun direkte, `1` = ét stop tilladt |
| `max_pris_pr_person` | prisloftet for det ben |
| `max_rejsetid_timer` | dropper de urimeligt lange forbindelser |
| `min_stjerner` | `4` = kun selskaber med 4 stjerner eller mere |
| `personer` | bruges kun til at gange totalen op |

Stjernerne på selskaberne står i `flyselskaber.json` og kan rettes samme vej.

---

## Vil du have andre tidspunkter?

Rediger `.github/workflows/flysoegning.yml` og find de to linjer:

```yaml
    - cron: "0 6 * * *"
    - cron: "0 16 * * *"
```

Tallene er `minut time * * *` i **UTC**. Dansk vintertid er UTC+1, sommertid
UTC+2. Vil du have kl. 08 og kl. 20 dansk vintertid, skriver du `0 7` og `0 19`.

---

## Fem ting der er værd at vide

**GitHub sætter skemaet på pause**, hvis der ikke sker noget i repoet i 60 dage.
Agenten gemmer en rapport ved hver kørsel, så det tæller som aktivitet — men
kigger du aldrig forbi i et par måneder, så tjek lige at den stadig kører.

**Kørslen starter sjældent præcis.** GitHub kører planlagte jobs, når der er
plads, typisk 0–20 minutter efter tidspunktet. Det betyder ingenting her.

**Det er gratis** i praksis: offentlige repos har ubegrænset køretid, private
har 2.000 minutter om måneden. To daglige søgninger bruger cirka 300.

**Priserne er pr. person og pr. enkeltbillet.** Ud og hjem købes hver for sig —
det er dét, der gør det muligt at flyve premium den ene vej og business den
anden, og at komme hjem fra en anden by.

**Google kan lave om på deres side.** Sker det, holder agenten op med at finde
noget, og kørslen bliver rød i Actions-fanen. Så skal parseren rettes.

---

## Hvis noget går galt

| Det ser sådan ud | Sådan retter du det |
|---|---|
| Rødt kryds i Actions | Klik kørslen, klik det trin der er rødt, og læs den sidste linje. `soeg.py` der fejler skyldes næsten altid en tastefejl i `kriterier.json` — fx et komma for meget. |
| Ingen mail | Tjek at du har bekræftet din mailadresse, og at Watch-knappen øverst i repoet står på **All Activity**. Og husk: der kommer kun mail, når prisen er faldet. |
| "Ingen komplet rejse fundet" | Kriterierne kan ikke opfyldes samtidig. Kig i afsnittet **Tættest på** i rapporten — der står præcis, hvad der mangler, fx "1.395 DKK over prisloftet". |
| Rapporten på nettet er gammel | Pages opdaterer et par minutter efter hver kørsel. Tryk Ctrl+F5. |
| Vil du stoppe det hele | Actions-fanen → **Flysoegning** → knappen **...** øverst til højre → **Disable workflow**. |

---

## Vil du hellere køre den på din egen maskine?

Det kan den også. Se `README.md` — dobbeltklik `INSTALLER.bat` én gang og
derefter `SOEG-FLY.bat`. Så kræver det bare, at computeren er tændt.
