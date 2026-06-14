"""Phase-2-Tests: reine URL-Normalisierung (`fetch.normalize`) + Netz-Sperre-Beweis.

Deckt BED-01 (Varianten-Reihenfolge) und ROB-01 (leere/kaputte URL -> None bzw.
bloßer Host) ab. Kein Netz — `normalize` ist eine reine String-Funktion.
Zusätzlich wird die autouse-Netz-Sperre aus conftest beidseitig bewiesen:
(a) ein un-gemockter `requests.get` fliegt auf; (b) ein per-Test `monkeypatch`
auf `Session.get` überschreibt die Sperre erfolgreich.
Stil angelehnt an `test_phase1_io.py`.
"""

from __future__ import annotations

import requests
import pytest

from lead_analyzer import fetch


# ---------- BED-01 / ROB-01: normalize() ----------

def test_normalize_none_and_empty():
    assert fetch.normalize(None) is None
    assert fetch.normalize("") is None
    assert fetch.normalize("   ") is None


def test_normalize_malformed_scheme_to_bare_host():
    # 'htp://naehatelier-sutter' -> bloßer Host 'naehatelier-sutter' (kein Crash;
    # DNS scheitert später -> Bedarf 5). Host hat keinen Punkt -> keine www-Variante mit Punkt-Logik,
    # aber Kandidaten werden trotzdem emittiert.
    out = fetch.normalize("htp://naehatelier-sutter")
    assert out is not None
    assert out[0] == "https://naehatelier-sutter"
    # https + www, http + www (Host ohne www-Präfix)
    assert out == [
        "https://naehatelier-sutter",
        "https://www.naehatelier-sutter",
        "http://naehatelier-sutter",
        "http://www.naehatelier-sutter",
    ]


def test_normalize_bare_host_order_exact():
    assert fetch.normalize("example.ch") == [
        "https://example.ch",
        "https://www.example.ch",
        "http://example.ch",
        "http://www.example.ch",
    ]


def test_normalize_www_host_no_second_www():
    out = fetch.normalize("www.example.ch")
    assert out == [
        "https://www.example.ch",
        "http://www.example.ch",
    ]
    # genau zwei Varianten, keine doppelte www
    assert len(out) == 2


def test_normalize_preserves_path_and_scheme_first():
    out = fetch.normalize("https://shop.example.ch/de")
    assert out[0] == "https://shop.example.ch/de"
    # Pfad bleibt in allen Varianten erhalten
    assert all(u.endswith("/de") for u in out)


def test_normalize_dedup_preserves_order():
    out = fetch.normalize("example.ch")
    assert len(out) == len(set(out))  # keine Duplikate
    assert out == list(dict.fromkeys(out))  # Reihenfolge unverändert


# ---------- Netz-Sperre-Beweis (conftest autouse, funktions-skopiert) ----------

def test_network_blocked_by_default():
    # (a) un-gemockter echter Request fliegt laut auf
    with pytest.raises(AssertionError):
        requests.get("http://example.com")


def test_network_block_is_overridable(monkeypatch):
    # (b) per-Test-Override gewinnt -> Plan 02-02 kann Session.get faken
    sentinel = object()
    monkeypatch.setattr(requests.Session, "get", lambda self, *a, **k: sentinel)
    assert requests.Session().get("http://example.com") is sentinel
