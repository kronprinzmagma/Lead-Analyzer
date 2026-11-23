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
- `FakeResponse` -> ein echtes `requests.Response` mit Test-Body für `fetch()`-Tests.
"""

from __future__ import annotations

import io

import pytest
import requests
from requests.structures import CaseInsensitiveDict
from requests.utils import get_encoding_from_headers

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


class _ZaehlenderBody(io.BytesIO):
    """Roher Antwort-Body (wie `resp.raw`), der mitzählt, wie viele Bytes gelesen wurden.

    So lässt sich prüfen, dass `fetch()` die 2-MB-Grenze wirklich einhält und nicht
    nachträglich den ganzen Rest des Bodys nachlädt."""

    gelesen = 0

    def read(self, size=-1, /):
        data = super().read(size)
        self.gelesen += len(data)
        return data


class FakeResponse(requests.Response):
    """Testdoppelgänger für `fetch()`-Tests, gebaut auf dem ECHTEN `requests.Response`.

    Bis 2026-11-23 war das eine freie Imitation mit frei setzbarem `encoding` und
    `apparent_encoding`. Das echte Objekt verhält sich anders: `encoding` kommt aus dem
    Content-Type-Header (ohne charset bei `text/*` fest ISO-8859-1, sonst None), und
    `apparent_encoding` liest `.content` — nach gestreamtem Lesen wirft das einen
    RuntimeError bzw. lädt den ganzen Rest des Bodys nach. Die Imitation hat diese
    Fehler darum versteckt (Idee 40, repo-cockpit code-praxis 2026-11-23).

    Jetzt: echtes `requests.Response`, Body als `raw`-Strom, `encoding` genau wie im
    requests-HTTPAdapter aus den Headern abgeleitet. Zusätzlich `.closed` (wurde die
    Antwort geschlossen?) und `.raw.gelesen` (wie viele Body-Bytes wurden gelesen?).
    `body` darf `bytes` oder `str` (wird UTF-8-kodiert) sein.
    """

    def __init__(
        self,
        status_code: int = 200,
        url: str = "https://example.ch/",
        headers: dict | None = None,
        body: bytes | str = b"<html><body>Inhalt</body></html>",
    ):
        super().__init__()
        self.status_code = status_code
        self.url = url
        self.headers = CaseInsensitiveDict(headers or {})
        self.raw = _ZaehlenderBody(body.encode("utf-8") if isinstance(body, str) else body)
        # Wie requests.adapters.HTTPAdapter.build_response:
        self.encoding = get_encoding_from_headers(self.headers)
        self.closed = False

    def close(self):
        self.closed = True
        super().close()
