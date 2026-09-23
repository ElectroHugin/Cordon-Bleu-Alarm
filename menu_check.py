#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Bethesda Mittagsmenü-Checker
# Copyright (C) 2026 Edmund Jochim
#
# Dieses Programm ist freie Software: Sie können es unter den Bedingungen
# der GNU General Public License, wie von der Free Software Foundation
# veröffentlicht, weitergeben und/oder modifizieren, entweder gemäss
# Version 3 der Lizenz oder (nach Ihrer Wahl) jeder späteren Version.
#
# Die Veröffentlichung dieses Programms erfolgt in der Hoffnung, dass es
# Ihnen von Nutzen sein wird, aber OHNE JEDE GEWÄHRLEISTUNG - sogar ohne
# die implizite Gewährleistung der MARKTFÄHIGKEIT oder EIGNUNG FÜR EINEN
# BESTIMMTEN ZWECK. Details finden Sie in der GNU General Public License.
#
# Sie sollten eine Kopie der GNU General Public License zusammen mit
# diesem Programm erhalten haben. Falls nicht, siehe
# <https://www.gnu.org/licenses/>.
"""
Bethesda Spital Mittagsmenü-Checker.

Prüft zwei Quellen auf gesuchte Gerichte (Standard: Cordon Bleu) im Mittagsmenü:
  1. die Menü-Seite (HTML), Einzeltage
  2. die beiden Wochen-PDFs "Mittag&Abend KW##.pdf" (aktuelle + kommende Woche), die auf
     der Menü-Seite verlinkt sind. Das PDF ist eine Tabelle (Spalten = Menülinien, Zeilen =
     Montag..Sonntag). Steht das Stichwort in einer SPALTENÜBERSCHRIFT (z.B. "Mittags.
     Cordonbleu"), gibt es die Menülinie die GANZE WOCHE ("Cordonbleu-Woche"); steht es in
     der Zelle eines Tages, gilt es nur für diesen EINZELNEN TAG.
     Die PDFs enthalten keinen echten Text (keine Textebene), die Tabellenlinien aber sind
     Vektoren: daraus wird das Raster gelesen und jede Zelle per OCR (Tesseract) gelesen.

Zwei Benachrichtigungskanäle, unabhängig voneinander aktivierbar (beide können
parallel laufen, wird jeweils nur genutzt wenn die zugehörigen Umgebungs-
variablen/Secrets gesetzt sind):
  - ntfy.sh Push-Nachricht  (NTFY_TOPIC)
  - E-Mail via SMTP         (SMTP_HOST, SMTP_USER, SMTP_PASSWORD, EMAIL_TO)
    Betreff und Text der E-Mail sind über EMAIL_SUBJECT / EMAIL_BODY anpassbar.

Bereits gemeldete Treffer werden in notified_dates.json gemerkt, damit nicht
mehrfach für dasselbe benachrichtigt wird (Einzeltag: ISO-Datum, ganze Woche:
"woche:JJJJ-Wnn").

Aufrufe:
  python menu_check.py                    normaler Check
  python menu_check.py --test             Test-Benachrichtigung (Beispieltreffer)
  python menu_check.py --dump-pdf [DATEI] zeigt, was aus den PDFs gelesen wird
"""
from __future__ import annotations

import io
import json
import os
import re
import smtplib
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from email.header import Header
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urljoin

import requests
from bs4 import BeautifulSoup

URL = "https://www.bethesda-spital.ch/de/aufenthalt-und-besuch/restaurant/menu.html"
STATE_FILE = Path(__file__).parent / "notified_dates.json"
USER_AGENT = {"User-Agent": "Mozilla/5.0 (menu-checker)"}

# --- ntfy.sh (Push) ---------------------------------------------------------
# Leer/nicht gesetzt = Kanal deaktiviert. Siehe README für Setup.
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip()

# --- E-Mail (SMTP) -----------------------------------------------------------
# Alle Werte ausser EMAIL_FROM nötig, sonst ist der Kanal deaktiviert. Siehe
# README für Setup mit z.B. einem Gmail-App-Passwort.
SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
SMTP_PORT = int(os.environ.get("SMTP_PORT", "").strip() or "587")
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

# --- E-Mail-Text anpassen ----------------------------------------------------
# Leer = Standardvorlage (unten). Platzhalter siehe README bzw. template_values().
# "\n" darf als Zeilenumbruch geschrieben werden (praktisch für einzeilige Variablen).
EMAIL_SUBJECT_TEMPLATE = os.environ.get("EMAIL_SUBJECT", "").strip()
EMAIL_BODY_TEMPLATE = os.environ.get("EMAIL_BODY", "").strip()

