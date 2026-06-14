"""Phase-2-Tests: reiner Dimension-1-Befund (`analyzers.existence.analyze`).

Deckt BED-01 (Verdict-Matrix) ab: erreichbar->ok, geparkt->severe,
Social->severe, dünn->gap, 403/406/429->gap "blockiert" (WAF-Schutz: NICHT
Bedarf 5). Kein Netz — `analyze` ist rein über ein `FetchResult`.
Nutzt den `make_fetch_result`-Helfer aus conftest. Stil wie `test_phase1_io.py`.
"""

from __future__ import annotations

import pytest

from lead_analyzer.analyzers import existence
from lead_analyzer.models import DimensionVerdict
from conftest import make_fetch_result


def _body(words: int) -> str:
    inner = " ".join(["wort"] * words)
    return f"<html><head><title>Seite</title></head><body><p>{inner}</p></body></html>"


# ---------- DEAD: nicht erreichbar (alle Varianten gescheitert) ----------

def test_error_and_no_html_is_dead_severe():
    fr = make_fetch_result(ok=False, status=None, html=None, final_url=None,
                           error="nicht erreichbar (Timeout)")
    v = existence.analyze(fr)
    assert isinstance(v, DimensionVerdict)
    assert v.dim == 1
    assert v.level == "severe"
    assert v.reason.startswith("nicht erreichbar")


def test_dead_reason_does_not_double_unreachable_phrase():
    # fetch.py sets fr.error == "nicht erreichbar"; the verdict must not read
    # the doubled "nicht erreichbar (nicht erreichbar)".
    fr = make_fetch_result(ok=False, status=None, html=None, final_url=None,
                           error="nicht erreichbar")
    v = existence.analyze(fr)
    assert v.level == "severe"
    assert v.dead is True
    assert v.reason == "nicht erreichbar"


def test_dead_reason_keeps_distinct_error_detail():
    fr = make_fetch_result(ok=False, status=None, html=None, final_url=None,
                           error="timeout")
    v = existence.analyze(fr)
    assert v.reason == "nicht erreichbar (timeout)"


def test_dead_reason_empty_error_reads_kein_body():
    fr = make_fetch_result(ok=False, status=None, html=None, final_url=None,
                           error=None)
    v = existence.analyze(fr)
    assert v.reason == "nicht erreichbar (kein Body)"


# ---------- WAF-Block: 403/406/429 -> gap, NICHT severe/Bedarf 5 ----------

@pytest.mark.parametrize("status", [403, 406, 429])
def test_waf_block_is_gap_not_severe(status):
    fr = make_fetch_result(ok=False, status=status, html=None, error=None)
    v = existence.analyze(fr)
    assert v.dim == 1
    assert v.level == "gap"          # explizit: NICHT severe (kein Bedarf 5)
    assert "blockiert" in v.reason.lower()


# ---------- DEAD: 4xx/5xx ohne Body ----------

@pytest.mark.parametrize("status", [404, 410, 500, 503])
def test_http_error_no_body_is_dead_severe(status):
    fr = make_fetch_result(ok=False, status=status, html=None, error=None)
    v = existence.analyze(fr)
    assert v.level == "severe"
    assert f"HTTP {status}" in v.reason


# ---------- DEAD: geparkt (Host bzw. Marker) ----------

def test_parked_host_is_dead_severe():
    fr = make_fetch_result(final_url="https://sedoparking.com/foo",
                           html="<html><body>irgendwas</body></html>")
    v = existence.analyze(fr)
    assert v.level == "severe"
    assert "geparkt" in v.reason.lower() or "platzhalter" in v.reason.lower()


def test_parked_marker_in_body_is_dead_severe():
    fr = make_fetch_result(final_url="https://kleinfirma.ch/",
                           html="<html><title>Domain</title><body>Diese Domain steht zum Verkauf - buy this domain</body></html>")
    v = existence.analyze(fr)
    assert v.level == "severe"
    assert "geparkt" in v.reason.lower() or "platzhalter" in v.reason.lower()


# ---------- Social-only -> severe (Präsenz vorhanden, nicht "tot") ----------

def test_social_host_is_severe():
    fr = make_fetch_result(final_url="https://facebook.com/somepage",
                           html=_body(500))
    v = existence.analyze(fr)
    assert v.level == "severe"
    assert "social" in v.reason.lower()


# ---------- Thin content -> gap ----------

def test_thin_body_is_gap():
    fr = make_fetch_result(final_url="https://klein.ch/", html=_body(50))
    v = existence.analyze(fr)
    assert v.level == "gap"
    assert "dünn" in v.reason.lower() or "duenn" in v.reason.lower()


# ---------- Reachable + substanziell -> ok ----------

def test_substantial_body_is_ok():
    fr = make_fetch_result(final_url="https://gut.ch/", html=_body(500))
    v = existence.analyze(fr)
    assert v.level == "ok"
    assert v.dim == 1
