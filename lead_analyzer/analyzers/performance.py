"""Dimension 3 — Mobile & Performance (rein, offline + optionale PSI-Verfeinerung).

`analyze(fr, soup, ps_result=None)` wandelt ein `FetchResult` + vor-geparste
BeautifulSoup (parse-once: baut NIE selbst eine soup) in einen
`DimensionVerdict(dim=3, ...)`. Die Funktion ist rein und offline — der einzige
optionale Input ist ein bereits vorberechnetes `PsResult` (der PSI-Client lebt in
clients/, Phase 06-04); diese Funktion macht selbst KEIN HTTP.

Vertrag (06-RESEARCH Pattern 1/2/3):
- Baseline IMMER aus dem viewport-meta-Tag (HTML-Ebene, offline messbar, AC11):
  vorhanden -> ok, fehlend -> gap.
- INVERSIONS-GUARD (Pitfall 8, T-06-06): `ps_result is None` bedeutet
  "übersprungen ODER Fehler" und wird IDENTISCH behandelt — nur Heuristik, NIE
  `severe`. Ein PSI-Fehler darf eine Seite niemals fälschlich als "langsam"
  abstrafen. Diese Branch steht ZUERST und kann strukturell kein severe liefern.
- Ein echtes PsResult verfeinert: das schlechteste Metrik-Band gewinnt
  (worst-metric-wins); fehlender viewport ist mindestens ein `gap`.
- Alle Verdicts: dim == 3.

[CITED: 06-RESEARCH.md Pattern 2 "PSI-error-is-not-slow", Pattern 3
 "Lighthouse band mapping"; FEATURES.md Dim 3 Schwellenwerte]
"""

from __future__ import annotations

import re

from ..models import DimensionVerdict


# Anker-gebundene Regex (kein ReDoS): exakt "viewport" als name-Attribut.
_VIEWPORT_NAME = re.compile(r"^viewport$", re.I)


def _has_viewport_meta(soup) -> bool:
    """True gdw. soup vorhanden ist UND ein `<meta name="viewport">` mit
    nicht-leerem content-Attribut existiert (name case-insensitiv)."""
    if soup is None:
        return False
    m = soup.find("meta", attrs={"name": _VIEWPORT_NAME})
    if not m:
        return False
    return bool((m.get("content") or "").strip())


def analyze(fr, soup, ps_result=None) -> DimensionVerdict:
    """Reiner Dimension-3-Befund: viewport-Baseline + optionale PSI-Verfeinerung."""
    has_viewport = _has_viewport_meta(soup)

    # --- INVERSIONS-GUARD: kein PSI-Resultat (übersprungen ODER Fehler) ---
    # IDENTISCHE Branch für beide Fälle (Pitfall 8): nur die HTML-Heuristik,
    # strukturell NIE severe. Steht bewusst ZUERST. [CITED: 06-RESEARCH Pattern 2]
    if ps_result is None:
        if has_viewport:
            return DimensionVerdict(
                3, "ok",
                "viewport-meta vorhanden (PageSpeed übersprungen/Fehler)",
                "heuristic-fallback",
            )
        return DimensionVerdict(
            3, "gap",
            "kein viewport-meta (PageSpeed übersprungen/Fehler)",
            "heuristic-fallback",
        )

    # PsResult-Verfeinerung folgt in Task 2 — vorläufig viewport-only.
    if has_viewport:
        return DimensionVerdict(3, "ok", "viewport-meta vorhanden", "heuristic-fallback")
    return DimensionVerdict(3, "gap", "kein viewport-meta", "heuristic-fallback")
