"""Dimension 1 — Existenz & Substanz (rein, offline).

`analyze(fr)` wandelt ein `FetchResult` in einen `DimensionVerdict(dim=1, ...)`.
Kein I/O — alle Signale stammen aus dem bereits abgerufenen `FetchResult`, sodass
die Funktion komplett offline mit Fixtures testbar ist.

Prioritäts-Reihenfolge (erster Treffer gewinnt) — exakt aus der RESEARCH-Tabelle:
1. error gesetzt UND kein html  -> severe "nicht erreichbar (...)"  [TOT -> Bedarf 5]
2. status in {403,406,429}       -> gap "blockiert – nicht bewertbar" [NICHT tot/5]
3. status >= 400 ohne html       -> severe "nicht erreichbar (HTTP ...)" [TOT -> 5]
4. geparkter Host/Marker         -> severe "geparkt/Platzhalter"      [TOT -> 5]
5. Social-Host                   -> severe "Social-only"             [Präsenz, nicht tot]
6. dünner Inhalt (<300 Wörter)   -> gap "dünner Inhalt"
7. sonst                         -> ok "erreichbar, Inhalt vorhanden"
"""

from __future__ import annotations

from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from ..models import DimensionVerdict


# Geparkte/Platzhalter-Domains (Host nach www-Strip).  [CITED: FEATURES.md Dim-1]
PARKED_HOSTS = {
    "sedoparking.com",
    "parkingcrew.net",
    "bodis.com",
    "above.com",
    "dan.com",
    "afternic.com",
    "hugedomains.com",
    "domainmarket.com",
}

# Platzhalter-/Parking-/Default-Server-Marker (case-insensitiver Substring).
PARKED_MARKERS = (
    "diese domain",
    "domain parken",
    "domain is for sale",
    "buy this domain",
    "this domain is for sale",
    "website coming soon",
    "under construction",
    "in arbeit",
    "standardseite",
    "apache2 ubuntu default page",
    "welcome to nginx",
    "iis windows server",
)

# Social-only-Hosts (Präsenz existiert, aber keine eigene Website).
SOCIAL_HOSTS = {
    "facebook.com",
    "m.facebook.com",
    "fb.com",
    "instagram.com",
    "linktr.ee",
    "linkedin.com",
    "tiktok.com",
    "t.me",
    "xing.com",
}

_THIN_WORDS = 300


def analyze(fr) -> DimensionVerdict:
    """Reiner Dimension-1-Befund über ein `FetchResult`."""
    # 1) Alle Varianten gescheitert: kein Body -> tot.
    if fr.error and not fr.html:
        return DimensionVerdict(1, "severe", f"nicht erreichbar ({fr.error})", "html")

    # 2) WAF-Block: geantwortet, aber nicht bewertbar -> NICHT Bedarf 5.
    if fr.status in (403, 406, 429):
        return DimensionVerdict(1, "gap", "blockiert – nicht bewertbar", "html")

    # 3) Echte HTTP-Fehler ohne Body -> tot.
    if fr.status is not None and fr.status >= 400 and not fr.html:
        return DimensionVerdict(1, "severe", f"nicht erreichbar (HTTP {fr.status})", "html")

    host = urlsplit(fr.final_url or fr.url or "").netloc.lower().removeprefix("www.")

    text = ""
    title = ""
    if fr.html:
        soup = BeautifulSoup(fr.html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        title = (soup.title.string or "").strip().lower() if soup.title and soup.title.string else ""
        text = soup.get_text(" ", strip=True)
    low = (title + " " + text[:1024]).lower()

    # 4) Geparkt (Host oder Marker).
    if host in PARKED_HOSTS or any(m in low for m in PARKED_MARKERS):
        return DimensionVerdict(1, "severe", "geparkt/Platzhalter", "html")

    # 5) Social-only.
    if host in SOCIAL_HOSTS:
        return DimensionVerdict(1, "severe", "Social-only", "html")

    # 6) Dünner Inhalt.
    if len(text.split()) < _THIN_WORDS:
        return DimensionVerdict(1, "gap", "dünner Inhalt", "html")

    # 7) Erreichbar mit Substanz.
    return DimensionVerdict(1, "ok", "erreichbar, Inhalt vorhanden", "html")
