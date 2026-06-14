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

from bs4 import BeautifulSoup

from lead_analyzer import fetch, scoring, reasons
from lead_analyzer.analyzers import seo, payment
from lead_analyzer.config import Config
from lead_analyzer.models import RowRecord
from lead_analyzer.pipeline import analyze_row

from conftest import make_fetch_result

_CFG = Config(input="x", output="y")
_URL_COL = "Website"


# --------------------------------------------------------------------------- #
# Phase 6 RED-Scaffolds (Wave 0): --no-pagespeed-Pfad + Single-Client-Invariante
# Beide referenzieren noch nicht verdrahtete Phase-6-Produktion -> RED bis 06-04/06-05.
# --------------------------------------------------------------------------- #


def test_no_pagespeed_flag(monkeypatch, tmp_path):
    """Config(use_pagespeed=False) -> kein PSI-Client; Bedarf identisch zum Platzhalter.

    Für eine viewport-präsente, erreichbare Seite muss der Bedarf mit abgeschaltetem
    PageSpeed exakt dem heutigen Platzhalter-Resultat entsprechen (byte-identische
    Offline-Garantie, BED-08). RED jetzt: der Heuristik-Analyzer (Dim 3) existiert noch
    nicht, der Pfad ist noch nicht verdrahtet.
    """
    from lead_analyzer.clients.pagespeed import PageSpeedClient  # RED bis 06-04

    # Bei use_pagespeed=False darf from_config keinen Client liefern.
    assert PageSpeedClient.from_config(Config(input="x", output="y", use_pagespeed=False)) is None

    html = (
        '<html><head><meta name="viewport" content="width=device-width">'
        "<title>X</title></head><body>"
        + ("Inhalt mit Substanz. " * 80)
        + "</body></html>"
    )
    monkeypatch.setattr(
        fetch, "fetch",
        lambda c, cfg: make_fetch_result(html=html, url="https://vp.ch/", final_url="https://vp.ch/"),
    )
    cfg_off = Config(input="x", output="y", use_pagespeed=False)
    res = analyze_row(_rec("https://vp.ch"), _URL_COL, cfg_off)
    # Heuristik (viewport vorhanden, ps_result None) -> Dim 3 ok -> Bedarf unverändert.
    dim3 = next(v for v in res.verdicts if v.dim == 3)
    assert dim3.level == "ok"


def test_one_client_per_run(monkeypatch, tmp_path):
    """Single-Client-Invariante (PERF-02/AC8): run() baut GENAU EINEN PSI-Client für den
    ganzen Lauf — nicht einen pro Zeile. Schützt die per-run geteilte Semaphore + das
    Budget gegen einen späteren Per-Row-Refactor. RED jetzt: run() baut noch keinen Client.
    """
    from lead_analyzer import pipeline
    from lead_analyzer.clients.pagespeed import PageSpeedClient  # RED bis 06-04

    calls = {"from_config": 0}
    orig = PageSpeedClient.from_config

    def counting_from_config(config):
        calls["from_config"] += 1
        return orig(config)

    monkeypatch.setattr(PageSpeedClient, "from_config", staticmethod(counting_from_config))

    # Multi-Row-Input (>=3 Zeilen) als CSV.
    inp = tmp_path / "in.csv"
    inp.write_text(
        "Website\nhttps://a.ch\nhttps://b.ch\nhttps://c.ch\n", encoding="utf-8"
    )
    out = tmp_path / "out.csv"
    monkeypatch.setattr(fetch, "fetch", lambda c, cfg: make_fetch_result())

    pipeline.run(Config(input=str(inp), output=str(out), write_csv=True, workers=1))

    assert calls["from_config"] == 1   # GENAU einmal für den ganzen Lauf


def _rec(url, name="", branche=""):
    return RowRecord(index=0, cells={_URL_COL: url, "Kundenname": name, "Branche": branche})


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
    assert "keine Website" in res.reason


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
    """res.reason == reasons.build(res.verdicts, payment=est) (single source of truth)."""
    monkeypatch.setattr(
        fetch, "fetch",
        lambda c, cfg: _modern_fetch(url="http://firma.ch/",
                                     final_url="http://firma.ch/"),
    )
    rec = _rec("http://firma.ch")
    res = analyze_row(rec, _URL_COL, _CFG)
    # die zahl-Schätzung dieser Zeile (name/branche leer, link-loses modern HTML)
    fr = _modern_fetch(url="http://firma.ch/", final_url="http://firma.ch/")
    soup = BeautifulSoup(fr.html, "html.parser")
    est = payment.estimate(rec, fr, soup, _CFG)
    assert res.reason == reasons.build(res.verdicts, payment=est)
    assert "Bedarf" in res.reason


def test_zahl_is_real_estimate(monkeypatch):
    """Normaler Pfad: AG + Zahnarzt -> echte hohe zahl + 'Zahl (Schätzung):'."""
    monkeypatch.setattr(fetch, "fetch", lambda c, cfg: _modern_fetch())
    rec = _rec("https://ok.ch", name="Muster AG", branche="Zahnarzt")
    res = analyze_row(rec, _URL_COL, _CFG)
    assert res.zahl >= 4
    assert "Zahl (Schätzung):" in res.reason


def test_zahl_is_real_estimate_thin(monkeypatch):
    """Link-lose Default-Seite ohne Name/Branche -> konservative 2 (single source)."""
    monkeypatch.setattr(fetch, "fetch", lambda c, cfg: make_fetch_result())
    res = analyze_row(_rec("https://ok.ch"), _URL_COL, _CFG)
    assert res.zahl == payment.estimate(_rec("https://ok.ch"), None, None, _CFG).zahl


def test_empty_url_gets_name_based_zahl(monkeypatch):
    """Leere URL -> Bedarf 5 'keine Website' OHNE Netz, aber echte name/branche-zahl."""
    def spy(*a, **k):
        raise AssertionError("fetch darf bei leerer URL NICHT laufen")

    monkeypatch.setattr(fetch, "fetch", spy)
    res = analyze_row(_rec(None, name="Beispiel AG", branche="Treuhand"), _URL_COL, _CFG)
    assert res.bedarf == 5
    assert "keine Website" in res.reason
    assert res.zahl >= 4   # AG + hoch-Tier -> kein Platzhalter 3


def test_exception_boundary_still_estimates_zahl(monkeypatch):
    """Analyzer wirft -> Bedarf 5 'Fehler:' UND echte name/branche-zahl (netzlos)."""
    monkeypatch.setattr(fetch, "fetch", lambda c, cfg: make_fetch_result())

    def boom(*a, **k):
        raise ValueError("kaputt")

    monkeypatch.setattr(seo, "analyze", boom)
    res = analyze_row(_rec("https://boom.ch", name="Krauer AG", branche="Garage"),
                      _URL_COL, _CFG)
    assert res.bedarf == 5
    assert res.reason.startswith("Fehler:")
    assert res.zahl >= 3


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
