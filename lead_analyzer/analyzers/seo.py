"""Dimension 4 — Auffindbarkeit / SEO (rein, offline).

`analyze(fr, soup)` wandelt ein `FetchResult` + vor-geparste BeautifulSoup in
einen `DimensionVerdict(dim=4, ...)`. Kein I/O, baut KEINE soup selbst (parse-once
-Vertrag: die Pipeline parst einmal und reicht die soup durch).

Gemessen wird die Einzelseiten-Indexierbarkeit:
- noindex via Meta-Robots ODER X-Robots-Tag-Header -> severe
- Title, Meta-Description, genau ein H1 -> Pflicht (Fehlen = gap)
- Title-/Meta-Länge, Canonical, html lang, mehrere H1 -> minor
robots.txt / sitemap.xml sind bewusst AUSGELASSEN (DEFERRED): sie bräuchten einen
zusätzlichen HTTP-Abruf + Cache (Phase 5/6). AC11 bleibt erfüllt (Dim 1–4 real
gemessen). [CITED: 03-RESEARCH.md Dim-4 / FEATURES.md]

KRITISCH — no-HTML-Policy: bei soup=None (403/406/429, leerer Body) -> NEUTRAL,
nicht-wertend (0 Gap-Punkte). KEIN severe/gap, sonst kippt ein WAF-Block
fälschlich auf Bedarf 5 (Phase-2-Invariante 403 != 5).

Aggregation (Pattern 2): any severe -> severe; sonst >=1 gap -> gap;
sonst >=2 minor -> gap; sonst ok.
"""

from __future__ import annotations

import re

from ..models import DimensionVerdict


# Anker-gebundene Regex (kein ReDoS, T-03-01): exakt "robots" als name-Attribut.
_ROBOTS_NAME = re.compile(r"^robots$", re.I)

_TITLE_MIN, _TITLE_MAX = 10, 70
_DESC_MIN, _DESC_MAX = 50, 160


def analyze(fr, soup) -> DimensionVerdict:
    """Reiner Dimension-4-Befund über `FetchResult` + vor-geparste soup."""
    # no-HTML-Policy: erreichbar-aber-kein-Body -> NEUTRAL (0 Gap-Punkte),
    # KEIN severe/gap, sonst kippt ein WAF-Block fälschlich auf Bedarf 5.
    if soup is None:
        return DimensionVerdict(4, "ok", "nicht bewertbar (kein HTML)", "n/a")

    severe: list[str] = []
    gap: list[str] = []
    minor: list[str] = []

    # ---- noindex (Meta-Robots ODER X-Robots-Tag-Header) -> severe ----
    m = soup.find("meta", attrs={"name": _ROBOTS_NAME})
    if m and "noindex" in (m.get("content") or "").lower():
        severe.append("noindex (Meta-Robots)")
    xrt = next((v for k, v in fr.headers.items() if k.lower() == "x-robots-tag"), "")
    if "noindex" in (xrt or "").lower():
        severe.append("noindex (X-Robots-Tag-Header)")

    # ---- Title ----
    title = soup.title.get_text(strip=True) if soup.title else ""
    if not title:
        gap.append("kein Title")
    elif not (_TITLE_MIN <= len(title) <= _TITLE_MAX):
        minor.append("Title-Länge ausserhalb 10–70")

    # ---- Meta-Description ----
    desc_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    desc = (desc_tag.get("content") or "").strip() if desc_tag else ""
    if not desc:
        gap.append("keine Meta-Description")
    elif not (_DESC_MIN <= len(desc) <= _DESC_MAX):
        minor.append("Meta-Description-Länge ausserhalb 50–160")

    # ---- H1 ----
    n_h1 = len(soup.find_all("h1"))
    if n_h1 == 0:
        gap.append("0× H1")
    elif n_h1 > 1:
        minor.append(f"{n_h1}× H1 (mehrfach)")

    # ---- Canonical ----
    if not soup.find("link", rel=lambda v: v and "canonical" in v):
        minor.append("kein Canonical")

    # ---- html lang ----
    if not (soup.html and soup.html.get("lang")):
        minor.append("kein html-lang")

    # ---- Pattern-2-Faltung ----
    if severe:
        return DimensionVerdict(4, "severe", "; ".join(severe), "html")
    if gap or len(minor) >= 2:
        notes = gap + minor
        return DimensionVerdict(4, "gap", "; ".join(notes), "html")
    if minor:
        return DimensionVerdict(4, "ok", "; ".join(minor), "html")
    return DimensionVerdict(4, "ok", "Title, Meta-Description, H1 vorhanden", "html")
