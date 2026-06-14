"""Phase-3-Tests: reiner Dimension-6-Befund (`analyzers.content.analyze`).

Deckt BED-06 (Inhalt, Aktualität & Conversion) ab: Kontaktpfad/Formular,
tel:/mailto:, Impressum/Datenschutz, Copyright-Aktualität und Legacy-Generator.
Pattern-2-Faltung (severe>gap>=2 minor>ok). Kein Netz — `analyze(fr, soup)` ist
rein; der Copyright-Scan liest `fr.html`.

WICHTIG: Frische-Jahre werden IMMER relativ zu `datetime.now().year` berechnet
(nie hardcodiert 2026), damit die Suite nicht über die Jahre verrottet.

CRITICAL: soup=None (erreichbar, aber kein lesbarer Body) -> NEUTRAL
(level "ok", source "n/a") — NICHT severe/gap (Invariante 403 != 5). Der Guard
muss VOR dem fr.html-Copyright-Scan greifen.
"""

from __future__ import annotations

from datetime import datetime

from bs4 import BeautifulSoup

from lead_analyzer.analyzers import content
from lead_analyzer.models import DimensionVerdict
from conftest import make_fetch_result


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


_FORM = '<form><input type="email" name="e"><textarea></textarea></form>'
_TEL = '<a href="tel:+41441234567">Anrufen</a>'
_MAILTO = '<a href="mailto:x@y.ch">Mail</a>'
_IMPRESSUM = '<a href="/impressum">Impressum</a>'


def _page(*, form=True, tel=True, mailto=True, impressum=True, copyright_year=None,
          generator=None) -> str:
    parts = ["<html><head>"]
    if generator is not None:
        parts.append(f'<meta name="generator" content="{generator}">')
    parts.append("</head><body>")
    if form:
        parts.append(_FORM)
    if tel:
        parts.append(_TEL)
    if mailto:
        parts.append(_MAILTO)
    if impressum:
        parts.append(_IMPRESSUM)
    if copyright_year is not None:
        parts.append(f"<footer>© {copyright_year} Firma</footer>")
    parts.append("</body></html>")
    return "".join(parts)


# ---------- clean ok ----------

def test_clean_page_is_ok():
    now = datetime.now().year
    html = _page(copyright_year=now)
    v = content.analyze(make_fetch_result(html=html), _soup(html))
    assert isinstance(v, DimensionVerdict)
    assert v.dim == 6
    assert v.level == "ok"


# ---------- kein Kontaktpfad -> gap ----------

def test_no_contact_path_is_gap():
    now = datetime.now().year
    html = _page(form=False, copyright_year=now)
    # Achtung: _MAILTO/_TEL/_IMPRESSUM bleiben, aber Formular weg und kein
    # "kontakt"-Link -> kein Kontaktpfad. Wir entfernen zusätzlich nichts; der
    # gap-Trigger ist "kein Formular UND kein kontakt-Link".
    v = content.analyze(make_fetch_result(html=html), _soup(html))
    assert v.dim == 6
    assert v.level == "gap"


# ---------- kein Impressum -> gap ----------

def test_no_impressum_is_gap():
    now = datetime.now().year
    html = _page(impressum=False, copyright_year=now)
    v = content.analyze(make_fetch_result(html=html), _soup(html))
    assert v.dim == 6
    assert v.level == "gap"


# ---------- veraltetes Copyright: now-2 -> gap ----------

def test_stale_copyright_gap():
    year = datetime.now().year - 2
    html = _page(copyright_year=year)
    v = content.analyze(make_fetch_result(html=html), _soup(html))
    assert v.dim == 6
    assert v.level == "gap"


# ---------- stark veraltetes Copyright: now-5 -> severe ----------

def test_stale_copyright_severe():
    year = datetime.now().year - 5
    html = _page(copyright_year=year)
    v = content.analyze(make_fetch_result(html=html), _soup(html))
    assert v.dim == 6
    assert v.level == "severe"


# ---------- Legacy-Generator -> gap ----------

def test_legacy_generator_is_gap():
    now = datetime.now().year
    html = _page(copyright_year=now, generator="WordPress 4.9")
    v = content.analyze(make_fetch_result(html=html), _soup(html))
    assert v.dim == 6
    assert v.level == "gap"


# ---------- 2 minor (kein tel UND kein mailto) -> gap ----------

def test_two_minor_folds_to_gap():
    now = datetime.now().year
    html = _page(tel=False, mailto=False, copyright_year=now)
    v = content.analyze(make_fetch_result(html=html), _soup(html))
    assert v.dim == 6
    assert v.level == "gap"


# ---------- 1 minor (nur kein tel) -> bleibt ok ----------

def test_single_minor_stays_ok():
    now = datetime.now().year
    html = _page(tel=False, copyright_year=now)
    v = content.analyze(make_fetch_result(html=html), _soup(html))
    assert v.dim == 6
    assert v.level == "ok"


# ---------- kein Copyright gefunden = minor (nicht hart bestraft) ----------

def test_no_copyright_is_minor_stays_ok():
    html = _page(copyright_year=None)  # form+tel+mailto+impressum, kein Copyright
    v = content.analyze(make_fetch_result(html=html), _soup(html))
    assert v.dim == 6
    assert v.level == "ok"


# ---------- NEUTRAL: kein HTML (soup is None, fr.html=None) ----------

def test_no_html_is_neutral_not_severe():
    fr = make_fetch_result(html=None)
    v = content.analyze(fr, None)
    assert v.dim == 6
    assert v.level == "ok"          # NICHT severe/gap
    assert v.source == "n/a"        # unterscheidet Neutral von echtem ok
    low = v.reason.lower()
    assert "nicht bewertbar" in low or "kein html" in low
