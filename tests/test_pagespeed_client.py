"""RED-Scaffold (Wave 0): optionaler PSI-Client `clients/pagespeed.py` (PERF-02, AC7/AC8).

Definiert das Verhalten des PageSpeedClient, bevor er existiert — RED via ImportError,
grün ab Plan 06-04. ALLES vollständig offline: `requests.get` wird pro Test gefaket
(die autouse-Netzsperre aus conftest ist per monkeypatch überschreibbar, LIFO), und der
`sleep` wird als No-Op injiziert -> KEIN Test wartet je echte Sekunden (T-06-02).

Kernverträge (06-RESEARCH Pattern 4 + Pitfalls):
- ohne Key -> kein Client / is_available() False.
- 200 mit gültigem Lighthouse-Body -> PsResult korrekt geparst.
- Timeout / malformed JSON / non-200 -> score() == None, wirft NIE.
- 429 + Retry-After -> gekappte Retries mit (injiziertem) sleep, dann None.
- Budget erschöpft -> None OHNE Netz-Call.
- Cache-Hit -> aus dem Cache OHNE Netz und OHNE Budget-Verbrauch.
- Semaphore kappt die Nebenläufigkeit (<= n in flight).
"""

from __future__ import annotations

import threading

import pytest
import requests

from lead_analyzer import cache
from lead_analyzer.clients.pagespeed import PageSpeedClient
from lead_analyzer.config import Config
from lead_analyzer.models import PsResult

# Gültiger PSI-v5-Body (Lighthouse lab scores).
_VALID_BODY = {
    "lighthouseResult": {
        "categories": {"performance": {"score": 0.42}},
        "audits": {
            "largest-contentful-paint": {"numericValue": 3000},
            "cumulative-layout-shift": {"numericValue": 0.05},
            "total-blocking-time": {"numericValue": 150},
        },
    }
}

_URL = "https://firma.ch/"


class _FakeResp:
    """Minimal-Imitat einer requests.Response für den PSI-Client."""

    def __init__(self, status_code=200, body=None, headers=None, raise_on_json=False):
        self.status_code = status_code
        self._body = body if body is not None else _VALID_BODY
        self.headers = headers or {}
        self._raise_on_json = raise_on_json

    def json(self):
        if self._raise_on_json:
            raise ValueError("malformed JSON")
        return self._body


def _client(sleep=lambda *_: None, concurrency=2, budget=400):
    """Baut einen Client direkt mit injiziertem No-Op-sleep und kleinem Budget/Semaphore."""
    # Direkt-Konstruktion umgeht from_config (Key-Policy) — wir testen score()/_request.
    from lead_analyzer.clients import pagespeed as ps_mod

    sem = threading.Semaphore(concurrency)
    budget_obj = ps_mod._Budget(budget)
    return PageSpeedClient(
        key="k", semaphore=sem, budget=budget_obj, timeout=(5.0, 30.0), sleep=sleep
    )


def test_unavailable_without_key(monkeypatch):
    """from_config ohne PAGESPEED_API_KEY -> None ODER is_available() False."""
    monkeypatch.delenv("PAGESPEED_API_KEY", raising=False)
    client = PageSpeedClient.from_config(Config(input="x", output="y", use_pagespeed=True))
    assert client is None or client.is_available() is False


def test_200_parsed(monkeypatch):
    """200 mit gültigem Body -> PsResult(perf=0.42, lcp=3000, cls=0.05, tbt=150)."""
    monkeypatch.setattr(requests, "get", lambda *a, **k: _FakeResp())
    res = _client().score(_URL)
    assert isinstance(res, PsResult)
    assert abs(res.perf_score - 0.42) < 1e-9
    assert res.lcp_ms == 3000
    assert res.cls == 0.05
    assert res.tbt_ms == 150


def test_timeout_returns_none(monkeypatch):
    """requests.get wirft Timeout -> score() == None, kein Re-raise."""
    def boom(*a, **k):
        raise requests.exceptions.Timeout("zu langsam")

    monkeypatch.setattr(requests, "get", boom)
    assert _client().score(_URL) is None


def test_malformed_json_none(monkeypatch):
    """200 aber .json() wirft ValueError -> score() == None."""
    monkeypatch.setattr(requests, "get", lambda *a, **k: _FakeResp(raise_on_json=True))
    assert _client().score(_URL) is None


def test_429_retry_after_capped(monkeypatch):
    """429 + Retry-After jedes Mal -> gekappte Retries, sleep aufgerufen, am Ende None."""
    calls = {"sleep": 0, "get": 0}

    def fake_get(*a, **k):
        calls["get"] += 1
        return _FakeResp(status_code=429, headers={"Retry-After": "1"})

    def fake_sleep(*_):
        calls["sleep"] += 1

    monkeypatch.setattr(requests, "get", fake_get)
    res = _client(sleep=fake_sleep).score(_URL)
    assert res is None
    assert calls["sleep"] >= 1          # Backoff hat stattgefunden
    assert calls["get"] <= 3            # gekappte Retries (<=3)


def test_budget_exhausted_skips(monkeypatch):
    """Budget=0 -> score() == None OHNE requests.get aufzurufen."""
    def tripwire(*a, **k):
        raise AssertionError("kein Netz bei erschöpftem Budget")

    monkeypatch.setattr(requests, "get", tripwire)
    assert _client(budget=0).score(_URL) is None


def test_cache_hit_no_network(monkeypatch):
    """Vorab gecachtes PsResult -> Rückgabe OHNE Netz und OHNE Budget-Verbrauch."""
    def tripwire(*a, **k):
        raise AssertionError("kein Netz bei Cache-Hit")

    monkeypatch.setattr(requests, "get", tripwire)
    ck = cache.key_for(["pagespeed-v1", "mobile", _URL])
    cache.put(ck, PsResult(perf_score=0.77, lcp_ms=1000, cls=0.01, tbt_ms=10).__dict__)

    client = _client(budget=0)          # Budget 0 -> nur Cache-Hit kann liefern
    res = client.score(_URL)
    assert isinstance(res, PsResult)
    assert abs(res.perf_score - 0.77) < 1e-9


def test_semaphore_caps(monkeypatch):
    """Mit Semaphore(2) übersteigt die gleichzeitige In-flight-Zahl nie 2."""
    lock = threading.Lock()
    state = {"current": 0, "max": 0}
    enter = threading.Event()

    def fake_get(*a, **k):
        with lock:
            state["current"] += 1
            state["max"] = max(state["max"], state["current"])
        enter.wait(0.05)                # kurz halten, um Overlap zu provozieren
        with lock:
            state["current"] -= 1
        return _FakeResp()

    monkeypatch.setattr(requests, "get", fake_get)
    client = _client(concurrency=2, budget=400)

    threads = [threading.Thread(target=client.score, args=(f"{_URL}{i}",)) for i in range(6)]
    for t in threads:
        t.start()
    enter.set()
    for t in threads:
        t.join()

    assert state["max"] <= 2            # Semaphore-Kappe eingehalten
