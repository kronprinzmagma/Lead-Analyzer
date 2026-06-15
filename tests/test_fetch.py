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
from lead_analyzer.config import Config
from lead_analyzer.models import FetchResult

from conftest import FakeResponse


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


# ---------- ROB-02: fetch() — die einzige Netz-Funktion, wirft nie ----------

_CFG = Config(input="x", output="y")  # timeout_connect=5.0, timeout_read=10.0


def _patch_get(monkeypatch, fn):
    """Überschreibt die conftest-Netz-Sperre gezielt mit `fn` (self, url, **kw)."""
    monkeypatch.setattr(requests.Session, "get", fn)


def test_fetch_clean_200_happy_path(monkeypatch):
    def fake_get(self, url, **kw):
        return FakeResponse(
            status_code=200,
            url="https://example.ch/",
            headers={"Content-Type": "text/html"},
            body="<html><head><title>OK</title></head><body>Hallo</body></html>",
        )

    _patch_get(monkeypatch, fake_get)
    fr = fetch.fetch(["https://example.ch/"], _CFG)
    assert isinstance(fr, FetchResult)
    assert fr.ok is True
    assert fr.status == 200
    assert fr.ssl_ok is True
    assert fr.final_url == "https://example.ch/"
    assert fr.error is None
    assert "Hallo" in fr.html


def test_request_shape(monkeypatch):
    """timeout-Tupel aus config, Browser-UA, de-CH, allow_redirects, stream, max_redirects."""
    captured = {}

    def fake_get(self, url, **kw):
        captured["url"] = url
        captured["kwargs"] = kw
        captured["max_redirects"] = self.max_redirects
        captured["headers"] = dict(self.headers)
        return FakeResponse(status_code=200, url=url)

    _patch_get(monkeypatch, fake_get)
    fetch.fetch(["https://example.ch/"], _CFG)

    assert captured["kwargs"]["timeout"] == (_CFG.timeout_connect, _CFG.timeout_read)
    assert captured["kwargs"]["allow_redirects"] is True
    assert captured["kwargs"]["stream"] is True
    assert captured["max_redirects"] == 10
    hdrs = captured["headers"]
    assert "Mozilla/5.0" in hdrs["User-Agent"]
    assert hdrs["Accept-Language"].startswith("de-CH")
    assert "text/html" in hdrs["Accept"]


def test_ssl_signal(monkeypatch):
    """SSLError bei verify=True -> Refetch verify=False, Body lesbar, ssl_ok=False, kein Crash."""
    calls = []

    def fake_get(self, url, **kw):
        calls.append(kw.get("verify"))
        if kw.get("verify") is True:
            raise requests.exceptions.SSLError("cert invalid")
        return FakeResponse(status_code=200, url=url, body="<html><body>trotzdem da</body></html>")

    _patch_get(monkeypatch, fake_get)
    fr = fetch.fetch(["https://example.ch/"], _CFG)
    assert fr.ssl_ok is False
    assert fr.ok is True
    assert "trotzdem da" in fr.html
    assert calls == [True, False]  # zuerst verify=True, dann Fallback verify=False


def test_timeout(monkeypatch):
    """Timeout auf allen Varianten -> ok=False, html=None, error Timeout-artig, kein Crash."""
    def fake_get(self, url, **kw):
        raise requests.exceptions.ReadTimeout("zu langsam")

    _patch_get(monkeypatch, fake_get)
    fr = fetch.fetch(["https://a.ch/", "https://www.a.ch/"], _CFG)
    assert fr.ok is False
    assert fr.html is None
    assert fr.status is None
    assert "Timeout" in fr.error


def test_connection_error_all_variants(monkeypatch):
    def fake_get(self, url, **kw):
        raise requests.exceptions.ConnectionError("dns fail")

    _patch_get(monkeypatch, fake_get)
    fr = fetch.fetch(["https://x.invalid/", "http://x.invalid/"], _CFG)
    assert fr.ok is False
    assert fr.html is None
    assert fr.error == "nicht erreichbar"


def test_too_many_redirects(monkeypatch):
    def fake_get(self, url, **kw):
        raise requests.exceptions.TooManyRedirects("loop")

    _patch_get(monkeypatch, fake_get)
    fr = fetch.fetch(["https://loop.ch/"], _CFG)
    assert fr.ok is False
    assert fr.error == "Redirect-Schleife"


def test_encoding_fallback(monkeypatch):
    """latin-1/win-1252-Bytes -> errors='replace', kein UnicodeDecodeError."""
    # 0xfc = ü in latin-1; als utf-8 wäre das ein ungültiges Byte.
    body = "Café Müller Grüße".encode("latin-1")

    def fake_get(self, url, **kw):
        return FakeResponse(
            status_code=200,
            url=url,
            body=body,
            encoding=None,
            apparent_encoding="ISO-8859-1",
        )

    _patch_get(monkeypatch, fake_get)
    fr = fetch.fetch(["https://umlaut.ch/"], _CFG)
    assert fr.ok is True
    assert fr.html is not None  # dekodiert, kein Crash
    assert "ller" in fr.html


