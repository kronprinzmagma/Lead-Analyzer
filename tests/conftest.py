"""Gemeinsame Test-Infrastruktur für Phase 2.

Kernzweck (harte CLAUDE.md-Vorgabe): Das **Netz ist im gesamten Test-Lauf
gesperrt**. Eine autouse-Fixture ersetzt `requests.Session.get` und
`requests.get` durch eine Funktion, die laut scheitert — jeder un-gemockte echte
Request fliegt sofort als AssertionError auf. Die Fixture ist FUNKTIONS-skopiert
und nutzt pytest-`monkeypatch`, damit ein einzelner Test sein eigenes
`monkeypatch.setattr(requests.Session, "get", fake)` darüberlegen kann (so braucht
Plan 02-02 für `fetch()`-Tests einen echten Override-Mechanismus).

Zusätzlich stehen wiederverwendbare Fakes als Modul-Funktionen/-Klassen bereit
(nicht nur als Fixtures), damit Plan 02-02 sie direkt importieren kann:
- `make_fetch_result(**overrides)` -> ein `FetchResult` mit sinnvollen Defaults.
- `FakeResponse` -> ein winziges `requests.Response`-Imitat für `fetch()`-Tests.
"""

from __future__ import annotations

import requests
import pytest

from lead_analyzer.models import FetchResult


# --------------------------------------------------------------------------- #
# Netz-Sperre: autouse, funktions-skopiert, über monkeypatch (überschreibbar)  #
# --------------------------------------------------------------------------- #

def _network_blocked(*args, **kwargs):  # pragma: no cover - soll nie durchlaufen
    raise AssertionError("network used in tests")


@pytest.fixture(autouse=True)
def _block_network(monkeypatch):
    """Sperrt jeden echten HTTP-Zugriff per Default.

    Funktions-skopiert via `monkeypatch`: ein einzelner Test kann danach mit
    einem eigenen `monkeypatch.setattr(requests.Session, "get", fake)` die
    Sperre gezielt überschreiben (LIFO-Reihenfolge -> der spätere Patch gewinnt).
    """
    monkeypatch.setattr(requests.Session, "get", _network_blocked)
    monkeypatch.setattr(requests, "get", _network_blocked)
    yield


@pytest.fixture(autouse=True)
def _isolate_cache(tmp_path):
    """Lenkt JEDEN Cache-Zugriff in ein per-Test tmp_path (W3, Pitfall 4).

    Phase 5 routet alle fetch()-Aufrufe durch den Cache. Diese autouse-Fixture
    garantiert, dass KEIN Test (neu oder bestehend) jemals ins repo cache/
    schreibt. Lazy-Import, damit die Collection vor Existenz von cache.py nicht
    bricht (TDD-RED-Phase) und damit cache-fremde Tests nicht hart koppeln.
    """
    try:
        from lead_analyzer import cache
    except ImportError:
        yield
        return
    cache.set_cache_dir(tmp_path)
    yield


# --------------------------------------------------------------------------- #
# Wiederverwendbare Fakes (Modul-Ebene -> auch von Plan 02-02 importierbar)     #
# --------------------------------------------------------------------------- #

def make_fetch_result(**overrides) -> FetchResult:
    """Baut ein `FetchResult` mit erreichbaren, gesunden Defaults.

    Jedes Feld ist per Keyword überschreibbar, z.B.
    `make_fetch_result(status=403, ok=False)`.
    """
    defaults = dict(
        url="https://example.ch/",
        ok=True,
        status=200,
        final_url="https://example.ch/",
        redirected=False,
        ssl_ok=True,
        headers={},
        html="<html><head><title>Beispiel</title></head><body>Inhalt</body></html>",
        error=None,
    )
    defaults.update(overrides)
    return FetchResult(**defaults)


def make_ps_result(**overrides):
    """Baut ein `PsResult` mit gesunden Defaults (spiegelt make_fetch_result).

    Lazy-Import von `lead_analyzer.models.PsResult` INNERHALB der Funktion, damit
    die Test-Collection in der RED-Phase überlebt, solange PsResult noch nicht
    existiert (Wave 0). Jedes Feld ist per Keyword überschreibbar, z.B.
    `make_ps_result(perf_score=0.30)`.
    """
    from lead_analyzer.models import PsResult  # lazy: toleriert RED-Phase

    defaults: dict[str, object] = dict(
        perf_score=0.95,   # 0..1, gute Lighthouse-Performance
        lcp_ms=2000,       # Largest Contentful Paint (ms) — gut (<2500)
        cls=0.05,          # Cumulative Layout Shift — gut (<0.10)
        tbt_ms=100,        # Total Blocking Time (ms) — gut (<200)
        ok=True,
    )
    defaults.update(overrides)
    return PsResult(**defaults)


class FakeResponse:
    """Winziges Imitat von `requests.Response` für `fetch()`-Tests (Plan 02-02).

    Liefert genau die Attribute/Methoden, die `fetch()` anfasst:
    `.status_code`, `.url`, `.headers`, `.encoding`, `.apparent_encoding` und
    `.iter_content(chunk)`. `body` darf `bytes` oder `str` sein; für den
    Encoding-Fallback-Test gibt man latin-1/win-1252-kodierte Bytes plus
    `encoding=None` herein, damit `apparent_encoding` greift.
    """

    def __init__(
        self,
        status_code: int = 200,
        url: str = "https://example.ch/",
        headers: dict | None = None,
        body: bytes | str = b"<html><body>Inhalt</body></html>",
        encoding: str | None = "utf-8",
        apparent_encoding: str = "utf-8",
        chunk_size: int = 8192,
    ):
        self.status_code = status_code
        self.url = url
        self.headers = headers or {}
        self._body = body.encode("utf-8") if isinstance(body, str) else body
        self.encoding = encoding
        self.apparent_encoding = apparent_encoding
        self._chunk_size = chunk_size

        self.closed = False

    def iter_content(self, chunk_size: int = 8192):
        size = chunk_size or self._chunk_size
        for i in range(0, len(self._body), size):
            yield self._body[i : i + size]

    def close(self):
        self.closed = True

    # Context-Manager: fetch() nutzt `with resp:` zum garantierten Schliessen.
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False
