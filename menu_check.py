#!/usr/bin/env python3
"""
Bethesda Spital Mittagsmenü-Checker.

Prüft die Mittagsmenü-Seite auf Montage mit Fleischkäse / Leberkäse / Cordon Bleu
(in diversen Schreibweisen) und schickt bei Treffer eine Benachrichtigung.

Zwei Benachrichtigungskanäle, unabhängig voneinander aktivierbar (beide können
parallel laufen, wird jeweils nur genutzt wenn die zugehörigen Umgebungs-
variablen/Secrets gesetzt sind):
  - ntfy.sh Push-Nachricht  (NTFY_TOPIC)
  - E-Mail via SMTP         (SMTP_HOST, SMTP_USER, SMTP_PASSWORD, EMAIL_TO)

Bereits gemeldete Termine werden in notified_dates.json gemerkt, damit nicht
jede Woche erneut für denselben Montag benachrichtigt wird.
"""
import json
import os
import re
import smtplib
import sys
from email.mime.text import MIMEText
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://www.bethesda-spital.ch/de/aufenthalt-und-besuch/restaurant/menu.html"
STATE_FILE = Path(__file__).parent / "notified_dates.json"

# --- ntfy.sh (Push) ---------------------------------------------------------
# Leer/nicht gesetzt = Kanal deaktiviert. Siehe README für Setup.
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip()

# --- E-Mail (SMTP) -----------------------------------------------------------
# Alle Werte ausser EMAIL_FROM nötig, sonst ist der Kanal deaktiviert. Siehe
# README für Setup mit z.B. einem Gmail-App-Passwort.
SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "").strip()
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "").strip()
# Mehrere Empfänger: einfach mit Komma oder Semikolon trennen, z.B.
# "ich@example.com, partner@example.com"
EMAIL_TO = [
    addr.strip()
    for addr in re.split(r"[,;]", os.environ.get("EMAIL_TO", ""))
    if addr.strip()
]
EMAIL_FROM = os.environ.get("EMAIL_FROM", "").strip() or SMTP_USER

EMAIL_ENABLED = bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD and EMAIL_TO)
NTFY_ENABLED = bool(NTFY_TOPIC)

WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

# --- Gerichte-Stichwörter ----------------------------------------------------
# Konfigurierbar über die Umgebungsvariable KEYWORDS (kommagetrennt), ohne
# Codeänderung. Beispiel: KEYWORDS="Fleischkäse, Leberkäse, Cordon Bleu, Wienerschnitzel"
# Fällt auf die drei ursprünglichen Gerichte zurück, wenn nicht gesetzt.
DEFAULT_KEYWORDS = "Fleischkäse, Leberkäse, Cordon Bleu, Kordon Bleu"

UMLAUT_ALTERNATIVES = {
    "ä": "(?:ä|ae)",
    "ö": "(?:ö|oe)",
    "ü": "(?:ü|ue)",
    "ß": "(?:ß|ss)",
    "é": "(?:é|e)",
}


def build_keyword_regex(raw_term: str) -> str:
    """Baut aus einem einfachen Suchbegriff ein tolerantes Regex-Fragment:
    - Umlaute/Akzente erlauben zusätzlich die ausgeschriebene Variante (ä -> ä|ae)
    - mehrere Wörter dürfen mit/ohne Leerzeichen oder Bindestrich verbunden sein
      (z.B. "Cordon Bleu" matcht auch "Cordon-Bleu" und "Cordonbleu")
    """
    words = raw_term.strip().split()
    word_patterns = []
    for word in words:
        chars = []
        for ch in word:
            lower = ch.lower()
            if lower in UMLAUT_ALTERNATIVES:
                chars.append(UMLAUT_ALTERNATIVES[lower])
            else:
                chars.append(re.escape(ch))
        word_patterns.append("".join(chars))
    return r"\s*-?\s*".join(word_patterns)


def load_keywords() -> re.Pattern:
    raw = os.environ.get("KEYWORDS", "").strip() or DEFAULT_KEYWORDS
    terms = [t.strip() for t in raw.split(",") if t.strip()]
    patterns = [build_keyword_regex(t) for t in terms]
    return re.compile("|".join(patterns), re.IGNORECASE), terms


KEYWORD_RE, ACTIVE_KEYWORDS = load_keywords()

SECTION_RE = re.compile(r"@@H2@@\s*(Mittagsmen[üu]|Abendmen[üu])")
DAY_RE = re.compile(r"@@H3@@\s*(" + "|".join(WEEKDAYS) + r"),\s*(\d{2})\.(\d{2})\.(\d{4})")


def fetch_html() -> str:
    resp = requests.get(URL, timeout=30, headers={"User-Agent": "Mozilla/5.0 (menu-checker)"})
    resp.raise_for_status()
    return resp.text


