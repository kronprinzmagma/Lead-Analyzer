"""Phase-3-Tests: reiner Dimension-5-Befund (`analyzers.ai_readiness.analyze`).

Deckt BED-05 (KI-/Answer-Engine-Bereitschaft) ab: JSON-LD-Business-Typ + Open
Graph -> ok; nur OG bzw. nur Microdata -> gap; nichts Strukturiertes -> severe.
Defensiv gegen kaputtes JSON-LD (kein Crash, Abwesenheit ist ein Signal). Kein
Netz — `analyze(soup)` ist rein über ein bereits geparstes BeautifulSoup-Objekt.
Stil wie `test_existence.py`.

CRITICAL: soup=None (erreichbar, aber kein lesbarer Body / 403/406/429) -> NEUTRAL
(level "ok", source "n/a") — NICHT severe/gap (sonst kippt ein WAF-Block auf
Bedarf 5, Invariante 403 != 5).
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from lead_analyzer.analyzers import ai_readiness
from lead_analyzer.models import DimensionVerdict


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


_OG3 = (
    '<meta property="og:title" content="X">'
    '<meta property="og:type" content="website">'
    '<meta property="og:url" content="https://x.ch/">'
)


# ---------- ok: JSON-LD Business-Typ + >=3 OG ----------

def test_jsonld_business_plus_og_is_ok():
    html = (
        '<html><head>'
        '<script type="application/ld+json">{"@type":"LocalBusiness","name":"X"}</script>'
        f'{_OG3}'
        '</head><body>x</body></html>'
    )
    v = ai_readiness.analyze(_soup(html))
    assert isinstance(v, DimensionVerdict)
    assert v.dim == 5
    assert v.level == "ok"


def test_jsonld_type_as_list_plus_og_is_ok():
    html = (
        '<html><head>'
        '<script type="application/ld+json">{"@type":["Organization","LocalBusiness"]}</script>'
        f'{_OG3}'
        '</head><body>x</body></html>'
    )
    v = ai_readiness.analyze(_soup(html))
    assert v.dim == 5
    assert v.level == "ok"


# ---------- gap: nur Open Graph ----------

def test_og_only_is_gap():
    html = f'<html><head>{_OG3}</head><body>x</body></html>'
    v = ai_readiness.analyze(_soup(html))
    assert v.dim == 5
    assert v.level == "gap"
    assert "kein json-ld" in v.reason.lower()


# ---------- gap: nur Microdata ----------

def test_microdata_only_is_gap():
    html = (
        '<html><body>'
        '<div itemscope itemtype="https://schema.org/Organization">X</div>'
        '</body></html>'
    )
    v = ai_readiness.analyze(_soup(html))
    assert v.dim == 5
    assert v.level == "gap"


# ---------- severe: nichts Strukturiertes ----------

def test_nothing_structured_is_severe():
    html = "<html><head><title>X</title></head><body><p>nur Text</p></body></html>"
    v = ai_readiness.analyze(_soup(html))
    assert v.dim == 5
    assert v.level == "severe"
    assert "kein strukturiertes markup" in v.reason.lower()


# ---------- defensiv: kaputtes JSON-LD wirft NIE ----------

def test_malformed_jsonld_does_not_crash_and_counts_as_none():
    html = (
        '<html><head>'
        '<script type="application/ld+json">{not valid json,,}</script>'
        '</head><body>x</body></html>'
    )
    v = ai_readiness.analyze(_soup(html))   # darf NICHT werfen
    assert v.dim == 5
    # kein verwertbares JSON-LD, kein OG, keine Microdata -> severe
    assert v.level == "severe"


def test_malformed_jsonld_with_og_is_gap():
    html = (
        '<html><head>'
        '<script type="application/ld+json">{kaputt,,}</script>'
        f'{_OG3}'
        '</head><body>x</body></html>'
    )
    v = ai_readiness.analyze(_soup(html))
    assert v.dim == 5
    assert v.level == "gap"


# ---------- NEUTRAL: kein HTML (soup is None) -> ok / n/a, NIE severe ----------

def test_no_html_is_neutral_not_severe():
    v = ai_readiness.analyze(None)
    assert v.dim == 5
    assert v.level == "ok"          # NICHT severe/gap
    assert v.source == "n/a"        # unterscheidet Neutral von echtem ok
    low = v.reason.lower()
    assert "nicht bewertbar" in low or "kein html" in low
