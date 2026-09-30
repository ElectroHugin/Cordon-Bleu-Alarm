# Cordon-Bleu-Alarm

Meldet per ntfy und E-Mail, wenn im Bethesda Spital Cordon-Bleu-Woche ist.
Privates Büro-Projekt, keine Verbindung zum Bethesda Spital.

## So funktioniert's

Auf der [Menüseite](https://www.bethesda-spital.ch/de/aufenthalt-und-besuch/restaurant/menu.html)
hängen zwei PDFs: aktuelle und kommende Woche. Das Skript lädt beide, liest
sie per OCR und schaut, ob irgendwo "Cordon Bleu" steht.

In der Cordon-Bleu-Woche heisst die erste Spalte `Mittags. Cordonbleu`
(sonst `Mittags. Pastateller`). Die Tagesgerichte heissen dann nur
«Eidgenoss», «Uri» usw. Steht Cordon Bleu in der Spaltenüberschrift, gibt's
eine Meldung "Cordonbleu-Woche". Steht es nur bei einem einzelnen Tag, gibt's
eine Meldung für diesen Tag.

Läuft per GitHub Actions jeden **Mittwoch und Donnerstag** früh. Donnerstag
ist nur Reserve. Was schon gemeldet wurde, steht in `notified_dates.json`,
also kommt jede Woche nur eine Meldung.

## Secrets

`Settings → Secrets and variables → Actions`

| Secret | |
|---|---|
| `NTFY_TOPIC` | ntfy-Topic |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` | Mailversand (z.B. Gmail mit App-Passwort, Port 587) |
| `EMAIL_TO` | Verteiler, mit Komma getrennt |
| `EMAIL_FROM` | optional, sonst `SMTP_USER` |
| `EMAIL_TO_DEBUG` | meine Adresse für Tests |
| `NTFY_TOPIC_DEBUG` | optional, sonst `NTFY_TOPIC` |
| `KEYWORDS` | optional, sonst `Cordon Bleu, Kordon Bleu` |

Optional als Variablen: `EMAIL_SUBJECT` und `EMAIL_BODY` (eigener Mailtext
mit Platzhaltern wie `{titel}`, `{woche}`, `{quell_url}`, siehe
`template_values()` im Code) sowie `TAGE` (nur bestimmte Wochentage melden).

## Manuell starten

Actions → Bethesda Menu Check → Run workflow → modus:

| modus | an wen |
|---|---|
| `trockenlauf` | echter Check, Meldung nur an mich, merkt sich nichts |
| `test-ntfy` / `test-email` / `test-beide` | Testnachricht nur an mich |
| `test-alle` | Testmail an den ganzen Verteiler |
| `dump-pdf` | nur Log: was aus den PDFs gelesen wurde |
| `check` | normaler Lauf, geht an alle |

Bei `trockenlauf` und `dump-pdf` kann man unter `pdf_url` auch ein
bestimmtes PDF angeben, z.B. ein altes aus einer Cordon-Bleu-Woche.

Wenn etwas kaputt ist (keine PDFs gefunden, OCR liest nichts), kommt einmal
pro Woche eine Meldung an mich.

## Lokal

Braucht Tesseract mit deutschem Sprachpaket.

```bash
pip install -r requirements.txt
python menu_check.py --trockenlauf "Mittag&Abend KW38.pdf"
python menu_check.py --dump-pdf
python menu_check.py --test ntfy
```

## Lizenz

GPL-3.0-or-later, siehe `LICENSE`.
