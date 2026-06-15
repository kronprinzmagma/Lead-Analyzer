"""RED-Scaffold (Wave 0): optionaler Zefix-Client `clients/zefix.py` (PERF-02, AC5/AC7/AC8).

Definiert das Verhalten des ZefixClient, bevor er existiert — RED via ImportError,
gruen ab Plan 08-01. ALLES vollstaendig offline: `requests.post` wird pro Test gefaket
(die autouse-Netzsperre aus conftest sperrt nur requests.get + Session.get — POST bleibt
offen, wird aber hier per monkeypatch ebenfalls gefaket), und der `sleep` wird als No-Op
injiziert -> KEIN Test wartet je echte Sekunden.

Kernvertraege (08-RESEARCH Patterns 1-5 + Pitfalls):
- ohne Credentials -> kein Client (from_config returns None).
- 200 mit genau 1 Ergebnis -> ZefixFacts korrekt geparst.
- 0 Ergebnisse oder >1 Ergebnisse -> None (negativ gecacht).
- Timeout / non-200 -> lookup() == None, wirft NIE, NICHT gecacht.
- 429 + Retry-After -> gekappte Retries mit (injiziertem) sleep, dann None.
- Budget erschoepft -> None OHNE Netz-Call.
- Cache-Hit -> aus dem Cache OHNE Netz und OHNE Budget-Verbrauch.
- Negativ-Cache-Hit (_miss:True) -> None OHNE Netz.
- Name < 3 Zeichen -> None OHNE Netz-Call.
"""

from __future__ import annotations

import threading

import pytest
import requests

from lead_analyzer import cache
from lead_analyzer.clients.zefix import ZefixClient
from lead_analyzer.config import Config
from lead_analyzer.models import ZefixFacts

# Gueltiger Zefix-CompanyShort-Response-Body (genau 1 Ergebnis — unambiguous match).
_VALID_BODY = [
    {
        "name": "Muster AG",
        "ehraid": 12345678,
        "uid": "CHE-123.456.789",
        "legalSeat": "Zuerich",
        "legalSeatId": 261,
        "registryOfCommerceId": 20,
        "legalForm": {
            "id": 3,
            "uid": "0106",
            "name": {"de": "Aktiengesellschaft", "fr": "Societe anonyme", "it": "SA", "en": "Corp"},
            "shortName": {"de": "AG", "fr": "SA", "it": "SA", "en": "Ltd"},
        },
        "status": "ACTIVE",
        "sogcDate": "2023-04-15",
        "deletionDate": None,
    }
]


class _FakeResp:
    """Minimal-Imitat einer requests.Response fuer den Zefix-Client."""

    def __init__(self, status_code=200, body=None, headers=None, raise_on_json=False):
        self.status_code = status_code
        self._body = body if body is not None else _VALID_BODY
        self.headers = headers or {}
        self._raise_on_json = raise_on_json

    def json(self):
        if self._raise_on_json:
            raise ValueError("malformed JSON")
        return self._body


def _client(sleep=lambda *_: None, budget=200):
    """Baut einen ZefixClient direkt mit injiziertem No-Op-sleep und Budget/Semaphore."""
    from lead_analyzer.clients import zefix as zx_mod

    sem = threading.Semaphore(2)
    budget_obj = zx_mod._Budget(budget)
    return ZefixClient("u", "p", sem, budget_obj, (5.0, 15.0), sleep=sleep)


# --------------------------------------------------------------------------- #
# 10 Verhaltensstests (Testnamen bindend per 08-VALIDATION.md)                 #
# --------------------------------------------------------------------------- #


def test_unavailable_without_creds(monkeypatch):
    """from_config ohne ZEFIX_USER/ZEFIX_PASSWORD -> None."""
    monkeypatch.delenv("ZEFIX_USER", raising=False)
    monkeypatch.delenv("ZEFIX_PASSWORD", raising=False)
    client = ZefixClient.from_config(Config(input="x", output="y", use_zefix=True))
    assert client is None


def test_single_match_parsed(monkeypatch):
    """200 mit genau 1 Ergebnis -> ZefixFacts korrekt geparst (AG, ACTIVE, source='zefix')."""
    monkeypatch.setattr(requests, "post", lambda *a, **k: _FakeResp(200, body=_VALID_BODY))
    result = _client().lookup("Muster AG")
    assert isinstance(result, ZefixFacts)
    assert result.legal_form_de == "AG"
    assert result.status == "ACTIVE"
    assert result.source == "zefix"
    assert "entity/12345678" in result.source_url