DEFAULT_SUBJECT = "Menü-Treffer: {titel}"
DEFAULT_BODY = (
    "{titel}\n"
    "\n"
    "Woche:   {woche}\n"
    "Quelle:  {quelle}\n"
    "\n"
    "{details}\n"
    "\n"
    "{hinweis}\n"
    "\n"
    "Direktlink: {quell_url}\n"
    "Menüseite:  {url}\n"
)

# --- PDF-Prüfung -------------------------------------------------------------
# PDF_CHECK=0 schaltet die PDF-Prüfung ab; PDF_OCR=never verbietet den OCR-Fallback.
PDF_CHECK = os.environ.get("PDF_CHECK", "1").strip().lower() not in ("0", "false", "nein", "off")
PDF_OCR = os.environ.get("PDF_OCR", "auto").strip().lower()  # auto | never
OCR_LANG = os.environ.get("OCR_LANG", "").strip() or "deu"

WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


def load_days() -> set:
    """Wochentage, für die Einzeltag-Treffer gemeldet werden (Umgebungsvariable TAGE).
    Standard: alle Tage. Einschränken z.B. mit TAGE="Montag, Freitag".
    Ganze-Woche-Treffer werden immer gemeldet."""
    raw = os.environ.get("TAGE", "").strip() or "alle"
    if raw.lower() in ("alle", "all", "*"):
        return set(WEEKDAYS)
    days = set()
    for token in re.split(r"[,;]", raw):
        token = token.strip().lower()
        if len(token) < 2:
            continue
        days.update(wd for wd in WEEKDAYS if wd.lower().startswith(token[:2]))
    return days or set(WEEKDAYS)


ACTIVE_DAYS = load_days()

# --- Gerichte-Stichwörter ----------------------------------------------------
# Konfigurierbar über die Umgebungsvariable KEYWORDS (kommagetrennt) - siehe
# README, Abschnitt "Gesuchte Gerichte anpassen". WICHTIG: KEYWORDS ersetzt
# diesen Default vollständig, es wird NICHT ergänzt/zusammengeführt. Wer also
# z.B. zusätzlich zu Cordon Bleu auch Fleischkäse/Leberkäse melden will, muss
# ALLE gewünschten Begriffe zusammen ins Secret schreiben, z.B.:
#   KEYWORDS="Cordon Bleu, Fleischkäse, Leberkäse"
DEFAULT_KEYWORDS = "Cordon Bleu, Kordon Bleu"

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


def load_keywords():
    raw = os.environ.get("KEYWORDS", "").strip() or DEFAULT_KEYWORDS
    terms = [t.strip() for t in raw.split(",") if t.strip()]
    patterns = [build_keyword_regex(t) for t in terms]
    return re.compile("|".join(patterns), re.IGNORECASE), terms


KEYWORD_RE, ACTIVE_KEYWORDS = load_keywords()

SECTION_RE = re.compile(r"@@H2@@\s*(Mittagsmen[üu]|Abendmen[üu])")
DAY_RE = re.compile(r"@@H3@@\s*(" + "|".join(WEEKDAYS) + r"),\s*(\d{2})\.(\d{2})\.(\d{4})")


# =============================================================================
# Hilfsfunktionen
# =============================================================================
def warn(msg: str):
    """Warnung; in GitHub Actions als Annotation sichtbar (gelbes Dreieck im Lauf)."""
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::warning::{msg}")
    else:
        print(f"[warnung] {msg}", file=sys.stderr)


def today_ch() -> date:
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("Europe/Zurich")).date()
    except Exception:  # noqa: BLE001 - z.B. fehlende tzdata auf Windows
        return date.today()


def resolve_iso_year(kw: int, today: date) -> Optional[int]:
    """Der Dateiname enthält nur die KW, kein Jahr: nimm das ISO-Jahr, dessen
    Woche 'kw' am nächsten an heute liegt (funktioniert auch um den Jahreswechsel)."""
    best = None
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            monday = date.fromisocalendar(year, kw, 1)
        except ValueError:
            continue
        dist = abs((monday - today).days)
        if best is None or dist < best[0]:
            best = (dist, year)
    return best[1] if best else None


