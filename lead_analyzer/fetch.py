"""Netz-Seam für Phase 2 — hier (Plan 02-01) NUR die reine `normalize()`.

`normalize(raw)` ist die einzige Logik dieses Plans: aus einer rohen Zellwert-
Eingabe wird eine geordnete Kandidaten-Liste (https/www/http-Varianten) gebaut,
oder `None` falls gar keine URL vorliegt (-> Aufrufer wertet ohne Netz mit
Bedarf 5). Kein I/O, vollständig offline testbar.

Die netz-führende `fetch()` kommt in Plan 02-02 und wird an DIESE Datei angehängt.
"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

import requests

from .models import FetchResult


def normalize(raw) -> list[str] | None:
    """Roher Zellwert -> geordnete Kandidaten-URLs, oder None bei leerer Eingabe.

    Reihenfolge der Regeln:
    1. None / leer / nur Leerzeichen -> None.
    2. Ein kaputtes Schema-Präfix wie 'htp://' wird abgeschnitten; der Rest gilt
       als bloßer Host ('htp://naehatelier-sutter' -> 'naehatelier-sutter').
    3. Ohne Schema wird 'https://' vorangestellt, dann via urlsplit zerlegt.
    4. Host kleingeschrieben; Varianten https/www/http in fester Ordnung, mit
       has_www-Schutz (kein zweites www, wenn schon vorhanden).
    5. Duplikate raus, Reihenfolge bleibt erhalten.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    # Kaputtes Schema (alles ausser http/https) abschneiden -> bloßer Host.
    if "://" in s:
        scheme, _, rest = s.partition("://")
        if scheme.lower() not in ("http", "https"):
            s = rest                      # 'htp://naehatelier-sutter' -> 'naehatelier-sutter'
    parts = urlsplit(s if "://" in s else "https://" + s)
    host = parts.netloc.lower()
    if not host:
        return None
    path = parts.path or ""
    bare = host[4:] if host.startswith("www.") else host
    has_www = host.startswith("www.")

    def mk(scheme: str, h: str) -> str:
        return urlunsplit((scheme, h, path, parts.query, ""))

    out = [mk("https", host)]
    if not has_www:
        out.append(mk("https", "www." + bare))
    out.append(mk("http", host))
    if not has_www:
        out.append(mk("http", "www." + bare))

    # Duplikate entfernen, Reihenfolge erhalten.
    seen: set[str] = set()
    uniq: list[str] = []
    for u in out:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq


# --------------------------------------------------------------------------- #
# fetch() — die EINZIGE netzführende Funktion. Wirft NIE (AC4/ROB-02).         #
# Tests mocken `requests.Session.get`; alles darüber/darunter ist rein.        #
# --------------------------------------------------------------------------- #

# Browser-UA + de-CH-Header gegen Schweizer WAF/Cloudflare-403 (Pitfall 3) und
# als Sprach-Bias für spätere deutsche Keyword-Dimensionen.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "de-CH,de;q=0.9,en;q=0.5",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Hartes Byte-Limit: alle Dim-1-Signale (Title, Body-Text) stehen vorne; kappt
# Endlos-/Riesen-Bodies (DoS-Schutz T-02-04, Pitfall 5/6).
_MAX_BYTES = 2_000_000


def _read_capped(resp) -> str:
    """Liest den Body gestreamt bis zum 2-MB-Cap und dekodiert tolerant.

    Encoding: deklariert -> apparent_encoding -> utf-8; immer `errors='replace'`,
    damit latin-1/win-1252-Seiten nie einen UnicodeDecodeError auslösen (AC4).
    """
    chunks: list[bytes] = []
    total = 0
    for chunk in resp.iter_content(8192):
        if not chunk:
            continue
        chunks.append(chunk)
        total += len(chunk)
        if total >= _MAX_BYTES:
            break
    raw = b"".join(chunks)
    enc = resp.encoding or resp.apparent_encoding or "utf-8"
    return raw.decode(enc, errors="replace")


def fetch(candidates: list[str], config) -> FetchResult:
    """Probt die Kandidaten-Varianten und liefert ein `FetchResult`. Wirft NIE.

    Knöpfe (ROB-02): hartes `timeout=(connect, read)` aus der Config (requests hat
    KEINEN Default-Timeout — Pitfall 2), Browser-UA + de-CH-Header, redirect-Cap,
    `stream=True` + 2-MB-Body-Cap. SSL wird als Signal erfasst, nicht als Crash:
    bei `SSLError` (verify=True) wird dieselbe URL mit `verify=False` neu geholt,
    der Body bleibt lesbar, `ssl_ok=False` (Phase 3 wertet das). Jede requests-
    Exception wird auf eine Notiz gemappt; eine echte HTTP-Antwort (auch 4xx/5xx)
    beendet das Probing sofort (eine Antwort = Host existiert).
    """
    session = requests.Session()
    session.max_redirects = 10               # Redirect-Schleifen begrenzen (T-02-05)
    session.headers.update(_HEADERS)
    timeout = (config.timeout_connect, config.timeout_read)
    last_err = "nicht erreichbar"

    try:
        for url in candidates:
            for verify in (True, False):     # zweiter Durchlauf NUR nach SSLError
                try:
                    resp = _do_get(session, url, timeout, verify)
                except requests.exceptions.SSLError:
                    last_err = "SSL-Fehler"
                    continue                  # dieselbe URL mit verify=False erneut
                except requests.exceptions.Timeout:
                    last_err = "Timeout"
                    break                     # nächste Variante
                except requests.exceptions.TooManyRedirects:
                    last_err = "Redirect-Schleife"
                    break
                except requests.exceptions.RequestException:
                    last_err = "nicht erreichbar"
                    break
                except Exception as e:        # belt-and-braces: fetch() wirft NIE
                    last_err = f"Fetch-Ausnahme: {type(e).__name__}"
                    break

                # Antwort erhalten = Host existiert. Body lesen; ein Lesefehler
                # (z.B. ChunkedEncodingError mid-stream) verwirft den Body, NICHT
                # die Existenz — Status bleibt erhalten (Review L2). `with resp`
                # gibt die Verbindung in jedem Fall zurück (Review M1).
                with resp:
                    try:
                        html = _read_capped(resp)
                        read_err = None
                    except Exception:
                        html = None
                        read_err = "Body-Lesefehler"
                    return FetchResult(
                        url=url,
                        ok=(200 <= resp.status_code < 400),
                        status=resp.status_code,
                        final_url=resp.url,
                        redirected=(resp.url != url),
                        ssl_ok=verify,         # False, wenn wir auf verify=False fielen
                        headers=dict(resp.headers),
                        html=html,
                        error=read_err,
                    )

        return FetchResult(
            url=candidates[0] if candidates else "",
            ok=False,
            status=None,
            final_url=None,
            redirected=False,
            ssl_ok=False,
            headers={},
            html=None,
            error=last_err,
        )
    finally:
        session.close()                       # Pool/Sockets freigeben (Review M1)


def _do_get(session, url: str, timeout, verify: bool):
    """Ein einzelner GET. Bei verify=False wird die InsecureRequestWarning scoped
    unterdrückt (das SSL-Signal ist bereits via ssl_ok=False erfasst)."""
    if verify:
        return session.get(url, timeout=timeout, allow_redirects=True, stream=True, verify=True)
    import warnings
    from urllib3.exceptions import InsecureRequestWarning
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", InsecureRequestWarning)
        return session.get(url, timeout=timeout, allow_redirects=True, stream=True, verify=False)
