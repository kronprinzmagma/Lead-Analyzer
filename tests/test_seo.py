"""Phase-3-Tests: reiner Dimension-4-Befund (`analyzers.seo.analyze`).

Deckt BED-04 ab: Auffindbarkeit (Title, Meta-Description, genau ein H1, Canonical,
html lang, noindex via Meta ODER X-Robots-Tag-Header). Kein Netz — `analyze(fr,
soup)` ist rein über `FetchResult` + vor-geparste BeautifulSoup. Die soup wird im
Test gebaut (parse-once-Vertrag: der Analyzer baut KEINE soup selbst).

KRITISCH: bei soup=None (403/406/429, leerer Body) -> NEUTRAL, NICHT severe/gap —
sonst kippt ein WAF-Block fälschlich auf Bedarf 5 (Invariante 403 != 5).
Stil wie `test_existence.py`.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from lead_analyzer.analyzers import seo
from lead_analyzer.models import DimensionVerdict
from conftest import make_fetch_result


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


# Ein vollständig sauberes HTML (Title, Meta-Desc, 1 H1, Canonical, lang).
_CLEAN = (
    '<html lang="de"><head>'
    "<title>Gute Firma Webseite</title>"
    '<meta name="description" content="Eine ausführliche Beschreibung der Firma '
    'mit genug Länge für die Meta.">'
    '<link rel="canonical" href="https://firma.ch/">'
    "</head><body><h1>Willkommen</h1></body></html>"
)


# ---------- noindex (Meta) -> severe ----------

def test_noindex_meta_is_severe():
    html = _CLEAN.replace("</head>", '<meta name="robots" content="noindex"></head>')
    v = seo.analyze(make_fetch_result(), _soup(html))
    assert isinstance(v, DimensionVerdict)
    assert v.dim == 4
    assert v.level == "severe"
    assert "noindex" in v.reason.lower()


# ---------- noindex (X-Robots-Tag-Header) -> severe, case-insensitiv ----------

def test_noindex_header_mixedcase_is_severe():
    fr = make_fetch_result(headers={"X-Robots-Tag": "noindex, nofollow"})
    v = seo.analyze(fr, _soup(_CLEAN))
    assert v.dim == 4
    assert v.level == "severe"
    assert "noindex" in v.reason.lower()


def test_noindex_header_lowercase_key_is_severe():
    fr = make_fetch_result(headers={"x-robots-tag": "noindex"})
    v = seo.analyze(fr, _soup(_CLEAN))
    assert v.level == "severe"


# ---------- fehlende Pflichtsignale -> gap ----------

def test_missing_title_is_gap():
    html = (
        '<html lang="de"><head>'
        '<meta name="description" content="Eine ausführliche Beschreibung der Firma '
        'mit genug Länge für die Meta.">'
        '<link rel="canonical" href="https://firma.ch/">'
        "</head><body><h1>Willkommen</h1></body></html>"
    )
    v = seo.analyze(make_fetch_result(), _soup(html))
    assert v.level == "gap"


def test_missing_meta_description_is_gap():
    html = (
        '<html lang="de"><head><title>Gute Firma Webseite</title>'
        '<link rel="canonical" href="https://firma.ch/">'
        "</head><body><h1>Willkommen</h1></body></html>"
    )
    v = seo.analyze(make_fetch_result(), _soup(html))
    assert v.level == "gap"


def test_zero_h1_is_gap():
    html = (
        '<html lang="de"><head><title>Gute Firma Webseite</title>'
        '<meta name="description" content="Eine ausführliche Beschreibung der Firma '
        'mit genug Länge für die Meta.">'
        '<link rel="canonical" href="https://firma.ch/">'
        "</head><body><p>kein H1</p></body></html>"
    )
    v = seo.analyze(make_fetch_result(), _soup(html))
    assert v.level == "gap"


# ---------- zwei minor-Flags -> gap (>=2 minor) ----------

def test_two_minor_flags_is_gap():
    # Title + Meta-Desc + 1 H1 vorhanden, aber KEIN Canonical UND KEIN lang.
    html = (
        "<html><head><title>Gute Firma Webseite</title>"
        '<meta name="description" content="Eine ausführliche Beschreibung der Firma '
        'mit genug Länge für die Meta.">'
        "</head><body><h1>Willkommen</h1></body></html>"
    )
    v = seo.analyze(make_fetch_result(), _soup(html))
    assert v.level == "gap"


# ---------- ein minor allein -> ok (<2 minor) ----------

def test_single_minor_is_ok():
    # Canonical vorhanden, nur lang fehlt -> 1 minor -> ok.
    html = (
        "<html><head><title>Gute Firma Webseite</title>"
        '<meta name="description" content="Eine ausführliche Beschreibung der Firma '
        'mit genug Länge für die Meta.">'
        '<link rel="canonical" href="https://firma.ch/">'
        "</head><body><h1>Willkommen</h1></body></html>"
    )
    v = seo.analyze(make_fetch_result(), _soup(html))
    assert v.level == "ok"


# ---------- vollständig sauber -> ok ----------

def test_fully_clean_is_ok():
    v = seo.analyze(make_fetch_result(), _soup(_CLEAN))
    assert v.dim == 4
    assert v.level == "ok"


# ---------- NEUTRAL bei fehlendem HTML (403/leerer Body) ----------

def test_no_html_is_neutral_not_severe():
    v = seo.analyze(make_fetch_result(html=None), None)
    assert v.dim == 4
    assert v.level == "ok"          # NICHT severe/gap (Invariante 403 != 5)
    assert v.source == "n/a"        # unterscheidbar von echtem "ok"
    assert "nicht bewertbar" in v.reason.lower() or "kein html" in v.reason.lower()