def extract_marked_text(html: str) -> str:
    """Insert @@H2@@ / @@H3@@ markers in front of heading text, then flatten to plain text."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["h2", "h3"]):
        marker = "@@H2@@ " if tag.name == "h2" else "@@H3@@ "
        tag.insert(0, marker)
    return soup.get_text("\n")


def find_matching_mondays(marked_text: str):
    section_markers = list(SECTION_RE.finditer(marked_text))
    hits = []
    for i, marker in enumerate(section_markers):
        section_name = marker.group(1)
        start = marker.end()
        end = section_markers[i + 1].start() if i + 1 < len(section_markers) else len(marked_text)
        if not section_name.lower().startswith("mittagsmen"):
            continue  # nur Mittagsmenü, Abendmenü wird ignoriert

        section_text = marked_text[start:end]
        day_markers = list(DAY_RE.finditer(section_text))
        for j, dm in enumerate(day_markers):
            weekday, dd, mm, yyyy = dm.groups()
            if weekday != "Montag":
                continue
            dstart = dm.end()
            dend = day_markers[j + 1].start() if j + 1 < len(day_markers) else len(section_text)
            day_text = section_text[dstart:dend]
            if KEYWORD_RE.search(day_text):
                date_iso = f"{yyyy}-{mm}-{dd}"
                snippet = re.sub(r"\s+", " ", day_text).strip()[:300]
                hits.append((date_iso, snippet))
    return hits


def load_notified() -> set:
    if STATE_FILE.exists():
        return set(json.loads(STATE_FILE.read_text()))
    return set()


def save_notified(dates: set):
    STATE_FILE.write_text(json.dumps(sorted(dates), ensure_ascii=False, indent=2))


def send_ntfy(title: str, message: str, date_iso: str):
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={
                "Title": title.encode("utf-8"),
                "Priority": "high",
                "Tags": "fork_and_knife",
            },
            timeout=15,
        )
        print(f"[ntfy] Notification sent for {date_iso}")
    except requests.RequestException as exc:
        print(f"[ntfy] Fehler beim Senden: {exc}", file=sys.stderr)


def send_email(title: str, message: str, date_iso: str):
    msg = MIMEText(message, "plain", "utf-8")
    msg["Subject"] = title
    msg["From"] = EMAIL_FROM
    msg["To"] = ", ".join(EMAIL_TO)
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        print(f"[email] Notification sent for {date_iso} an {len(EMAIL_TO)} Empfänger")
    except (smtplib.SMTPException, OSError) as exc:
        print(f"[email] Fehler beim Senden: {exc}", file=sys.stderr)


def notify_all(date_iso: str, snippet: str):
    """Schickt die Benachrichtigung über alle aktivierten Kanäle (0, 1 oder 2)."""
    title = f"Cordon Bleu Alarm! Montag {date_iso}"
    message = f"Mittagsmenü am Montag, {date_iso}:\n{snippet}\n\n{URL}"
    dispatch_notification(title, message, date_iso)


def dispatch_notification(title: str, message: str, date_iso: str):
    if not NTFY_ENABLED and not EMAIL_ENABLED:
        print(
            "[warnung] Kein Benachrichtigungskanal konfiguriert (weder NTFY_TOPIC "
            "noch vollständige SMTP_*/EMAIL_TO Variablen gesetzt) - Treffer wird "
            "nur ins Log geschrieben.",
            file=sys.stderr,
        )

    if NTFY_ENABLED:
        send_ntfy(title, message, date_iso)
    if EMAIL_ENABLED:
        send_email(title, message, date_iso)


def run_test_notification():
    """Schickt eine klar als Test gekennzeichnete Benachrichtigung über alle
    aktivierten Kanäle - unabhängig davon, ob gerade ein echter Treffer auf
    der Seite steht. Verändert notified_dates.json nicht."""
    print(f"Test-Modus: aktive Keywords wären {', '.join(ACTIVE_KEYWORDS)}")
    print(f"ntfy aktiv: {NTFY_ENABLED} | E-Mail aktiv: {EMAIL_ENABLED} ({len(EMAIL_TO)} Empfänger)")

    if not NTFY_ENABLED and not EMAIL_ENABLED:
        print(
            "Kein Kanal konfiguriert - es gibt nichts zu testen. Bitte "
            "NTFY_TOPIC und/oder SMTP_*/EMAIL_TO setzen.",
            file=sys.stderr,
        )
        sys.exit(1)

    title = "Testbenachrichtigung Bethesda Menu Checker"
    message = (
        "Das ist eine Testbenachrichtigung - es wurde kein echtes Menü geprüft.\n"
        f"Konfigurierte Gerichte: {', '.join(ACTIVE_KEYWORDS)}\n\n"
        "Wenn du das hier liest, funktioniert der Kanal wie er soll."
    )
    dispatch_notification(title, message, "TEST")
    print("Test abgeschlossen.")


def main():
    if "--test" in sys.argv or os.environ.get("TEST_NOTIFICATION") == "1":
        run_test_notification()
        return

    print(f"Suche nach: {', '.join(ACTIVE_KEYWORDS)}")
    html = fetch_html()
    marked_text = extract_marked_text(html)
    hits = find_matching_mondays(marked_text)

    notified = load_notified()
    new_hits = [(d, s) for d, s in hits if d not in notified]

    if not new_hits:
        print(f"Keine neuen Treffer. ({len(hits)} insgesamt auf der Seite, bereits gemeldet: {len(notified)})")
        return

    for date_iso, snippet in new_hits:
        notify_all(date_iso, snippet)
        notified.add(date_iso)

    save_notified(notified)


if __name__ == "__main__":
    main()
