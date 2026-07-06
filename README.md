# Bethesda Mittagsmenü-Checker

Prüft wöchentlich (Montagmorgen) die Mittagsmenü-Seite des Bethesda Spitals auf
Fleischkäse, Leberkäse oder Cordon Bleu **im Mittagsmenü** an einem **Montag**
und schickt bei Treffer eine Push-Benachrichtigung aufs Handy.

## Warum GitHub Actions?

Kein eigener Server/Raspberry nötig. GitHub Actions bietet kostenlose,
zeitgesteuerte ("Cron") Jobs in der Cloud – der Job läuft automatisch jeden
Montagmorgen, ganz ohne dass du etwas anklicken musst. Läuft der Job einmal,
läuft er quasi für immer weiter (auch monatelang), solange das Repo existiert.

## Setup (einmalig, ca. 10 Minuten)

1. **Neues GitHub-Repo anlegen** (privat oder öffentlich, spielt keine Rolle)
   und diesen Ordner hochladen/pushen.

2. **Benachrichtigungskanal(e) einrichten.** Beide Kanäle sind komplett
   unabhängig voneinander. Du kannst nur ntfy, nur E-Mail, beide parallel,
   oder (zum Testen) auch keinen einrichten - dann erscheint der Treffer nur
   im Actions-Log. Secrets, die du nicht setzt, deaktivieren einfach den
   jeweiligen Kanal, es passiert nichts Falsches.

   **Option A - ntfy.sh (Push, kein Account nötig):**
   - App installieren: [ntfy für Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy)
     oder [ntfy für iOS](https://apps.apple.com/us/app/ntfy/id1625396347).
   - In der App ein "Topic" abonnieren – frei wählbarer, am besten schwer
     erratbarer Name, z.B. `edmund-bethesda-menu-8f3k2`. Jeder, der den
     Topic-Namen kennt, kann sonst mitlesen (es ist kein Login-System,
     sondern eine Art öffentlicher Kanalname).
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
     Einfach den Secret-Wert entsprechend anpassen (kein Code-Änderung nötig).

     Andere Anbieter (z.B. Bluewin, GMX, eigener Mailserver) funktionieren
     genauso - einfach `SMTP_HOST`/`SMTP_PORT` entsprechend anpassen.

   **Beide Optionen parallel:** einfach beide Secret-Sets gleichzeitig
   hinterlegen - `menu_check.py` schickt dann bei einem Treffer sowohl eine
   ntfy-Push-Nachricht als auch eine E-Mail. Du kannst das Set jederzeit
   ändern (Secrets hinzufügen/löschen), ohne den Code anzufassen.

3. **Actions aktivieren**: Im Repo unter dem Reiter "Actions" bestätigen,
   dass Workflows laufen dürfen (bei neu erstellten Repos meist schon aktiv).

4. **Fertig.** Der Workflow läuft automatisch jeden Montag um 05:30 UTC
   (≈ 6:30–7:30 Schweizer Zeit, je nach Sommer-/Winterzeit).

## Benachrichtigung testen, ohne auf Cordon Bleu zu warten

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
python menu_check.py --test
# oder gleichwertig:
TEST_NOTIFICATION=1 python menu_check.py
```

Falls kein Kanal konfiguriert ist, meldet das Skript das klar und bricht ab,
statt stillschweigend nichts zu tun.

## Manuell testen (echter Menü-Check)

Im Repo unter "Actions" → "Bethesda Menu Check" → "Run workflow" klicken,
um den Job sofort einmal auszulösen (unabhängig vom Zeitplan) – so kannst du
das Setup testen, ohne auf den nächsten Montag zu warten.

## Wie funktioniert die Erkennung?

- `menu_check.py` lädt die Menü-Seite und trennt sie in Mittags- und
  Abendmenü-Abschnitte (Abendmenü wird komplett ignoriert).
- Innerhalb des Mittagsmenü-Abschnitts wird nur der Montag-Block geprüft.
- Gesucht wird per Regex nach Schreibvarianten von "Fleischkäse",
  "Leberkäse" und "Cordon Bleu" (inkl. Bindestrich-Varianten, Gross-/
  Kleinschreibung etc.).
- Bereits gemeldete Termine werden in `notified_dates.json` gespeichert,
  damit du nicht jede Woche erneut für denselben Montag benachrichtigt wirst,
  falls dieser Termin mehrfach auf der Seite erscheint (die Seite zeigt
  mehrere Wochen im Voraus).

## Gesuchte Gerichte anpassen (auch in Zukunft)

Standardmässig wird nach Fleischkäse, Leberkäse und Cordon Bleu gesucht.
Das lässt sich jederzeit ändern, **ohne den Code anzufassen** - einfach ein
Secret `KEYWORDS` (oder eine Repository Variable, siehe Hinweis unten)
mit einer kommagetrennten Liste hinterlegen:

```
Fleischkäse, Leberkäse, Cordon Bleu, Wienerschnitzel, Zürcher Geschnetzeltes
```

Das Skript ist bei der Schreibweise recht tolerant:
- **Umlaute:** `ä`/`ö`/`ü`/`ß` matchen automatisch auch die ausgeschriebene
  Variante (`Käse` matcht auch `Kaese`).
- **Mehrere Wörter:** ein Leerzeichen im Suchbegriff (z.B. `Cordon Bleu`)
  matcht automatisch auch zusammengeschrieben oder mit Bindestrich
  (`CordonBleu`, `Cordon-Bleu`). Das gilt auch für eigene Begriffe wie
  `Wiener Schnitzel` → matcht auch `Wienerschnitzel`.
- **Gross-/Kleinschreibung** spielt keine Rolle.

Wenn `KEYWORDS` nicht gesetzt ist, gilt automatisch die ursprüngliche
Dreier-Liste (Fleischkäse/Leberkäse/Cordon Bleu) als Default - du kannst
also jederzeit ohne Risiko `KEYWORDS` hinzufügen, ändern oder wieder löschen.

*Hinweis:* Da die Gerichte-Liste keine sensible Information ist, kannst du
sie statt als Secret auch bequemer einsehbar als
**Repository Variable** pflegen (`Settings → Secrets and variables →
Actions → Variables → New repository variable`, Name `KEYWORDS`) - der
Workflow müsste dann `${{ vars.KEYWORDS }}` statt `${{ secrets.KEYWORDS }}`
referenzieren (eine Zeile in `check-menu.yml`).



```bash
pip install -r requirements.txt

# nur ntfy:
NTFY_TOPIC=dein-topic-name python menu_check.py

# nur E-Mail:
SMTP_HOST=smtp.gmail.com SMTP_USER=me@gmail.com SMTP_PASSWORD=app-passwort \
  EMAIL_TO=me@gmail.com python menu_check.py

# beide gleichzeitig: einfach alle Variablen zusammen setzen
```

Zum Testen der Erkennung selbst (unabhängig von echten Treffern auf der
Seite) kannst du testweise einen bereits gemeldeten Eintrag aus
`notified_dates.json` löschen und den Lauf wiederholen, falls gerade ein
Treffer auf der Seite steht - oder einfach eine Weile warten, bis ein
Montag mit passendem Gericht erscheint.
