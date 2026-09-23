# Bethesda Mittagsmenü-Checker

**⚠️ Inoffizielles Community-Projekt.** Dieses Tool steht in keiner
Verbindung zum Bethesda Spital Basel und wird nicht von ihm betrieben,
gesponsert oder unterstützt. Es liest lediglich die öffentlich einsehbare
Menü-Seite aus. Alle Rechte an Name, Logo und Inhalten der Speisekarte
liegen beim Bethesda Spital. Nutzung auf eigenes Risiko, siehe auch
[Lizenz](#lizenz--license) und Haftungsausschluss unten.

Prüft wöchentlich (Montagmorgen) automatisiert die Mittagsmenü-Seite des
Bethesda Spitals **und die beiden dort verlinkten Wochen-PDFs** (aktuelle und
kommende Woche) auf frei konfigurierbare Gerichte (Standard: Cordon Bleu)
**im Mittagsmenü** und schickt bei Treffer eine Benachrichtigung per Push
(ntfy.sh) und/oder E-Mail. Die Meldung nennt das gefundene Gericht, die
Fundstelle (Webseite oder PDF) und ob es für die **ganze Woche** gilt
("Cordonbleu-Woche") oder nur für einen **einzelnen Tag**.

---

## Warum GitHub Actions?

Kein eigener Server/Raspberry Pi nötig. GitHub Actions bietet kostenlose,
zeitgesteuerte ("Cron") Jobs in der Cloud – der Job läuft automatisch jeden
Montagmorgen, ganz ohne dass du etwas anklicken musst. Läuft der Job einmal,
läuft er quasi für immer weiter (auch monatelang), solange das Repo existiert.
Für öffentliche Repos sind Standard-GitHub-Hosted-Runner-Minuten zudem
komplett kostenlos und unlimitiert (Stand: GitHub-Dokumentation 2026) –
für ein wöchentliches Skript wie dieses spielt das aber ohnehin keine Rolle,
egal ob privates oder öffentliches Repo.

## Setup (einmalig, ca. 10 Minuten)

1. **Neues GitHub-Repo anlegen** (privat oder öffentlich) und diesen Ordner
   hochladen/pushen.

2. **Benachrichtigungskanal(e) einrichten.** Beide Kanäle sind komplett
   unabhängig voneinander. Du kannst nur ntfy, nur E-Mail, beide parallel,
   oder (zum Testen) auch keinen einrichten - dann erscheint der Treffer nur
   im Actions-Log. Secrets, die du nicht setzt, deaktivieren einfach den
   jeweiligen Kanal, es passiert nichts Falsches.

   **Option A - ntfy.sh (Push, kein Account nötig):**
   - App installieren: [ntfy für Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy)
     oder [ntfy für iOS](https://apps.apple.com/us/app/ntfy/id1625396347).
   - In der App ein "Topic" abonnieren – frei wählbarer, **schwer erratbarer**
     Name, z.B. `menu-check-8f3k2x9q`. Ein ntfy-Topic ist kein Login-System,
     sondern eher ein öffentlicher Kanalname: Wer den Namen kennt, kann
     mitlesen. Wähle ihn entsprechend zufällig, vor allem wenn das Repo
     öffentlich ist (siehe auch Hinweise zur Veröffentlichung unten).
   - Im Repo als Secret hinterlegen:
     `Settings → Secrets and variables → Actions → New repository secret`
     Name: `NTFY_TOPIC`, Wert: dein gewählter Topic-Name.

   **Option B - E-Mail (SMTP):** funktioniert mit jedem SMTP-Anbieter; hier
   am Beispiel Gmail:
   - Voraussetzung: 2-Faktor-Authentifizierung für den Google-Account aktiviert.
   - Ein **App-Passwort** erzeugen: [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
     → App auswählen (z.B. "Mail"), Passwort generieren (16-stelliger Code).
     Das ist NICHT dein normales Gmail-Passwort - nur für diesen Zweck gültig
     und jederzeit widerrufbar.
   - Folgende Secrets im Repo hinterlegen
     (`Settings → Secrets and variables → Actions → New repository secret`):

     | Secret Name | Wert |
     |---|---|
     | `SMTP_HOST` | `smtp.gmail.com` |
     | `SMTP_PORT` | `587` (optional, ist der Default) |
     | `SMTP_USER` | deine Gmail-Adresse |
     | `SMTP_PASSWORD` | das 16-stellige App-Passwort |
     | `EMAIL_TO` | Ziel-Adresse(n), s.u. |
     | `EMAIL_FROM` | optional, Default ist `SMTP_USER` |

     **Mehrere Ziel-E-Mails:** `EMAIL_TO` akzeptiert eine mit Komma oder
     Semikolon getrennte Liste, z.B.:
     ```
     ich@example.com, partner@example.com, noch-jemand@example.com
     ```

     Andere Anbieter (z.B. Bluewin, GMX, eigener Mailserver) funktionieren
     genauso - einfach `SMTP_HOST`/`SMTP_PORT` entsprechend anpassen.

   **Beide Optionen parallel:** einfach beide Secret-Sets gleichzeitig
   hinterlegen - `menu_check.py` schickt dann bei einem Treffer sowohl eine
   ntfy-Push-Nachricht als auch eine E-Mail.

3. **Actions aktivieren**: Im Repo unter dem Reiter "Actions" bestätigen,
   dass Workflows laufen dürfen (bei neu erstellten Repos meist schon aktiv).

4. **Fertig.** Der Workflow läuft automatisch jeden Montag um 05:30 UTC
   (≈ 6:30–7:30 Schweizer Zeit, je nach Sommer-/Winterzeit). Für das
   Lesen der PDFs (OCR) installiert der Workflow selbst Tesseract (kein
   Setup nötig).

## Benachrichtigung testen, ohne auf ein Treffer-Gericht zu warten

Es kann Monate dauern, bis ein passendes Gericht auf der
Speisekarte steht. Um die konfigurierten Kanäle (ntfy und/oder E-Mail)
unabhängig davon jederzeit zu testen:

**Über die GitHub-Weboberfläche (empfohlen):**
1. Im Repo auf den Reiter "Actions" gehen.
2. "Bethesda Menu Check" auswählen → "Run workflow".
3. Die Checkbox "Nur Test-Benachrichtigung senden" aktivieren → "Run workflow".
4. Nach ca. 10-20 Sekunden solltest du eine klar als Test gekennzeichnete
   Nachricht über alle konfigurierten Kanäle erhalten.

Das prüft die echten Zugangsdaten (SMTP-Login, ntfy-Topic) und läuft exakt
über denselben Code-Pfad wie ein echter Treffer - nur mit Test-Text statt
echtem Menü-Inhalt. Die Testnachricht nutzt Beispieldaten (Cordonbleu-Woche)
und deine eigene [E-Mail-Vorlage](#e-mail-text-anpassen) - so siehst du
vorab, wie die Mail aussehen wird. `notified_dates.json` wird dabei nicht
verändert.

**Lokal:**
```bash
pip install -r requirements.txt

python menu_check.py --test
# oder gleichwertig:
TEST_NOTIFICATION=1 python menu_check.py
```

Falls kein Kanal konfiguriert ist, meldet das Skript das klar und bricht ab,
statt stillschweigend nichts zu tun.

**Manueller echter Testlauf** (statt Test-Benachrichtigung): Im Repo unter
"Actions" → "Bethesda Menu Check" → "Run workflow" klicken, Checkbox NICHT
aktivieren – so lässt sich der normale Ablauf jederzeit auslösen, ohne auf
den nächsten Montag zu warten.

## Wie funktioniert die Erkennung?

**Quelle 1 - Webseite**
- `menu_check.py` lädt die Menü-Seite und trennt sie in Mittags- und
  Abendmenü-Abschnitte (Abendmenü wird komplett ignoriert).
- Innerhalb des Mittagsmenü-Abschnitts werden alle Tage geprüft (einschränkbar
  mit `TAGE`).
- Gesucht wird per Regex nach Schreibvarianten der konfigurierten Gerichte
  (inkl. Umlaut-, Bindestrich- und Gross-/Kleinschreibungs-Varianten).

**Quelle 2 - Wochen-PDFs** (`Mittag&Abend KW38.pdf`, `... KW39.pdf`)
- Die PDF-Links ändern sich jede Woche und werden deshalb bei jedem Lauf von
  der Menü-Seite gelesen (alle PDF-Links mit `KW##` im Dateinamen). Das Jahr
  wird aus der Kalenderwoche abgeleitet; bereits vergangene Wochen werden
  übersprungen (die Seite nennt am Montagmorgen teils noch die Vorwoche
  "aktuelle Woche").
- Das PDF ist eine Tabelle: Spalten = Menülinien (`Mittags. Cordonbleu` bzw.
  `Mittags. Pastateller`, `Mittags. Vital`, `Mittags. Vegi`, `Suppe / Dessert`),
  Zeilen = Montag bis Sonntag. Die PDFs enthalten **keinen echten Text**
  (keine Textebene), die gepunkteten Tabellenlinien sind aber Vektoren. Das
  Skript liest daraus das Raster und liest **jede Zelle einzeln per OCR
  (Tesseract)**. Hätte ein PDF eine Textebene, würde diese zuerst genutzt.
- Nur die Mittagsseite zählt (erkannt an der Kopfzeile `Mittags. ...`), die
  Abendseite wird nicht gelesen.
- **Einordnung des Treffers:**
  - Stichwort in einer **Spaltenüberschrift** (z.B. `Mittags. Cordonbleu
    (Schweinefleisch)`) → die Menülinie gibt es **die ganze Woche**
    (Cordonbleu-Woche). Gemeldet wird nur das, ohne Auflistung der
    einzelnen Tagesgerichte.
  - Stichwort in der **Zelle eines Tages** → **nur dieser Tag**
  - Tabellenraster nicht erkannt (Layout geändert) → Meldung "Tag/Woche
    unklar" mit Hinweis, das PDF anzusehen

**Doppelmeldungen vermeiden:** `notified_dates.json` merkt sich Einzeltage
als Datum (`2026-09-28`) und ganze Wochen als `woche:2026-W39`. Bestehende
Einträge bleiben gültig. Einzeltage innerhalb einer Cordonbleu-Woche werden
nicht zusätzlich gemeldet. Schlägt der Versand über alle aktivierten Kanäle
fehl, wird der Treffer **nicht** als gemeldet gespeichert und beim nächsten
Lauf erneut versucht.

## E-Mail-Text anpassen

Betreff und Text der E-Mail lassen sich ohne Code-Änderung anpassen, als
**Repository Variablen** (`Settings → Secrets and variables → Actions →
Variables → New repository variable`): `EMAIL_SUBJECT` und `EMAIL_BODY`.
Ohne diese Variablen gilt die Standardvorlage. Die ntfy-Push-Nachricht nutzt
immer die Standardvorlage.

Platzhalter in geschweiften Klammern:

| Platzhalter | Inhalt (Beispiel) |
|---|---|
| `{titel}` | Kurztitel für den Betreff: `Cordonbleu-Woche (KW 39)` bzw. `<Gericht> - nur Mittwoch, 23.09.2026` |
| `{gericht}` | Zeile, in der das Stichwort gefunden wurde (`Cordonbleu`); bei ganzer Woche nur das Stichwort selbst |
| `{beschreibung}` | Gericht inkl. Folgezeilen/Beilagen (nur bei Einzeltag, siehe `{details}`) |
| `{details}` | `Gericht:\n<beschreibung>` - bei ganzer Woche leer (Cordonbleu-Woche allein reicht als Info, ohne Auflistung der Tagesgerichte) |
| `{umfang}` | `ganze Woche (KW 39)` / `nur Montag, 28.09.2026` / `Tag/Woche unklar (KW 39)` |
| `{tag}` | Wochentag oder `ganze Woche` |
| `{datum}` | Datum bzw. Zeitraum der Woche |
| `{woche}` | `KW 39 (aktuelle Woche, 21.09.-27.09.2026)` |
| `{kw}` | Kalenderwoche (`39`) |
| `{quelle}` | `Webseite (Mittagsmenü)` oder `PDF Mittag&Abend KW39.pdf` |
| `{quell_url}` | Link zur Fundstelle (PDF bzw. Menü-Seite) |
| `{url}` | Menü-Seite |
| `{stichwoerter}` | konfigurierte Suchbegriffe |
| `{hinweis}` | Zusatzhinweis nur bei "Tag/Woche unklar", sonst leer |

`\n` steht für einen Zeilenumbruch (nützlich, falls die Variable einzeilig
eingegeben wird; mehrzeilige Eingabe funktioniert ebenfalls). Unbekannte
Platzhalter bleiben unverändert stehen, eine fehlerhafte Vorlage (z.B.
unpaarige Klammer) fällt mit Warnung im Log auf die Standardvorlage zurück.

Beispiel:

```
EMAIL_SUBJECT:  Cordon Bleu! {titel}
EMAIL_BODY:     Hallo!\n\n{titel}\nWann: {umfang} ({woche})\nWo: {quelle}\n\n{details}\n{quell_url}
```

## Weitere Einstellungen (optional, Repository Variablen)

| Variable | Wirkung |
|---|---|
| `TAGE` | Einzeltage, die gemeldet werden, kommagetrennt (z.B. `Montag, Freitag`). Standard: alle Tage. Ganze-Woche-Treffer werden immer gemeldet. |
| `PDF_CHECK` | `0` schaltet die PDF-Prüfung ab (nur Webseite). |
| `PDF_OCR` | `never` schaltet OCR ab (dann werden nur PDFs mit Textebene gelesen, die aktuellen haben keine). |
| `OCR_LANG` | Tesseract-Sprache, Standard `deu`. |

## PDF-Diagnose

Damit man sieht, was das Skript aus den PDFs tatsächlich liest (erkanntes
Raster, Text jeder Zelle) und wie es Treffer einordnet, z.B. falls das
PDF-Layout mal geändert wird:

- GitHub: "Actions" → "Bethesda Menu Check" → "Run workflow" → Checkbox
  "Nur PDF-Diagnose" aktivieren. Die Ausgabe steht im Log des Laufs.
- Lokal: `python menu_check.py --dump-pdf` (PDFs von der Seite) oder
  `python menu_check.py --dump-pdf "Mittag&Abend KW38.pdf"` (lokale Datei).
  Für OCR lokal wird `tesseract-ocr` samt Sprachpaket benötigt.

## Gesuchte Gerichte anpassen (auch in Zukunft)

Standardmässig (im veröffentlichten Code) wird nur nach Cordon Bleu gesucht.
Das lässt sich jederzeit ändern, **ohne den Code anzufassen** - einfach ein
Secret `KEYWORDS` (oder eine Repository Variable, siehe Hinweis unten)
mit einer kommagetrennten Liste hinterlegen:

```
Cordon Bleu, Fleischkäse, Leberkäse, Wienerschnitzel, Zürcher Geschnetzeltes
```

**Wichtig - `KEYWORDS` überschreibt, es ergänzt nicht:** Ist das Secret
gesetzt, wird **ausschliesslich** die dort eingetragene Liste verwendet,
der Code-Default wird komplett ignoriert. Wer also z.B. privat zusätzlich
zu Cordon Bleu auch Fleischkäse und Leberkäse gemeldet bekommen möchte,
muss **alle drei zusammen** ins Secret schreiben - nicht nur die neuen
Begriffe. Setzt man `KEYWORDS="Schnitzel"`, wird **nur** noch nach
Schnitzel gesucht, Cordon Bleu fällt komplett weg, solange es nicht mit
im Secret steht.

Das Skript ist bei der Schreibweise recht tolerant:
- **Umlaute:** `ä`/`ö`/`ü`/`ß` matchen automatisch auch die ausgeschriebene
  Variante (`Käse` matcht auch `Kaese`).
- **Mehrere Wörter:** ein Leerzeichen im Suchbegriff (z.B. `Cordon Bleu`)
  matcht automatisch auch zusammengeschrieben oder mit Bindestrich
  (`CordonBleu`, `Cordon-Bleu`). Das gilt auch für eigene Begriffe wie
  `Wiener Schnitzel` → matcht auch `Wienerschnitzel`.
- **Gross-/Kleinschreibung** spielt keine Rolle.

Wenn `KEYWORDS` nicht gesetzt ist, gilt automatisch der Code-Default
(Cordon Bleu) - siehe `DEFAULT_KEYWORDS` in `menu_check.py`.

*Hinweis:* Da die Gerichte-Liste keine sensible Information ist, kannst du
sie statt als Secret auch bequemer einsehbar als
**Repository Variable** pflegen (`Settings → Secrets and variables →
Actions → Variables → New repository variable`, Name `KEYWORDS`) - der
Workflow müsste dann `${{ vars.KEYWORDS }}` statt `${{ secrets.KEYWORDS }}`
referenzieren (eine Zeile in `check-menu.yml`).

## Lizenz / License

Dieses Projekt steht unter der **GNU General Public License v3.0 oder
später** (GPL-3.0-or-later). Eine vollständige Kopie des Lizenztextes
gehört als `LICENSE`-Datei ins Repo-Hauptverzeichnis (siehe
[gnu.org/licenses](https://www.gnu.org/licenses/)).

Kurzfassung: Du darfst dieses Programm frei nutzen, verändern und
weitergeben. Abgeleitete Werke müssen ebenfalls unter der GPL(-kompatiblen
Lizenz) veröffentlicht werden, Änderungen sind zu kennzeichnen. Es gibt
keinerlei Gewährleistung. Details siehe Lizenztext.

---
---

# Bethesda Lunch Menu Checker (English)

**⚠️ Unofficial community project.** This tool has no affiliation with,
and is not operated, sponsored, or endorsed by, Bethesda Spital Basel. It
merely reads the publicly available menu page. All rights to the name,
logo, and menu content belong to Bethesda Spital. Use at your own risk,
see also [License](#lizenz--license) and disclaimer above.

Automatically checks the Bethesda Spital lunch menu page **and the two
weekly PDFs linked there** (current and upcoming week) every Monday morning
for freely configurable dishes (default: Cordon Bleu) **in the lunch menu**,
and sends a notification via push (ntfy.sh) and/or email on a match. The
message names the dish found, where it was found (web page or PDF), and
whether it applies to the **whole week** ("Cordonbleu week") or just a
**single day**.

## Why GitHub Actions?

No server or Raspberry Pi required. GitHub Actions provides free,
scheduled ("cron") jobs in the cloud - the job runs automatically every
Monday morning without you having to click anything. Once set up, it keeps
running indefinitely (even for months) as long as the repo exists. For
public repositories, standard GitHub-hosted runner minutes are also
completely free and unlimited (per GitHub's 2026 documentation) - though
for a once-a-week script like this, that distinction barely matters either
way.

## Setup (one-time, ~10 minutes)

1. **Create a new GitHub repo** (private or public) and push this folder.

2. **Set up notification channel(s).** Both channels are fully independent.
   You can enable only ntfy, only email, both in parallel, or (for testing)
   neither - in that case a match just shows up in the Actions log. Any
   secret you don't set simply disables that channel; nothing breaks.

   **Option A - ntfy.sh (push, no account needed):**
   - Install the app: [ntfy for Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy)
     or [ntfy for iOS](https://apps.apple.com/us/app/ntfy/id1625396347).
   - Subscribe to a "topic" in the app - pick a **hard-to-guess** name, e.g.
     `menu-check-8f3k2x9q`. An ntfy topic isn't a login system but more like
     a public channel name: anyone who knows it can read it. Choose it
     accordingly, especially for public repos (see checklist below).
   - Add it as a repo secret:
     `Settings → Secrets and variables → Actions → New repository secret`
     Name: `NTFY_TOPIC`, value: your chosen topic name.

   **Option B - Email (SMTP):** works with any SMTP provider; example with Gmail:
   - Requires 2-factor authentication enabled on the Google account.
   - Generate an **app password**: [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
     → pick an app (e.g. "Mail"), generate a 16-character code. This is NOT
     your regular Gmail password - it's scoped to this purpose and can be
     revoked anytime.
   - Add these repo secrets
     (`Settings → Secrets and variables → Actions → New repository secret`):

     | Secret name | Value |
     |---|---|
     | `SMTP_HOST` | `smtp.gmail.com` |
     | `SMTP_PORT` | `587` (optional, this is the default) |
     | `SMTP_USER` | your Gmail address |
     | `SMTP_PASSWORD` | the 16-character app password |
     | `EMAIL_TO` | recipient(s), see below |
     | `EMAIL_FROM` | optional, defaults to `SMTP_USER` |

     **Multiple recipients:** `EMAIL_TO` accepts a comma- or
     semicolon-separated list, e.g.:
     ```
     me@example.com, partner@example.com, someone-else@example.com
     ```

     Other providers (e.g. Outlook, your own mail server) work the same way -
     just adjust `SMTP_HOST`/`SMTP_PORT` accordingly.

   **Both channels in parallel:** just set up both secret sets at once -
   `menu_check.py` will then send both an ntfy push and an email on a match.

3. **Enable Actions**: under the "Actions" tab, confirm workflows are
   allowed to run (usually already enabled for newly created repos).

4. **Done.** The workflow runs automatically every Monday at 05:30 UTC
   (≈ 6:30-7:30 Swiss time, depending on daylight saving). To read the
   PDFs (OCR) the workflow installs Tesseract itself (no setup needed).

## Testing notifications without waiting for a matching dish

It can take months before a matching dish shows up on the menu. To test
the configured channels (ntfy and/or email) independently of that:

**Via the GitHub web UI (recommended):**
1. Go to the "Actions" tab in the repo.
2. Select "Bethesda Menu Check" → "Run workflow".
3. Enable the "Send test notification only" checkbox → "Run workflow".
4. Within ~10-20 seconds you should receive a clearly marked test message
   on all configured channels.

This validates the real credentials (SMTP login, ntfy topic) using the
exact same code path as a real match - just with test text instead of
actual menu content. The test message uses sample data (a Cordonbleu week)
and your own [email template](#customizing-the-email-text), so you can
preview what the mail will look like. `notified_dates.json` is not modified.

**Locally:**
```bash
pip install -r requirements.txt

python menu_check.py --test
# equivalently:
TEST_NOTIFICATION=1 python menu_check.py
```

If no channel is configured, the script clearly reports that and exits,
instead of silently doing nothing.

**Manual real check run** (instead of a test notification): in the repo,
go to "Actions" → "Bethesda Menu Check" → "Run workflow", leave the
checkbox unchecked - this triggers the normal check anytime, without
waiting for the next Monday.

## How does the detection work?

**Source 1 - web page**
- `menu_check.py` loads the menu page and splits it into lunch and dinner
  sections (dinner is fully ignored).
- Within the lunch section, all days are checked (can be restricted with
  `TAGE`).
- Matching is done via regex against spelling variants of the configured
  dishes (including umlaut, hyphen, and case variants).

**Source 2 - weekly PDFs** (`Mittag&Abend KW38.pdf`, `... KW39.pdf`)
- The PDF links change every week, so they are read from the menu page on
  every run (all PDF links with `KW##` in the file name). The year is derived
  from the calendar week; weeks that are already over are skipped (on Monday
  morning the page sometimes still calls last week the "current week").
- The PDF is a table: columns = menu lines (`Mittags. Cordonbleu` or
  `Mittags. Pastateller`, `Mittags. Vital`, `Mittags. Vegi`, `Suppe / Dessert`),
  rows = Monday to Sunday. The PDFs contain **no real text** (no text
  layer), but the dotted table lines are vectors. The script reads the grid
  from them and reads **each cell separately via OCR (Tesseract)**. If a PDF
  ever has a text layer, that is used first.
- Only the lunch page counts (recognized by the `Mittags. ...` header row),
  the dinner page is not read.
- **Classifying a match:**
  - keyword in a **column header** (e.g. `Mittags. Cordonbleu
    (Schweinefleisch)`) → that menu line exists **the whole week**
    (Cordonbleu week). Only that is reported, without listing the
    individual daily dishes.
  - keyword in the **cell of a day** → **that day only**
  - table grid not recognized (layout changed) → "day/week unclear" message
    asking you to look at the PDF

**Avoiding duplicate notifications:** `notified_dates.json` remembers single
days as a date (`2026-09-28`) and whole weeks as `woche:2026-W39`. Existing
entries stay valid. Single days inside a Cordonbleu week are not reported
additionally. If sending fails on every enabled channel, the match is **not**
saved as notified and is retried on the next run.

## Customizing the email text

Subject and body of the email can be customized without touching the code,
as **repository variables** (`Settings → Secrets and variables → Actions →
Variables → New repository variable`): `EMAIL_SUBJECT` and `EMAIL_BODY`.
Without them the default template applies. The ntfy push message always uses
the default template.

Placeholders in curly braces (names are German, as in the code):

| Placeholder | Content (example) |
|---|---|
| `{titel}` | short title for the subject line: `Cordonbleu-Woche (KW 39)` or `<dish> - nur Mittwoch, 23.09.2026` |
| `{gericht}` | line in which the keyword was found (`Cordonbleu`); for a whole week, just the keyword itself |
| `{beschreibung}` | dish including following lines/sides (single-day match only, see `{details}`) |
| `{details}` | `Gericht:\n<beschreibung>` - empty for a whole week (the Cordonbleu week itself is enough info, no listing of daily dishes) |
| `{umfang}` | `ganze Woche (KW 39)` / `nur Montag, 28.09.2026` / `Tag/Woche unklar (KW 39)` |
| `{tag}` | weekday or `ganze Woche` |
| `{datum}` | date or date range of the week |
| `{woche}` | `KW 39 (aktuelle Woche, 21.09.-27.09.2026)` |
| `{kw}` | calendar week (`39`) |
| `{quelle}` | `Webseite (Mittagsmenü)` or `PDF Mittag&Abend KW39.pdf` |
| `{quell_url}` | link to where it was found (PDF or menu page) |
| `{url}` | menu page |
| `{stichwoerter}` | configured search terms |
| `{hinweis}` | extra note only for "day/week unclear" matches, otherwise empty |

`\n` stands for a line break (handy if the variable is entered on one
line; multi-line input works too). Unknown placeholders are left as they
are; a broken template (e.g. unbalanced brace) falls back to the default
template with a warning in the log.

Example:

```
EMAIL_SUBJECT:  Cordon Bleu! {titel}
EMAIL_BODY:     Hello!\n\n{titel}\nWhen: {umfang} ({woche})\nWhere: {quelle}\n\n{details}\n{quell_url}
```

## More settings (optional, repository variables)

| Variable | Effect |
|---|---|
| `TAGE` | Single days that are reported, comma-separated (e.g. `Montag, Freitag`). Default: all days. Whole-week matches are always reported. |
| `PDF_CHECK` | `0` disables the PDF check (web page only). |
| `PDF_OCR` | `never` disables OCR (then only PDFs with a text layer are read; the current ones have none). |
| `OCR_LANG` | Tesseract language, default `deu`. |

## PDF diagnostics

To see what the script actually reads from the PDFs (detected grid, text of
each cell) and how it classifies matches, e.g. if the PDF layout ever changes:

- GitHub: "Actions" → "Bethesda Menu Check" → "Run workflow" → tick "PDF
  diagnostics only". The output is in the run log.
- Locally: `python menu_check.py --dump-pdf` (PDFs from the page) or
  `python menu_check.py --dump-pdf "Mittag&Abend KW38.pdf"` (local file).
  Local OCR requires `tesseract-ocr` plus the language pack.

## Customizing the target dishes (now and in the future)

By default (in the published code), the script only looks for Cordon Bleu.
This can be changed anytime **without touching the code** - just set a
`KEYWORDS` secret (or repository variable, see note below) with a
comma-separated list:

```
Cordon Bleu, Fleischkäse, Leberkäse, Wienerschnitzel, Zürcher Geschnetzeltes
```

**Important - `KEYWORDS` overrides, it doesn't merge:** if the secret is
set, **only** the list in it is used - the code default is fully ignored.
So if you want to keep getting notified about Cordon Bleu *and* add
Fleischkäse/Leberkäse, you must put **all three together** in the secret,
not just the new terms. Setting `KEYWORDS="Schnitzel"` means **only**
Schnitzel is searched for - Cordon Bleu drops out entirely unless it's
also listed in the secret.

The script is fairly tolerant of spelling:
- **Umlauts:** `ä`/`ö`/`ü`/`ß` automatically also match the spelled-out
  variant (`Käse` also matches `Kaese`).
- **Multiple words:** a space in the search term (e.g. `Cordon Bleu`) also
  matches the word written together or hyphenated (`CordonBleu`,
  `Cordon-Bleu`). This applies to custom terms too, e.g. `Wiener Schnitzel`
  also matches `Wienerschnitzel`.
- **Case** doesn't matter.

If `KEYWORDS` isn't set, the code default (Cordon Bleu) applies
automatically - see `DEFAULT_KEYWORDS` in `menu_check.py`.

*Note:* since the dish list isn't sensitive information, you can maintain
it more conveniently as a **repository variable** instead of a secret
(`Settings → Secrets and variables → Actions → Variables → New repository
variable`, name `KEYWORDS`) - the workflow would then need to reference
`${{ vars.KEYWORDS }}` instead of `${{ secrets.KEYWORDS }}` (one line in
`check-menu.yml`).

## License

This project is licensed under the **GNU General Public License v3.0 or
later** (GPL-3.0-or-later). A full copy of the license text should be
placed as a `LICENSE` file in the repo root (see
[gnu.org/licenses](https://www.gnu.org/licenses/)).

Summary: you may freely use, modify, and redistribute this program.
Derivative works must also be released under a GPL(-compatible) license,
with changes marked. There is no warranty of any kind. See the license
text for details.
