"""Phase-3-Integration: volle 6-Dimensionen-Verdrahtung in analyze_row (offline).

Deckt BED-02/04/05/06/07/08 + NACH-01 end-to-end ab: analyze_row parst HTML
genau EINMAL und führt alle sechs Dimensions-Befunde zusammen (Dim 1 existence,
Dim 2 technical, Dim 3 Platzhalter, Dim 4 seo, Dim 5 ai_readiness, Dim 6 content),
aggregiert via scoring.bedarf und hängt reasons.build als Begründung an.

KEIN Test fasst das Netz an: `fetch.fetch` wird pro Test durch
`make_fetch_result`-Fakes ersetzt; die autouse-Netzsperre aus conftest bleibt aktiv.
"""

from __future__ import annotations

import pytest

from lead_analyzer import fetch, scoring, reasons
from lead_analyzer.analyzers import seo
from lead_analyzer.config import Config
from lead_analyzer.models import RowRecord
from lead_analyzer.pipeline import analyze_row

from conftest import make_fetch_result

_CFG = Config(input="x", output="y")
_URL_COL = "Website"


def _rec(url):
    return RowRecord(index=0, cells={_URL_COL: url})


# Modernes Fixture: erfüllt ALLE sechs Dimensionen -> Bedarf 1.
# https + eigene Domain (Dim2 ok); lang+title+meta-desc+canonical+1 H1 (Dim4 ok);
# JSON-LD business + 3 OG (Dim5 ok); Formular+tel+mailto+Impressum+aktuelles
# Copyright (Dim6 ok); >300 Wörter Inhalt (Dim1 ok).
_MODERN_HTML = (
    '<html lang="de"><head>'
    '<title>Beispiel Firma — Schreinerei in Bern</title>'
    '<meta name="description" content="Wir sind eine moderne Schreinerei in Bern '
    'mit langjähriger Erfahrung und bieten massgefertigte Möbel sowie Innenausbau.">'
    '<link rel="canonical" href="https://firma.ch/">'
    '<script type="application/ld+json">'
    '{"@context":"https://schema.org","@type":"LocalBusiness","name":"Firma"}'
    '</script>'
    '<meta property="og:title" content="Firma">'
    '<meta property="og:description" content="Schreinerei">'
    '<meta property="og:image" content="https://firma.ch/x.jpg">'
    '</head><body>'
    '<h1>Willkommen bei der Firma</h1>'
    '<p>' + ("Inhalt mit viel Substanz und vielen Wörtern. " * 80) + '</p>'
    '<form><input type="email" name="mail"><textarea></textarea></form>'
    '<a href="tel:+41310000000">Anrufen</a>'
    '<a href="mailto:info@firma.ch">Mail</a>'
    '<a href="/impressum">Impressum</a>'
    '<footer>© 2026 Firma</footer>'
    '</body></html>'
)


def _modern_fetch(**overrides):
    base = dict(
        ok=True, status=200,
        url="https://firma.ch/", final_url="https://firma.ch/",
        ssl_ok=True, html=_MODERN_HTML,
    )
    base.update(overrides)
    return make_fetch_result(**base)


# --------------------------------------------------------------------------- #
# Sechs Verdicts verdrahtet                                                    #
# --------------------------------------------------------------------------- #

def test_six_verdicts_wired(monkeypatch):
    """Nach einem normalen Fetch hat res.verdicts Länge 6 und deckt Dim 1..6 ab."""
    monkeypatch.setattr(fetch, "fetch", lambda c, cfg: make_fetch_result())
    res = analyze_row(_rec("https://ok.ch"), _URL_COL, _CFG)
    assert len(res.verdicts) == 6
    assert {v.dim for v in res.verdicts} == {1, 2, 3, 4, 5, 6}
    # Dim 3 ist der Platzhalter (level ok).
    dim3 = next(v for v in res.verdicts if v.dim == 3)
    assert dim3.level == "ok"


# --------------------------------------------------------------------------- #
# Richtung: modern -> 1, kaputt -> 5, http-only > 1                            #
# --------------------------------------------------------------------------- #

def test_modern_site_is_bedarf_1(monkeypatch):
    """Ein Fixture, das alle sechs Dimensionen erfüllt -> Bedarf 1 (BED-08)."""
    monkeypatch.setattr(fetch, "fetch", lambda c, cfg: _modern_fetch())
    res = analyze_row(_rec("https://firma.ch"), _URL_COL, _CFG)
    assert res.bedarf == 1


def test_broken_dead_is_bedarf_5(monkeypatch):
    """Unerreichbar (dead) -> Bedarf 5; dead-Override überlebt den neuen 6-Dim-Pfad."""
    monkeypatch.setattr(
        fetch, "fetch",
        lambda c, cfg: make_fetch_result(ok=False, status=None, html=None,
                                         error="nicht erreichbar"),
    )
    res = analyze_row(_rec("https://tot.ch"), _URL_COL, _CFG)
    assert res.bedarf == 5


