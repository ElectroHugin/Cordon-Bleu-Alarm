# Bethesda Mittagsmenü-Checker

**⚠️ Inoffizielles Community-Projekt.** Dieses Tool steht in keiner
Verbindung zum Bethesda Spital Basel und wird nicht von ihm betrieben,
gesponsert oder unterstützt. Es liest lediglich die öffentlich einsehbare
Menü-Seite aus. Alle Rechte an Name, Logo und Inhalten der Speisekarte
liegen beim Bethesda Spital. Nutzung auf eigenes Risiko, siehe auch
[Lizenz](#lizenz--license) und Haftungsausschluss unten.

Prüft wöchentlich (Montagmorgen) automatisiert die Mittagsmenü-Seite des
Bethesda Spitals auf frei konfigurierbare Gerichte (Standard: Fleischkäse,
Leberkäse, Cordon Bleu) **im Mittagsmenü** an einem **Montag** und schickt
bei Treffer eine Benachrichtigung per Push (ntfy.sh) und/oder E-Mail.

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
   (≈ 6:30–7:30 Schweizer Zeit, je nach Sommer-/Winterzeit).

## Benachrichtigung testen, ohne auf ein Treffer-Gericht zu warten

Es kann Monate dauern, bis ein passendes Gericht an einem Montag auf der
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
echtem Menü-Inhalt. `notified_dates.json` wird dabei nicht verändert.

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

- `menu_check.py` lädt die Menü-Seite und trennt sie in Mittags- und
  Abendmenü-Abschnitte (Abendmenü wird komplett ignoriert).
- Innerhalb des Mittagsmenü-Abschnitts wird nur der Montag-Block geprüft.
- Gesucht wird per Regex nach Schreibvarianten der konfigurierten Gerichte
  (inkl. Umlaut-, Bindestrich- und Gross-/Kleinschreibungs-Varianten).
- Bereits gemeldete Termine werden in `notified_dates.json` gespeichert,
  damit du nicht jede Woche erneut für denselben Montag benachrichtigt wirst,
  falls dieser Termin mehrfach auf der Seite erscheint (die Seite zeigt
  mehrere Wochen im Voraus).

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

Automatically checks the Bethesda Spital lunch menu page every Monday
morning for freely configurable dishes (default: Fleischkäse, Leberkäse,
Cordon Bleu) **in the lunch menu** on a **Monday**, and sends a
notification via push (ntfy.sh) and/or email on a match.

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
   (≈ 6:30-7:30 Swiss time, depending on daylight saving).

## Testing notifications without waiting for a matching dish

It can take months before a matching dish shows up on a Monday. To test
the configured channels (ntfy and/or email) independently of that:

**Via the GitHub web UI (recommended):**
1. Go to the "Actions" tab in the repo.
2. Select "Bethesda Menu Check" → "Run workflow".
3. Enable the "Send test notification only" checkbox → "Run workflow".
4. Within ~10-20 seconds you should receive a clearly marked test message
   on all configured channels.

This validates the real credentials (SMTP login, ntfy topic) using the
exact same code path as a real match - just with test text instead of
actual menu content. `notified_dates.json` is not modified.

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

- `menu_check.py` loads the menu page and splits it into lunch and dinner
  sections (dinner is fully ignored).
- Within the lunch section, only the Monday block is checked.
- Matching is done via regex against spelling variants of the configured
  dishes (including umlaut, hyphen, and case variants).
- Already-notified dates are stored in `notified_dates.json` so you don't
  get repeated notifications for the same Monday if it appears on the page
  across multiple weekly runs (the site shows several weeks ahead).

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