def test_byte_cap_stops_reading(monkeypatch):
    """Body > 2 MB wird auf ~2 MB gekappt (iter_content stoppt)."""
    big = b"a" * (3_000_000)

    def fake_get(self, url, **kw):
        return FakeResponse(status_code=200, url=url, body=big, chunk_size=8192)

    _patch_get(monkeypatch, fake_get)
    fr = fetch.fetch(["https://big.ch/"], _CFG)
    assert fr.ok is True
    # gekappt: deutlich unter 3 MB, im Bereich des 2-MB-Caps (+ ein Rest-Chunk)
    assert len(fr.html) < 2_100_000


def test_4xx_keeps_probing_then_falls_back(monkeypatch):
    """4xx beendet das Probing NICHT mehr: weitere Kandidaten werden getestet,
    und liefert keiner etwas Brauchbares, gewinnt die erste 4xx als Fallback
    (Codex-Review Finding 2)."""
    calls = []

    def fake_get(self, url, **kw):
        calls.append(url)
        return FakeResponse(status_code=404, url=url, body="<html><body>weg</body></html>")

    _patch_get(monkeypatch, fake_get)
    fr = fetch.fetch(["https://a.ch/", "https://www.a.ch/"], _CFG)
    assert fr.status == 404
    assert fr.ok is False  # 404 ist nicht 200-399
    assert fr.url == "https://a.ch/"  # erste (höchstpriore) 4xx als Fallback
    assert calls == ["https://a.ch/", "https://www.a.ch/"]  # ALLE Kandidaten geprobt


def test_4xx_apex_then_200_www(monkeypatch):
    """Der eigentliche Gewinn: Apex liefert 404, 'www.' liefert 200 -> die 200
    gewinnt, NICHT die frühe 404 (Codex-Review Finding 2)."""
    def fake_get(self, url, **kw):
        if url == "https://www.a.ch/":
            return FakeResponse(status_code=200, url=url, body="<html><body>echt</body></html>")
        return FakeResponse(status_code=404, url=url, body="<html><body>weg</body></html>")

    _patch_get(monkeypatch, fake_get)
    fr = fetch.fetch(["https://a.ch/", "https://www.a.ch/"], _CFG)
    assert fr.ok is True
    assert fr.status == 200
    assert fr.url == "https://www.a.ch/"
    assert "echt" in fr.html


def test_fetch_never_raises_on_unexpected_exception(monkeypatch):
    """Auch eine völlig unerwartete Exception darf fetch() nicht nach aussen werfen."""
    def fake_get(self, url, **kw):
        raise RuntimeError("völlig unerwartet")

    _patch_get(monkeypatch, fake_get)
    fr = fetch.fetch(["https://boom.ch/"], _CFG)  # darf NICHT raisen
    assert fr.ok is False
    assert fr.html is None
    assert fr.error is not None


def test_fetch_empty_candidates_is_safe():
    fr = fetch.fetch([], _CFG)
    assert fr.ok is False
    assert fr.html is None


# ---------- Review-Fixes: M1 (Response schliessen) + L2 (Lesefehler != tot) ----------

def test_response_is_closed_after_fetch(monkeypatch):
    """M1: die gestreamte Response wird via `with resp:` immer geschlossen
    (Verbindung/Socket zurück in den Pool) — auch wenn der Byte-Cap früh abbricht."""
    resp = FakeResponse(status_code=200, url="https://a.ch/", body="<html><body>ok</body></html>")

    def fake_get(self, url, **kw):
        return resp

    _patch_get(monkeypatch, fake_get)
    fr = fetch.fetch(["https://a.ch/"], _CFG)
    assert fr.ok is True
    assert resp.closed is True  # geschlossen


def test_midstream_read_error_keeps_host_exists(monkeypatch):
    """L2: Antwort erhalten (Host existiert), aber Body-Lesen scheitert mid-stream
    -> Status bleibt, html=None, error gesetzt; NICHT als 'nicht erreichbar' verworfen."""
    class BrokenBody(FakeResponse):
        def iter_content(self, chunk_size=8192):
            yield b"<html>"
            raise requests.exceptions.ChunkedEncodingError("abgebrochen")

    broken = BrokenBody(status_code=200, url="https://a.ch/")

    def fake_get(self, url, **kw):
        return broken

    _patch_get(monkeypatch, fake_get)
    fr = fetch.fetch(["https://a.ch/"], _CFG)
    assert fr.status == 200          # Host hat geantwortet
    assert fr.html is None           # Body verworfen
    assert fr.error is not None
    assert broken.closed is True     # trotzdem geschlossen (M1)

    # Und die Existenz-Dimension wertet das als gap (existiert), NICHT als tot/Bedarf 5.
    from lead_analyzer.analyzers import existence
    from lead_analyzer import scoring
    verdict = existence.analyze(fr)
    assert verdict.dead is False
    assert scoring.bedarf_from_dim1(verdict) != 5