def fmt_date(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def week_label(iso_year: int, iso_week: int, today: date) -> str:
    monday = date.fromisocalendar(iso_year, iso_week, 1)
    sunday = monday + timedelta(days=6)
    this_monday = today - timedelta(days=today.weekday())
    rel = {0: "aktuelle Woche", 1: "kommende Woche"}.get((monday - this_monday).days // 7, "")
    rng = f"{monday:%d.%m.}-{sunday:%d.%m.%Y}"
    return f"KW {iso_week} ({rel + ', ' if rel else ''}{rng})"


# =============================================================================
# Treffer-Datenmodell
# =============================================================================
@dataclass
class Finding:
    scope: str  # "woche" (ganze Woche) | "tag" (Einzeltag) | "unklar" (nur PDF)
    quelle: str  # z.B. "Webseite (Mittagsmenü)" oder "PDF Menü der kommenden Woche"
    quell_url: str
    gericht: str  # Zeile, in der das Stichwort gefunden wurde
    beschreibung: str  # Gericht inkl. Folgezeilen (Beilagen etc.)
    iso_year: int
    iso_week: int
    day: Optional[date] = None
    weekday: str = ""

    @property
    def week_key(self) -> str:
        return f"{self.iso_year}-W{self.iso_week:02d}"

    @property
    def key(self) -> str:
        """Schlüssel für notified_dates.json. Einzeltage = ISO-Datum (kompatibel
        zum bisherigen Format), Wochen/Unklar mit Präfix."""
        if self.scope == "tag" and self.day:
            return self.day.isoformat()
        return f"{self.scope}:{self.week_key}"


# =============================================================================
# Quelle 1: Webseite (HTML)
# =============================================================================
def fetch_html() -> str:
    resp = requests.get(URL, timeout=30, headers=USER_AGENT)
    resp.raise_for_status()
    return resp.text


def extract_marked_text(html: str) -> str:
    """Insert @@H2@@ / @@H3@@ markers in front of heading text, then flatten to plain text."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["h2", "h3"]):
        marker = "@@H2@@ " if tag.name == "h2" else "@@H3@@ "
        tag.insert(0, marker)
    return soup.get_text("\n")


def describe_web_match(lines: list, idx: int) -> str:
    """Trefferzeile + Folgezeilen bis zum Preis / nächsten Menü-Label (max. 5 Zeilen),
    davor das Menü-Label ('Mittags. Vital' / 'Mittags. Vegi'), falls vorhanden."""
    label = ""
    for j in range(idx - 1, -1, -1):
        if re.match(r"(Mittags|Abend)\.", lines[j]):
            label = lines[j]
            break
    parts = [lines[idx]]
    for ln in lines[idx + 1 : idx + 6]:
        if ln.startswith("CHF") or re.match(r"(Mittags|Abend)\.", ln):
            break
        parts.append(ln)
    text = " / ".join(parts)
    return f"{label}: {text}" if label else text


def find_web_findings(marked_text: str) -> list:
    section_markers = list(SECTION_RE.finditer(marked_text))
    findings = []
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
            if weekday not in ACTIVE_DAYS:
                continue
            dstart = dm.end()
            dend = day_markers[j + 1].start() if j + 1 < len(day_markers) else len(section_text)
            day_text = section_text[dstart:dend]
            m = KEYWORD_RE.search(day_text)
            if not m:
                continue

            lines = [ln.strip() for ln in day_text.splitlines() if ln.strip()]
            idx = next((k for k, ln in enumerate(lines) if KEYWORD_RE.search(ln)), None)
            if idx is None:  # Stichwort über einen Zeilenumbruch hinweg
                gericht = re.sub(r"\s+", " ", m.group(0)).strip()
                beschreibung = re.sub(r"\s+", " ", day_text).strip()[:300]
            else:
                gericht = lines[idx]
                beschreibung = describe_web_match(lines, idx)[:300]

            d = date(int(yyyy), int(mm), int(dd))
            iso = d.isocalendar()
            findings.append(
                Finding(
                    scope="tag",
                    quelle="Webseite (Mittagsmenü)",
                    quell_url=URL,
                    gericht=gericht,
                    beschreibung=beschreibung,
                    iso_year=iso[0],
                    iso_week=iso[1],
                    day=d,
                    weekday=weekday,
                )
            )
    return findings


# =============================================================================
# Quelle 2: Wochen-PDFs
# =============================================================================
@dataclass
class PdfLink:
    url: str
    kw: int
    text: str


def find_pdf_links(html: str) -> list:
    """Alle auf der Seite verlinkten PDFs mit 'KW##' im Namen (aktuelle + kommende Woche).
    Die Links ändern sich jede Woche, daher wird immer die Seite ausgewertet."""
    soup = BeautifulSoup(html, "html.parser")
    links, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = urljoin(URL, a["href"].strip())
        decoded = unquote(href.split("?")[0])
        if not decoded.lower().endswith(".pdf"):
            continue
        m = re.search(r"KW\s*0?(\d{1,2})", decoded, re.IGNORECASE)
        if not m or href in seen:
            continue
        seen.add(href)
        links.append(PdfLink(url=href, kw=int(m.group(1)), text=" ".join(a.get_text(" ").split())))
    return sorted(links, key=lambda link: link.kw)


def load_pdf_bytes(src: str) -> bytes:
    if src.lower().startswith(("http://", "https://")):
        resp = requests.get(src, timeout=60, headers=USER_AGENT)
        resp.raise_for_status()
        data = resp.content
    else:
        data = Path(src).read_bytes()
    if not data.lstrip()[:5] == b"%PDF-":
        raise ValueError("Antwort ist kein PDF")
    return data


def _mu():
    try:
        import pymupdf
    except ImportError:  # ältere PyMuPDF-Versionen
        import fitz as pymupdf
    return pymupdf


def _open_pdf(data: bytes):
    return _mu().open(stream=data, filetype="pdf")


# --- Tabellenraster ----------------------------------------------------------
# Die Wochen-PDFs sind eine Tabelle: Spalten = Menülinien (z.B. "Mittags. Cordonbleu",
# "Mittags. Vital", "Mittags. Vegi", "Suppe / Dessert"), Zeilen = Montag bis Sonntag.
# Der Text ist NICHT als Text im PDF gespeichert (keine Textebene), aber die gepunkteten
# Tabellenlinien sind Vektoren. Daraus wird das Raster gelesen und jede Zelle einzeln
# per OCR gelesen - das ist viel sauberer als die ganze Seite auf einmal.
@dataclass
class Grid:
    cols: list  # [(x0, x1), ...] Menü-Spalten
    header: tuple  # (y0, y1) Kopfzeile mit den Spaltenüberschriften
    rows: list  # [(y0, y1), ...] sieben Tageszeilen, Montag ... Sonntag


def _cluster(values: list, tol: float = 1.0) -> list:
    groups = []
    for v in sorted(values):
        if groups and v - groups[-1][-1] <= tol:
            groups[-1].append(v)
        else:
            groups.append([v])
    return [sum(g) / len(g) for g in groups]


def find_grid(page) -> Optional[Grid]:
    hor, ver = [], []
    for d in page.get_drawings():
        if d.get("type") != "s":  # nur Linien, keine Füllflächen
            continue
        r = d["rect"]
        if r.height < 1.0 and r.width > 20:
            hor.append(r)
        elif r.width < 1.0 and r.height > 1.0:
            ver.append(r)
    if len(ver) < 3 or not hor:
        return None
    top, bottom = min(r.y0 for r in ver), max(r.y1 for r in ver)
    inner = [r for r in hor if top + 3 < r.y0 < bottom - 3]
    if not inner:
        return None
    xs = _cluster([r.x0 for r in ver])
    ys = _cluster([r.y0 for r in inner])
    right = max(r.x1 for r in inner)
    rows = list(zip(ys, ys[1:] + [bottom]))
    cols = list(zip(xs, xs[1:] + [right]))
    if len(rows) != 7 or len(cols) < 2:
        return None  # Layout nicht wie erwartet (Montag..Sonntag)
    return Grid(cols=cols, header=(top, ys[0]), rows=rows)


def _clean_lines(lines) -> list:
    out = []
    for ln in lines:
        ln = re.sub(r"^[|:;.,‚'`_\s]+", "", ln.strip())  # Artefakte der gepunkteten Linien
        ln = re.sub(r"\s*CHF\s*[\d.,]+\s*$", "", ln)  # Preis am Zeilenende
        if re.search(r"\w", ln) and not re.match(r"^CHF\b", ln, re.IGNORECASE):
            out.append(ln)
    return out


def _ocr_lines(page, rect, psm: int) -> list:
    """OCR über Tesseract (Binary + Sprachpaket nötig, im Workflow per apt installiert)."""
    import pytesseract
    from PIL import Image

    pix = page.get_pixmap(dpi=300, clip=rect)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    return _clean_lines(pytesseract.image_to_string(img, lang=OCR_LANG, config=f"--psm {psm}").splitlines())


def read_area(page, x0: float, y0: float, x1: float, y1: float, allow_ocr: bool, psm: int = 6) -> list:
    """Text eines Bereichs: erst Textebene, sonst OCR. Der Rand wird ausgespart
    (dort verlaufen die gepunkteten Linien)."""
    rect = _mu().Rect(x0 + 2, y0 + 2, x1 - 2, y1 - 2)
    lines = _clean_lines(page.get_text("text", clip=rect).splitlines())
    if lines or not allow_ocr:
        return lines
    return _ocr_lines(page, rect, psm)


@dataclass
class Table:
    kind: str  # "mittag" | "abend"
    header: list  # pro Spalte: Liste von Zeilen
    body: list = field(default_factory=list)  # pro Tag (Mo..So): pro Spalte: Liste von Zeilen
    chars: int = 0


def page_kind(header_text: str) -> str:
    t = header_text.lower()
    if "mittag" in t:
        return "mittag"
    if "abend" in t:
        return "abend"
    return "mittag"  # unbekannt: lieber mitprüfen als übersehen


def read_table(page, grid: Grid, allow_ocr: bool) -> Table:
    header = [read_area(page, x0, grid.header[0], x1, grid.header[1], allow_ocr) for x0, x1 in grid.cols]
    kind = page_kind(" ".join(" ".join(h) for h in header))
    table = Table(kind=kind, header=header)
    table.chars = sum(len(t) for h in header for t in h)
    if kind != "mittag":
        return table  # Abendmenü wird nicht gelesen
    for y0, y1 in grid.rows:
        row = [read_area(page, x0, y0, x1, y1, allow_ocr) for x0, x1 in grid.cols]
        table.body.append(row)
        table.chars += sum(len(t) for cell in row for t in cell)
    return table


def join_dish(lines: list) -> str:
    """Zeilen einer Zelle zu einem Satz: «Eidgenoss» mit Raclettekäse und Bauernschinken, Wedges, Salat"""
    out = ""
    for ln in lines:
        if not out:
            out = ln
        elif out.endswith((",", " und", " an", " mit", " auf")) or re.match(r"^(mit|und|an|auf|in|im|vom)\b", ln):
            out += " " + ln
        else:
            out += ", " + ln
    return out


def _clean_head(text: str) -> str:
    return re.sub(r"^\W*Mittags?\.\s*", "", text).strip()


def table_findings(link: PdfLink, iso_year: int, table: Table) -> list:
    """Einordnung:
    - Stichwort in einer SPALTENÜBERSCHRIFT (z.B. 'Mittags. Cordonbleu') -> die Menülinie gibt
      es die ganze Woche (Cordonbleu-Woche); gemeldet wird nur das, keine Einzelgerichte
    - Stichwort in einer Zelle einer Tageszeile -> nur dieser Tag"""
    filename = unquote(link.url.split("?")[0]).rsplit("/", 1)[-1] or f"KW{link.kw}.pdf"
    monday = date.fromisocalendar(iso_year, link.kw, 1)

    def make(scope: str, gericht: str, beschreibung: str, weekday: str = "") -> Finding:
        return Finding(
            scope=scope,
            quelle=f"PDF {filename}",
            quell_url=link.url,
            gericht=gericht,
            beschreibung=beschreibung[:600],
            iso_year=iso_year,
            iso_week=link.kw,
            day=monday + timedelta(days=WEEKDAYS.index(weekday)) if weekday else None,
            weekday=weekday,
        )

    for c, head in enumerate(table.header):
        head_text = " ".join(head)
        if not KEYWORD_RE.search(head_text):
            continue
        term = KEYWORD_RE.search(head_text).group(0).strip()
        return [make("woche", term, _clean_head(head_text))]

    result = []
    for r, row in enumerate(table.body):
        for cell in row:
            if KEYWORD_RE.search(" ".join(cell)):
                line = next((ln for ln in cell if KEYWORD_RE.search(ln)), cell[0])
                if WEEKDAYS[r] in ACTIVE_DAYS:
                    result.append(make("tag", line, join_dish(cell), WEEKDAYS[r]))
                else:
                    print(f"[pdf] KW{link.kw}: Treffer am {WEEKDAYS[r]} ignoriert (TAGE={', '.join(sorted(ACTIVE_DAYS))})")
                break  # ein Treffer pro Tag reicht
    return result


def fallback_findings(link: PdfLink, iso_year: int, lines: list) -> list:
    """Kein Tabellenraster erkannt (PDF-Layout geändert oder gescannt): Seite komplett lesen
    und nur melden, DASS das Stichwort vorkommt - ohne Zuordnung zu Tag/Woche."""
    text = " ".join(lines)
    if re.search(r"abend\.", text, re.IGNORECASE) and not re.search(r"mittags?\.", text, re.IGNORECASE):
        return []
    for i, ln in enumerate(lines):
        if KEYWORD_RE.search(ln):
            filename = unquote(link.url.split("?")[0]).rsplit("/", 1)[-1] or f"KW{link.kw}.pdf"
            return [
                Finding(
                    scope="unklar",
                    quelle=f"PDF {filename}",
                    quell_url=link.url,
                    gericht=ln,
                    beschreibung=" / ".join(lines[i : i + 3])[:300],
                    iso_year=iso_year,
                    iso_week=link.kw,
                )
            ]
    return []


def analyse_pdf(link: PdfLink, today: date) -> list:
    iso_year = resolve_iso_year(link.kw, today)
    if iso_year is None:
        raise ValueError(f"KW {link.kw} ist keine gültige Kalenderwoche")
    if date.fromisocalendar(iso_year, link.kw, 7) < today:
        # Die Seite nennt am Montagmorgen teils noch die Vorwoche als "aktuelle Woche".
        print(f"[pdf] KW{link.kw}: Woche bereits vorbei - übersprungen")
        return []
    data = load_pdf_bytes(link.url)
    allow_ocr = PDF_OCR != "never"

    findings, chars = [], 0
    for pno, page in enumerate(_open_pdf(data)):
        grid = find_grid(page)
        if grid:
            table = read_table(page, grid, allow_ocr)
            chars += table.chars
            print(f"[pdf] KW{link.kw} Seite {pno + 1}: Tabelle erkannt ({table.kind}), {table.chars} Zeichen gelesen")
            if table.kind == "mittag":
                findings += table_findings(link, iso_year, table)
        else:
            r = page.rect
            lines = read_area(page, r.x0, r.y0, r.x1, r.y1, allow_ocr, psm=3)
            chars += sum(len(ln) for ln in lines)
            print(f"[pdf] KW{link.kw} Seite {pno + 1}: kein Tabellenraster erkannt, Volltext {len(lines)} Zeilen")
            findings += fallback_findings(link, iso_year, lines)
    if chars == 0:
        warn(f"PDF KW{link.kw}: kein Text lesbar (weder Textebene noch OCR) - OCR/Tesseract prüfen")
    elif not any(f.scope == "woche" for f in findings) and any(f.scope == "unklar" for f in findings):
        print(f"[pdf] KW{link.kw}: Treffer ohne erkanntes Tabellenlayout - Zuordnung unklar")
    print(f"[pdf] KW{link.kw}: {len(findings)} Treffer")
    return findings


def check_pdfs(html: str, today: date) -> list:
    links = find_pdf_links(html)
    if not links:
        warn("Keine Wochenmenü-PDFs (...KW##.pdf) auf der Seite gefunden - Seitenstruktur geändert?")
        return []
    findings = []
    for link in links:
        try:
            findings += analyse_pdf(link, today)
        except Exception as exc:  # noqa: BLE001 - ein defektes PDF soll den Rest nicht verhindern
            warn(f"PDF KW{link.kw} konnte nicht geprüft werden: {exc}")
    return sorted(findings, key=lambda f: f.scope != "woche")


def dump_pdfs(sources: list):
    """Diagnose: zeigt pro PDF das erkannte Tabellenraster, den gelesenen Text jeder Zelle und
    die Einordnung der Treffer. Ohne Argumente: die auf der Menüseite verlinkten PDFs."""
    today = today_ch()
    if sources:
        links = []
        for src in sources:
            m = re.search(r"KW\s*0?(\d{1,2})", unquote(src), re.IGNORECASE)
            links.append(PdfLink(src, int(m.group(1)) if m else today.isocalendar()[1], Path(src).name))
    else:
        links = find_pdf_links(fetch_html())
        if not links:
            print("Keine PDF-Links auf der Seite gefunden.")
    allow_ocr = PDF_OCR != "never"
    for link in links:
        print(f"\n===== {link.text or link.url}  (KW {link.kw}) =====")
        iso_year = resolve_iso_year(link.kw, today) or today.year
        for pno, page in enumerate(_open_pdf(load_pdf_bytes(link.url))):
            grid = find_grid(page)
            if not grid:
                print(f"--- Seite {pno + 1}: kein Tabellenraster erkannt (Fallback: Volltext)")
                r = page.rect
                lines = read_area(page, r.x0, r.y0, r.x1, r.y1, allow_ocr, psm=3)
                print("\n".join(f"    {ln}" for ln in lines))
                print(f"  => Findings: {[(f.scope, f.gericht) for f in fallback_findings(link, iso_year, lines)]}")
                continue
            print(
                f"--- Seite {pno + 1}: Raster {len(grid.cols)} Spalten x {len(grid.rows)} Tage | "
                f"Spalten x={[round(a) for a, _ in grid.cols]} | Zeilen y={[round(a) for a, _ in grid.rows]}"
            )
            table = read_table(page, grid, allow_ocr)
            print(f"    Art: {table.kind}")
            for c, head in enumerate(table.header):
                print(f"    Kopf Spalte {c + 1}: {' | '.join(head)}")
            for r, row in enumerate(table.body):
                for c, cell in enumerate(row):
                    print(f"    {WEEKDAYS[r][:2]} Sp{c + 1}: {join_dish(cell)}")
            if table.kind == "mittag":
                found = table_findings(link, iso_year, table)
                for f in found:
                    print(f"  => TREFFER {f.scope} {f.weekday or ''} | {f.gericht}\n{f.beschreibung}")
                if not found:
                    print("  => kein Treffer")


# =============================================================================
# Benachrichtigung
# =============================================================================
class _SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"  # unbekannter Platzhalter bleibt sichtbar stehen


def template_values(f: Finding, today: Optional[date] = None) -> dict:
    """Platzhalter für Betreff/Text der E-Mail."""
    today = today or today_ch()
    monday = date.fromisocalendar(f.iso_year, f.iso_week, 1)
    sunday = monday + timedelta(days=6)
    details = f"Gericht:\n{f.beschreibung}"
    if f.scope == "woche":
        umfang = f"ganze Woche (KW {f.iso_week})"
        tag, datum, hinweis = "ganze Woche", f"{monday:%d.%m.}-{sunday:%d.%m.%Y}", ""
        titel = f"{f.gericht}-Woche (KW {f.iso_week})"
        details = ""  # Cordonbleu-Woche reicht als Info, keine Einzelgerichte
    elif f.scope == "tag" and f.day:
        umfang = f"nur {f.weekday}, {fmt_date(f.day)}"
        tag, datum, hinweis = f.weekday, fmt_date(f.day), ""
        titel = f"{f.gericht} - {umfang}"
    else:
        umfang = f"Tag/Woche unklar (KW {f.iso_week})"
        tag, datum = "unklar", f"{monday:%d.%m.}-{sunday:%d.%m.%Y}"
        hinweis = "Das Tabellenlayout des PDFs wurde nicht erkannt, daher keine Zuordnung zu Tag/Woche - bitte das PDF ansehen."
        titel = f"{f.gericht} - {umfang}"
    return {
        "gericht": f.gericht,
        "beschreibung": f.beschreibung,
        "umfang": umfang,
        "tag": tag,
        "datum": datum,
        "woche": week_label(f.iso_year, f.iso_week, today),
        "kw": str(f.iso_week),
        "quelle": f.quelle,
        "quell_url": f.quell_url,
        "url": URL,
        "stichwoerter": ", ".join(ACTIVE_KEYWORDS),
        "hinweis": hinweis,
        "titel": titel,
        "details": details,
    }


def render(template: str, values: dict, default: str) -> str:
    tpl = (template or default).replace("\\n", "\n")
    try:
        return tpl.format_map(_SafeDict(values))
    except (ValueError, IndexError, KeyError, AttributeError) as exc:
        warn(f"E-Mail-Vorlage fehlerhaft ({exc}) - Standardvorlage wird verwendet")
        return default.format_map(_SafeDict(values))


def build_messages(f: Finding, test: bool = False) -> dict:
    """Liefert {'ntfy': (titel, text), 'email': (betreff, text)}. ntfy nutzt immer die
    Standardvorlage, die E-Mail die anpassbare (EMAIL_SUBJECT / EMAIL_BODY)."""
    values = template_values(f)
    prefix, note = ("[TEST] ", "TESTNACHRICHT - kein echter Treffer, nur Beispieldaten.\n\n") if test else ("", "")

    def clean(subject: str, body: str):
        subject = prefix + " ".join(subject.split())
        body = note + re.sub(r"\n{3,}", "\n\n", body).strip() + "\n"
        return subject, body

    return {
        "ntfy": clean(render("", values, DEFAULT_SUBJECT), render("", values, DEFAULT_BODY)),
        "email": clean(
            render(EMAIL_SUBJECT_TEMPLATE, values, DEFAULT_SUBJECT),
            render(EMAIL_BODY_TEMPLATE, values, DEFAULT_BODY),
        ),
    }


def send_ntfy(title: str, message: str, click_url: str, label: str) -> bool:
    try:
        resp = requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={
                "Title": title.encode("utf-8"),
                "Priority": "high",
                "Tags": "fork_and_knife",
                "Click": click_url,
            },
            timeout=15,
        )
        resp.raise_for_status()
        print(f"[ntfy] Notification sent for {label}")
        return True
    except requests.RequestException as exc:
        print(f"[ntfy] Fehler beim Senden: {exc}", file=sys.stderr)
        return False


def send_email(title: str, message: str, label: str) -> bool:
    msg = MIMEText(message, "plain", "utf-8")
    msg["Subject"] = Header(title, "utf-8")
    msg["From"] = EMAIL_FROM
    msg["To"] = ", ".join(EMAIL_TO)
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        print(f"[email] Notification sent for {label} an {len(EMAIL_TO)} Empfänger")
        return True
    except (smtplib.SMTPException, OSError) as exc:
        print(f"[email] Fehler beim Senden: {exc}", file=sys.stderr)
        return False


def dispatch_notification(f: Finding, test: bool = False) -> bool:
    """Schickt über alle aktivierten Kanäle (0, 1 oder 2). True = als erledigt zu werten:
    mindestens ein Kanal hat geklappt (oder es ist gar keiner konfiguriert, dann nur Log).
    Schlägt jeder aktivierte Kanal fehl, wird der Treffer NICHT als gemeldet gespeichert
    und beim nächsten Lauf erneut versucht."""
    msgs = build_messages(f, test=test)
    label = "TEST" if test else f.key
    if not NTFY_ENABLED and not EMAIL_ENABLED:
        print(
            "[warnung] Kein Benachrichtigungskanal konfiguriert (weder NTFY_TOPIC "
            "noch vollständige SMTP_*/EMAIL_TO Variablen gesetzt) - Treffer wird "
            "nur ins Log geschrieben.",
            file=sys.stderr,
        )
        print(f"{msgs['email'][0]}\n{msgs['email'][1]}")
        return True

    results = []
    if NTFY_ENABLED:
        results.append(send_ntfy(*msgs["ntfy"], click_url=f.quell_url, label=label))
    if EMAIL_ENABLED:
        results.append(send_email(*msgs["email"], label=label))
    return any(results)


def run_test_notification():
    """Schickt eine klar als Test gekennzeichnete Benachrichtigung mit Beispieldaten über
    alle aktivierten Kanäle - inkl. deiner E-Mail-Vorlage, so kann man sie vorab ansehen.
    Verändert notified_dates.json nicht."""
    print(f"Test-Modus: aktive Keywords wären {', '.join(ACTIVE_KEYWORDS)}")
    print(f"ntfy aktiv: {NTFY_ENABLED} | E-Mail aktiv: {EMAIL_ENABLED} ({len(EMAIL_TO)} Empfänger)")

    if not NTFY_ENABLED and not EMAIL_ENABLED:
        print(
            "Kein Kanal konfiguriert - es gibt nichts zu testen. Bitte "
            "NTFY_TOPIC und/oder SMTP_*/EMAIL_TO setzen.",
            file=sys.stderr,
        )
        sys.exit(1)

    today = today_ch()
    iso = (today + timedelta(days=7)).isocalendar()
    sample = Finding(
        scope="woche",
        quelle=f"PDF Mittag&Abend KW{iso[1]}.pdf (Beispieldaten)",
        quell_url=URL,
        gericht="Cordonbleu",
        beschreibung="Cordonbleu (Schweinefleisch)",
        iso_year=iso[0],
        iso_week=iso[1],
    )
    ok = dispatch_notification(sample, test=True)
    print("Test abgeschlossen." if ok else "Test fehlgeschlagen - siehe Fehlermeldungen oben.")
    if not ok:
        sys.exit(1)


# =============================================================================
# Zustand (notified_dates.json)
# =============================================================================
def load_notified() -> set:
    if STATE_FILE.exists():
        return set(json.loads(STATE_FILE.read_text()))
    return set()


def save_notified(keys: set):
    STATE_FILE.write_text(json.dumps(sorted(keys), ensure_ascii=False, indent=2))


def main():
    args = sys.argv[1:]
    if "--test" in args or os.environ.get("TEST_NOTIFICATION") == "1":
        run_test_notification()
        return
    if "--dump-pdf" in args or os.environ.get("DUMP_PDF") == "1":
        dump_pdfs([a for a in args if not a.startswith("--")])
        return

    today = today_ch()
    print(f"Suche nach: {', '.join(ACTIVE_KEYWORDS)} | Einzeltage: {', '.join(sorted(ACTIVE_DAYS, key=WEEKDAYS.index))}")
    html = fetch_html()

    findings = check_pdfs(html, today) if PDF_CHECK else []
    findings += find_web_findings(extract_marked_text(html))

    # Einzeltage, die schon durch einen Ganze-Woche-Treffer abgedeckt sind, nicht extra melden
    week_keys = {f.week_key for f in findings if f.scope == "woche"}
    notified = load_notified()
    new, seen = [], set()
    for f in findings:
        if f.scope == "tag" and f.week_key in week_keys:
            continue
        if f.key in notified or f.key in seen:
            continue
        seen.add(f.key)
        new.append(f)

    if not new:
        print(f"Keine neuen Treffer. ({len(findings)} insgesamt gefunden, bereits gemeldet: {len(notified)})")
        return

    for f in new:
        print(f"Neuer Treffer: {f.key} | {f.scope} | {f.quelle} | {f.gericht}")
        if dispatch_notification(f):
            notified.add(f.key)
        else:
            warn(f"Benachrichtigung für {f.key} fehlgeschlagen - wird beim nächsten Lauf erneut versucht")

    save_notified(notified)


if __name__ == "__main__":
    main()
