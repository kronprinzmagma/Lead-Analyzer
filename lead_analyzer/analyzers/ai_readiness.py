"""Dimension 5 — KI-/Answer-Engine-Bereitschaft (rein, offline).

`analyze(soup)` prüft, wie gut eine Seite für Antwort-Maschinen (Google, LLMs,
Voice/Assistenten) strukturiert ist — das Website-Produkt-Versprechen «in KI-Antworten
auffindbar». Gemessen werden drei strukturierte-Markup-Signale aus dem bereits
geparsten BeautifulSoup-Objekt; kein Netz, vollständig offline testbar.

Signale [CITED: 03-RESEARCH.md Dim-5]:
1. JSON-LD  — <script type="application/ld+json"> mit einem @type (LocalBusiness,
   Organization, … — inklusiv: jeder @type zählt als vorhandenes JSON-LD).
2. Open Graph — <meta property="og:*"> (Social-/Preview-Markup).
3. Microdata — itemscope/itemtype (älteres, aber gültiges strukturiertes Markup).

Verdict-Tabelle (explizit, NICHT Pattern 2):
- JSON-LD vorhanden UND >=3 OG-Tags   -> ok
- irgendein Markup, aber unvollständig -> gap
- gar nichts strukturiert             -> severe

CRITICAL — soup=None (erreichbar, aber kein lesbarer Body: 403/406/429, leerer
Body): NEUTRAL, nicht-wertend (0 Gap-Punkte) — NIE severe, sonst kippt ein
WAF-Block fälschlich auf Bedarf 5 (Invariante 403 != 5).
"""

from __future__ import annotations

import json
import re

from ..models import DimensionVerdict


def analyze(soup) -> DimensionVerdict:
    """Reiner Dimension-5-Befund über ein geparstes BeautifulSoup-Objekt."""
    # soup=None-Guard: erreichbar, aber kein Body -> NICHT bewertbar.
    # Neutrales, nicht-wertendes Verdict (0 Gap-Punkte) — KEIN severe,
    # sonst kippt ein WAF-Block fälschlich auf Bedarf 5 (Invariante 403 != 5).
    if soup is None:
        return DimensionVerdict(5, "ok", "nicht bewertbar (kein HTML)", "n/a")

    # 1) JSON-LD: alle ld+json-Skripte einsammeln, defensiv parsen.
    #    Kaputtes JSON wird übersprungen (try/except) — Abwesenheit ist ein Signal,
    #    kein Crash [CITED: Threat T-03-04].
    ld = soup.find_all("script", attrs={"type": "application/ld+json"})
    types: set[str] = set()
    for s in ld:
        try:
            data = json.loads(s.string or s.get_text() or "")
        except (ValueError, TypeError):
            continue
        for obj in (data if isinstance(data, list) else [data]):
            if isinstance(obj, dict) and obj.get("@type"):
                t = obj["@type"]
                # @type kann String, Liste — oder (selten, aber gültiges JSON) ein
                # dict / eine Liste mit dicts sein. Nur hashbare Strings aufnehmen,
                # sonst würde set.update() mit 'unhashable type: dict' crashen.
                for one in (t if isinstance(t, list) else [t]):
                    if isinstance(one, str):
                        types.add(one)

    # 2) Open Graph: og:*-Meta-Tags.
    og = soup.find_all("meta", property=re.compile(r"^og:", re.I))

    # 3) Microdata: itemscope/itemtype.
    microdata = bool(soup.find(attrs={"itemscope": True}) or soup.find(attrs={"itemtype": True}))

    # Verdict-Tabelle (explizit).
    if not types and not og and not microdata:
        return DimensionVerdict(5, "severe", "kein strukturiertes Markup", "html")
    if types and len(og) >= 3:
        return DimensionVerdict(5, "ok", f"JSON-LD {sorted(types)} + Open Graph vorhanden", "html")

    # Sonst: unvollständig -> gap. Konkret benennen, was fehlt.
    missing: list[str] = []
    if not types:
        missing.append("kein JSON-LD")
    elif len(og) == 0:
        missing.append("kein Open Graph")
    elif len(og) < 3:
        missing.append("zu wenig Open Graph")
    if not og and not microdata:
        missing.append("kein Open Graph/Microdata")
    detail = ", ".join(missing) if missing else "strukturiertes Markup unvollständig"
    return DimensionVerdict(
        5, "gap", f"strukturiertes Markup unvollständig ({detail})", "html"
    )
