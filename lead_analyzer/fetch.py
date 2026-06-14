"""Netz-Seam für Phase 2 — hier (Plan 02-01) NUR die reine `normalize()`.

`normalize(raw)` ist die einzige Logik dieses Plans: aus einer rohen Zellwert-
Eingabe wird eine geordnete Kandidaten-Liste (https/www/http-Varianten) gebaut,
oder `None` falls gar keine URL vorliegt (-> Aufrufer wertet ohne Netz mit
Bedarf 5). Kein I/O, vollständig offline testbar.

Die netz-führende `fetch()` kommt in Plan 02-02 und wird an DIESE Datei angehängt.
"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit


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