def test_zero_results_none(monkeypatch):
    """200 mit 0 Ergebnissen -> None (negativ gecacht); 2. Lookup trifft Cache, kein Netz."""
    monkeypatch.setattr(requests, "post", lambda *a, **k: _FakeResp(200, body=[]))
    client = _client()
    result = client.lookup("Unbekannt GmbH")
    assert result is None

    # Zweiter Lookup: Tripwire — POST darf jetzt NICHT mehr aufgerufen werden
    def tripwire(*a, **k):
        raise AssertionError("network called on negativ-gecachtem Lookup")

    monkeypatch.setattr(requests, "post", tripwire)
    result2 = client.lookup("Unbekannt GmbH")
    assert result2 is None


def test_ambiguous_none(monkeypatch):
    """200 mit >1 Ergebnis -> None (ambiguous, negativ gecacht); 2. Lookup trifft Cache."""
    monkeypatch.setattr(requests, "post", lambda *a, **k: _FakeResp(200, body=_VALID_BODY * 2))
    client = _client()
    result = client.lookup("Muster AG")
    assert result is None

    def tripwire(*a, **k):
        raise AssertionError("network called on ambiguous negativ-gecachtem Lookup")

    monkeypatch.setattr(requests, "post", tripwire)
    result2 = client.lookup("Muster AG")
    assert result2 is None


def test_timeout_none(monkeypatch):
    """requests.post wirft Timeout -> None, NICHT gecacht; 2. Lookup (200) liefert ZefixFacts."""
    def timeout_post(*a, **k):
        raise requests.exceptions.Timeout("zu langsam")

    monkeypatch.setattr(requests, "post", timeout_post)
    client = _client()
    result = client.lookup("Timeout AG")
    assert result is None

    # Zweiter Lookup mit erfolgreichem POST: Timeout wurde NICHT gecacht -> Netz wird gerufen
    monkeypatch.setattr(requests, "post", lambda *a, **k: _FakeResp(200, body=_VALID_BODY))
    result2 = client.lookup("Timeout AG")
    assert isinstance(result2, ZefixFacts)


def test_429_retry_capped(monkeypatch):
    """429 + Retry-After -> gekappte Retries, sleep aufgerufen >=1, POST aufgerufen <=3, am Ende None."""
    calls = {"sleep": 0, "post": 0}

    def fake_post(*a, **k):
        calls["post"] += 1
        return _FakeResp(429, body=[], headers={"Retry-After": "1"})

    def fake_sleep(*_):
        calls["sleep"] += 1

    monkeypatch.setattr(requests, "post", fake_post)
    result = _client(sleep=fake_sleep).lookup("Retry AG")
    assert result is None
    assert calls["sleep"] >= 1      # Backoff hat stattgefunden
    assert calls["post"] <= 3       # gekappte Retries


def test_budget_exhausted(monkeypatch):
    """Budget=0 -> lookup() == None OHNE requests.post aufzurufen."""
    def tripwire(*a, **k):
        raise AssertionError("kein Netz bei erschoepftem Budget")

    monkeypatch.setattr(requests, "post", tripwire)
    assert _client(budget=0).lookup("Muster AG") is None


def test_cache_hit_no_network(monkeypatch):
    """Vorab gecachtes ZefixFacts -> Rueckgabe OHNE Netz und OHNE Budget-Verbrauch."""
    def tripwire(*a, **k):
        raise AssertionError("kein Netz bei Cache-Hit")

    monkeypatch.setattr(requests, "post", tripwire)
    ck = cache.key_for(["zefix-v1", "Muster AG", ""])
    cached_facts = ZefixFacts(
        legal_form_de="AG",
        legal_form_fr="SA",
        status="ACTIVE",
        uid="CHE-123.456.789",
        legal_seat="Zuerich",
        source_url="https://www.zefix.admin.ch/de/search/entity/12345678/info",
        source="zefix",
    )
    cache.put(ck, cached_facts.__dict__)

    client = _client(budget=0)  # Budget 0 -> nur Cache-Hit kann liefern
    result = client.lookup("Muster AG")
    assert isinstance(result, ZefixFacts)
    assert result.legal_form_de == "AG"
    assert result.source == "zefix"


def test_negative_cache_hit(monkeypatch):
    """Vorab gecachtes {'_miss': True} -> None OHNE Netz."""
    def tripwire(*a, **k):
        raise AssertionError("kein Netz bei Negativ-Cache-Hit")

    monkeypatch.setattr(requests, "post", tripwire)
    ck = cache.key_for(["zefix-v1", "Unbekannt GmbH", ""])
    cache.put(ck, {"_miss": True})

    result = _client().lookup("Unbekannt GmbH")
    assert result is None


def test_short_name_guard(monkeypatch):
    """Name < 3 Zeichen -> None OHNE requests.post aufzurufen (Zefix minLength: 3)."""
    def tripwire(*a, **k):
        raise AssertionError("kein Netz bei zu kurzem Namen")

    monkeypatch.setattr(requests, "post", tripwire)
    assert _client().lookup("ab") is None
    assert _client().lookup("") is None
    assert _client().lookup("X") is None
