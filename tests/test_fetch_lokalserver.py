"""Zeichensatz-Fälle gegen einen lokalen Testserver (Idee 40, 2026-11-23).

Ergänzt die Tests in `test_fetch.py` um den ganzen echten Weg: requests baut das
Antwortobjekt selbst aus einer echten HTTP-Antwort. Der Server läuft nur auf
127.0.0.1 in diesem Prozess; die conftest-Netzsperre wird pro Test gezielt
aufgehoben, und Proxy-Variablen werden entfernt, damit nichts die Maschine verlässt.
Alle Seiten synthetisch, keine echten Firmen.
"""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import requests

from lead_analyzer import fetch
from lead_analyzer.config import Config

# Beim Import ist die autouse-Netzsperre aus conftest noch nicht aktiv (sie greift erst
# pro Test) -> hier steht das echte Session.get.
_ECHTES_GET = requests.Session.get

_CFG = Config(input="x", output="y", use_cache=False)

_SEITE = (
    "<html><head><title>Bäckerei Müller in Zürich</title></head>"
    "<body><p>Über uns: Grüsse aus der Backstube.</p></body></html>"
).encode()

# Pfad -> Content-Type-Header (None = Header fehlt ganz)
_FAELLE = {
    "/mit-charset": "text/html; charset=utf-8",
    "/ohne-charset": "text/html",
    "/ohne-content-type": None,
    "/xhtml": "application/xhtml+xml",
}


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # Name von http.server vorgegeben
        content_type = _FAELLE.get(self.path, "text/html")
        self.send_response(200)
        if content_type is not None:
            self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(_SEITE)))
        self.end_headers()
        self.wfile.write(_SEITE)

    def log_message(self, *args):  # kein Rauschen im Testlauf
        pass


@pytest.fixture
def lokalserver(monkeypatch):
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setattr(requests.Session, "get", _ECHTES_GET)   # Sperre nur für diesen Test auf
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize("pfad", list(_FAELLE))
def test_umlaute_ueber_echte_http_antwort(lokalserver, pfad):
    fr = fetch.fetch([lokalserver + pfad], _CFG)
    assert fr.status == 200
    assert fr.error is None, fr.error
    assert "Bäckerei Müller in Zürich" in fr.html
    assert "Über uns" in fr.html
