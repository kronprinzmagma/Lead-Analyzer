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
- Felddaten vor Labor (seit 2026-11-19): Enthält das PsResult Werte echter
  Chrome-Besucher (CrUX: LCP, INP, CLS), zählen NUR diese; die simulierte
  Labormessung dient dann nicht mehr als Note. Ohne Felddaten (kleine Seiten
  mit wenig Besuchern) gilt das Labor wie bisher.
- Alle Verdicts: dim == 3.

[CITED: 06-RESEARCH.md Pattern 2 "PSI-error-is-not-slow", Pattern 3
 "Lighthouse band mapping"; FEATURES.md Dim 3 Schwellenwerte]
"""

from __future__ import annotations

import re

from ..models import DimensionVerdict


# Anker-gebundene Regex (kein ReDoS): exakt "viewport" als name-Attribut.
_VIEWPORT_NAME = re.compile(r"^viewport$", re.I)

# Band-Ordnung für worst-metric-wins (höher = schlechter).
_BAND_RANK = {"ok": 0, "gap": 1, "severe": 2}

# Lighthouse-Schwellen je Metrik: (ok-Grenze, gap-Grenze). <= ok-Grenze -> "ok",
# <= gap-Grenze -> "gap", sonst -> "severe". perf_score ist invers (höher = besser)
# und wird gesondert behandelt. [CITED: FEATURES.md Dim 3 / 06-RESEARCH Pattern 3]
_THRESHOLDS = {
    "lcp_ms": (2500, 4000),   # Largest Contentful Paint (ms)
    "cls": (0.10, 0.25),      # Cumulative Layout Shift
    "tbt_ms": (200, 600),     # Total Blocking Time (ms)
}


def _has_viewport_meta(soup) -> bool:
    """True gdw. soup vorhanden ist UND ein `<meta name="viewport">` mit
    nicht-leerem content-Attribut existiert (name case-insensitiv)."""
    if soup is None:
        return False
    m = soup.find("meta", attrs={"name": _VIEWPORT_NAME})
    if not m:
        return False
    return bool((m.get("content") or "").strip())


def _worse(a: str, b: str) -> str:
    """Gibt das schlechtere zweier Bänder zurück (severe > gap > ok)."""
    return a if _BAND_RANK[a] >= _BAND_RANK[b] else b


def _band_for(value: float, ok_max: float, gap_max: float) -> str:
    """Direkte Metrik (niedriger = besser) in ein Band einsortieren."""
    if value <= ok_max:
        return "ok"
    if value <= gap_max:
        return "gap"
    return "severe"


# Core-Web-Vitals-Schwellen für Felddaten (75. Perzentil), offizielle Grenzen von
# Google: "good" -> ok, "needs improvement" -> gap, "poor" -> severe.
# [CITED: web.dev/articles/vitals — LCP 2.5/4 s, INP 200/500 ms, CLS 0.1/0.25]
_FIELD_THRESHOLDS = {
    "field_lcp_ms": (2500, 4000),
    "field_inp_ms": (200, 500),
    "field_cls": (0.10, 0.25),
}


def _field_bands(r) -> list[str]:
    """Bänder aller vorhandenen Feld-Metriken; leer = keine Felddaten."""
    bands: list[str] = []
    for field, (ok_max, gap_max) in _FIELD_THRESHOLDS.items():
        value = getattr(r, field, None)
        if value is not None:
            bands.append(_band_for(value, ok_max, gap_max))
    return bands


def _field_reason(r) -> str:
    """Kurztext der Feldwerte fürs Log, z. B. 'LCP 2.4 s, INP 279 ms, CLS 0.33'."""
    parts = []
    if getattr(r, "field_lcp_ms", None) is not None:
        parts.append(f"LCP {r.field_lcp_ms / 1000:.1f} s")
    if getattr(r, "field_inp_ms", None) is not None:
        parts.append(f"INP {r.field_inp_ms:.0f} ms")
    if getattr(r, "field_cls", None) is not None:
        parts.append(f"CLS {r.field_cls:.2f}")
    return ", ".join(parts)


def _band_from_lighthouse(r) -> str:
    """Schlechtestes Band über alle VORHANDENEN Metriken (worst-metric-wins).

    Fehlende (None) Metriken werden übersprungen — kein Penalty (T-06-07). Sind
    alle Metriken None, gibt es keinen Anhaltspunkt -> "ok" (nicht abstrafen)."""
    bands: list[str] = []

    # perf_score ist invers (höher = besser): >=0.90 ok / >=0.50 gap / sonst severe.
    if r.perf_score is not None:
        if r.perf_score >= 0.90:
            bands.append("ok")
        elif r.perf_score >= 0.50:
            bands.append("gap")
        else:
            bands.append("severe")

    # Direkte Metriken (niedriger = besser) per Schwellen-Tabelle.
    for field, (ok_max, gap_max) in _THRESHOLDS.items():
        value = getattr(r, field)
        if value is not None:
            bands.append(_band_for(value, ok_max, gap_max))

    if not bands:
        return "ok"
    return max(bands, key=lambda b: _BAND_RANK[b])


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

    # --- Felddaten echter Besucher haben Vorrang vor dem Labor ---
    field_bands = _field_bands(ps_result)
    if field_bands:
        level = max(field_bands, key=lambda b: _BAND_RANK[b])
        if not has_viewport:
            level = _worse(level, "gap")
        scope = getattr(ps_result, "field_scope", None) or "Seite"
        reason = (
            f"echte Besucher (CrUX, 28 Tage, {scope}): {_field_reason(ps_result)}"
            + ("" if has_viewport else "; kein viewport-meta")
        )
        return DimensionVerdict(3, level, reason, "crux")

    # --- Keine Felddaten: Lighthouse-Laborbänder (worst-metric-wins) ---
    level = _band_from_lighthouse(ps_result)
    # Fehlender viewport ist mindestens ein gap, auch bei guten PSI-Werten.
    if not has_viewport:
        level = _worse(level, "gap")
    # None-Guard im f-string (T-06-07): perf_score kann None sein.
    perf = f"{ps_result.perf_score:.2f}" if ps_result.perf_score is not None else "n/a"
    reason = (
        f"PageSpeed Labor mobile perf={perf} (keine Felddaten)"
        + ("" if has_viewport else "; kein viewport-meta")
    )
    return DimensionVerdict(3, level, reason, "pagespeed")