def test_http_only_bumps_bedarf(monkeypatch):
    """Identisch zum modernen Fixture, aber http-only (Dim2 severe) -> Bedarf > 1."""
    monkeypatch.setattr(
        fetch, "fetch",
        lambda c, cfg: _modern_fetch(url="http://firma.ch/",
                                     final_url="http://firma.ch/"),
    )
    res = analyze_row(_rec("http://firma.ch"), _URL_COL, _CFG)
    assert res.bedarf > 1
    assert res.bedarf >= 3  # ein severe -> s_score-Band >= 3


# --------------------------------------------------------------------------- #
# Leere URL ohne Netz                                                          #
# --------------------------------------------------------------------------- #

def test_empty_url_is_5_no_network(monkeypatch):
    """Leere URL -> Bedarf 5 'keine Website', OHNE fetch-Aufruf."""
    def spy(*a, **k):
        raise AssertionError("fetch darf bei leerer URL NICHT laufen")

    monkeypatch.setattr(fetch, "fetch", spy)
    res = analyze_row(_rec(None), _URL_COL, _CFG)
    assert res.bedarf == 5
    assert res.reason == "keine Website"


# --------------------------------------------------------------------------- #
# 403-no-body != 5 (REGRESSION GUARD)                                          #
# --------------------------------------------------------------------------- #

def test_block_403_no_body_is_not_5_and_is_2(monkeypatch):
    """Clean-https-WAF-Block (403, kein Body) -> Bedarf 2, niemals 5.

    Dim1=gap (blockiert), Dim2=ok (https eigene Domain), Dim3=ok, Dim4/5/6=neutral
    -> G=1, S=0 -> Band 2. Die !=5-Invariante ist der load-bearing Teil.
    """
    monkeypatch.setattr(
        fetch, "fetch",
        lambda c, cfg: make_fetch_result(
            ok=False, status=403, html=None,
            url="https://waf.ch/", final_url="https://waf.ch/", ssl_ok=True),
    )
    res = analyze_row(_rec("https://waf.ch"), _URL_COL, _CFG)
    assert res.bedarf != 5
    assert res.bedarf == 2
    assert "blockiert" in res.reason


# --------------------------------------------------------------------------- #
# Begründung threaded + zahl Platzhalter                                       #
# --------------------------------------------------------------------------- #

def test_reason_is_reasons_build(monkeypatch):
    """res.reason == reasons.build(res.verdicts) (single source of truth)."""
    monkeypatch.setattr(
        fetch, "fetch",
        lambda c, cfg: _modern_fetch(url="http://firma.ch/",
                                     final_url="http://firma.ch/"),
    )
    res = analyze_row(_rec("http://firma.ch"), _URL_COL, _CFG)
    assert res.reason == reasons.build(res.verdicts)
    assert "Bedarf" in res.reason


def test_zahl_stays_placeholder(monkeypatch):
    monkeypatch.setattr(fetch, "fetch", lambda c, cfg: make_fetch_result())
    res = analyze_row(_rec("https://ok.ch"), _URL_COL, _CFG)
    assert res.zahl == scoring.placeholder_result(_rec("https://ok.ch")).zahl


# --------------------------------------------------------------------------- #
# Per-Row-Boundary intakt                                                      #
# --------------------------------------------------------------------------- #

def test_row_boundary_degrades_not_raises(monkeypatch):
    """Ein Analyzer wirft mitten in der Zeile -> degradiertes RowResult, kein Crash."""
    monkeypatch.setattr(fetch, "fetch", lambda c, cfg: make_fetch_result())

    def boom(*a, **k):
        raise ValueError("kaputt")

    monkeypatch.setattr(seo, "analyze", boom)
    res = analyze_row(_rec("https://boom.ch"), _URL_COL, _CFG)
    assert res.bedarf == 5
    assert res.reason.startswith("Fehler:")


# --------------------------------------------------------------------------- #
# Richtungs-Gradient: modern -> http-only -> dead ist nicht-fallend, endet bei 5
# --------------------------------------------------------------------------- #

def test_direction_gradient_non_decreasing(monkeypatch):
    """Mit zunehmender Verschlechterung steigt Bedarf monoton (BED-08)."""
    seq = []

    monkeypatch.setattr(fetch, "fetch", lambda c, cfg: _modern_fetch())
    seq.append(analyze_row(_rec("https://firma.ch"), _URL_COL, _CFG).bedarf)

    monkeypatch.setattr(
        fetch, "fetch",
        lambda c, cfg: _modern_fetch(url="http://firma.ch/",
                                     final_url="http://firma.ch/"),
    )
    seq.append(analyze_row(_rec("http://firma.ch"), _URL_COL, _CFG).bedarf)

    monkeypatch.setattr(
        fetch, "fetch",
        lambda c, cfg: make_fetch_result(ok=False, status=None, html=None,
                                         error="nicht erreichbar"),
    )
    seq.append(analyze_row(_rec("https://tot.ch"), _URL_COL, _CFG).bedarf)

    assert seq == sorted(seq)   # nicht-fallend
    assert seq[-1] == 5
