"""Regeländerungen nach Nils' Entscheid vom 2026-11-19 (Musterseiten 02, 05, 12).

(a) Leere JavaScript-Hülle (Single-Page-App) gilt nicht als «dünner Inhalt»;
    Dim 5/6 werden aus der Hülle nicht beurteilt.
(b) Sperre durch Schutzfilter (403/406/429 oder Challenge-Seite) -> Website-Bedarf
    «nicht bewertbar» statt Note; Excel/CSV zeigen den Vermerk, Log `bedarf: null`.
(c) Fehlt einer sonst guten Seite nur strukturiertes Markup (Dim 5), höchstens Bedarf 2.
"""

from __future__ import annotations

import json

import openpyxl
from bs4 import BeautifulSoup

from conftest import make_fetch_result
from lead_analyzer import scoring, table_io
from lead_analyzer.analyzers import existence
from lead_analyzer.models import DimensionVerdict, RowRecord, RowResult
from lead_analyzer.sales_arguments import NOT_RATED_NOTE, build_arguments

_SPA = (
    '<html><head><title>X</title><script src="/app.js"></script></head>'
    '<body><div id="root"></div></body></html>'
)
_ANGULAR = '<html><head><script src="/main.js"></script></head><body><app-root></app-root></body></html>'
_THIN_STATIC = "<html><head><title>X</title></head><body><p>Nur zwei Sätze. Mehr nicht.</p></body></html>"


def _soup(html):
    return BeautifulSoup(html, "html.parser")


# --- (a) JavaScript-Hülle ---------------------------------------------------- #

def test_js_shell_detected():
    assert existence.is_js_shell(_soup(_SPA))
    assert existence.is_js_shell(_soup(_ANGULAR))


def test_thin_static_page_is_not_js_shell():
    """Dünne Seite ohne Skript bleibt «dünn» (keine Aufweichung der alten Regel)."""
    assert not existence.is_js_shell(_soup(_THIN_STATIC))
    v = existence.analyze(make_fetch_result(html=_THIN_STATIC), _soup(_THIN_STATIC))
    assert v.level == "gap" and "dünn" in v.reason


def test_page_with_text_and_root_div_is_not_shell():
    """Serverseitig gerenderte Seite mit viel Text und #root ist keine leere Hülle."""
    html = ('<html><head><script src="/a.js"></script></head><body><div id="root">'
            + "<p>" + "Wort " * 400 + "</p></div></body></html>")
    assert not existence.is_js_shell(_soup(html))


def test_js_shell_dim1_ok_not_thin():
    v = existence.analyze(make_fetch_result(html=_SPA), _soup(_SPA))
    assert v.level == "ok"
    assert "JavaScript" in v.reason


# --- (b) nicht bewertbar ----------------------------------------------------- #

def test_challenge_page_with_503_is_unbewertbar():
    html = "<html><head><title>Just a moment...</title></head><body>cf-chl</body></html>"
    v = existence.analyze(make_fetch_result(ok=False, status=503, html=html))
    assert v.unbewertbar and not v.dead
    assert "blockiert" in v.reason


def test_plain_503_without_challenge_unchanged():
    """503 ohne Body bleibt «nicht erreichbar» (tot -> 5), nicht «nicht bewertbar»."""
    v = existence.analyze(make_fetch_result(ok=False, status=503, html=None))
    assert v.dead and not v.unbewertbar


def test_bewertbar_flag():
    assert scoring.bewertbar([DimensionVerdict(1, "ok", "x")])
    assert not scoring.bewertbar([DimensionVerdict(1, "gap", "x", unbewertbar=True)])


def test_sort_puts_unrated_last():
    recs = [RowRecord(i, {}) for i in range(3)]
    res = [RowResult(0, bedarf=None, zahl=5), RowResult(1, bedarf=1, zahl=1), RowResult(2, bedarf=4, zahl=2)]
    order = [r.index for _, r in scoring.stable_sort(list(zip(recs, res, strict=True)))]
    assert order == [2, 1, 0]


def test_output_shows_nicht_bewertbar(tmp_path):
    rec = RowRecord(0, {"Kundenname": "Muster AG", "Website": "https://x.example"})
    res = RowResult(0, bedarf=None, zahl=4, reason="Website-Bedarf nicht bewertbar (…)")
    out = tmp_path / "o.xlsx"
    table_io.write_output(str(out), ["Kundenname", "Website"], [(rec, res)], url_col="Website")
    ws = openpyxl.load_workbook(out)["Leads"]
    row = [c.value for c in ws[2]]
    assert row[2] == "nicht bewertbar"
    assert row[3] == 4                     # Zahlungskräftigkeit bleibt numerisch
    log = tmp_path / "o.run.jsonl"
    table_io.write_run_log(str(log), "Website", [(rec, res)])
    entry = json.loads(log.read_text(encoding="utf-8"))
    assert entry["bedarf"] is None and entry["bewertbar"] is False


def test_sales_arguments_for_unrated_row():
    rec = RowRecord(0, {"Kundenname": "Muster AG"})
    name, defizite, text = build_arguments(rec, RowResult(0, bedarf=None, zahl=3))
    assert name == "Muster AG" and defizite == "" and text == NOT_RATED_NOTE


# --- (c) nur Markup fehlt ---------------------------------------------------- #

def _vs(levels):
    return [DimensionVerdict(i + 1, lvl, "x") for i, lvl in enumerate(levels)]


def test_only_markup_missing_caps_at_2():
    assert scoring.bedarf(_vs(["ok", "ok", "ok", "ok", "severe", "ok"])) == 2


def test_markup_plus_other_gap_unchanged():
    """Kommt eine weitere Lücke dazu, gilt die bisherige Aggregation (S=1 -> 3)."""
    assert scoring.bedarf(_vs(["ok", "ok", "ok", "gap", "severe", "ok"])) == 3
