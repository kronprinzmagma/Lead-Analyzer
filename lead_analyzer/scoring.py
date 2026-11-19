"""Score-Aggregation + stabiler Sort.

Die echte 6-Dimensionen-Aggregation (Phase 3) lebt jetzt in `bedarf()`. Die
Phase-1/2-Helfer (clamp_score, bedarf_from_dim1, placeholder_result, stable_sort)
bleiben bis zur Pipeline-Migration (03-04) erhalten, damit deren Tests grün bleiben.
"""

from __future__ import annotations

from .models import DimensionVerdict, RowRecord, RowResult


# --------------------------------------------------------------------------- #
# Echte 6-Dimensionen-Aggregation (Phase 3, BED-07/BED-08)                     #
# --------------------------------------------------------------------------- #

# Dimension 3 (Mobile & Performance) braucht die PageSpeed-Insights-API und kommt
# erst in Phase 6. Bis dahin ein neutraler Platzhalter (level="ok" -> 0 Gap-Punkte,
# harmlos für die Aggregation). Phase 6 ersetzt genau diese eine Zeile durch den
# echten PageSpeed-Befund.
DIM3_PLACEHOLDER = DimensionVerdict(
    3, "ok", "Performance: erst Phase 6 (PageSpeed)", "heuristic-fallback"
)  # [CITED: 03-RESEARCH.md Dim-3-Entscheid]

_POINTS = {"ok": 0, "gap": 1, "severe": 2}


def bedarf(verdicts: list[DimensionVerdict]) -> int:
    """Deterministische 6-Dimensionen-Aggregation -> 1..5 (BED-07/BED-08).

    dead-Override (keine/defekte Website) hat höchste Priorität (-> 5). Sonst
    Gap-Punkte G + Severe-Anzahl S -> Bänder gemäss docs/scoring_website_bedarf.md.
    Tie-Break = max(G-Band, S-Band) -> monoton (AC3): jede zusätzliche Lücke kann
    den Score nur heben oder halten.
    """
    if any(v.dead for v in verdicts):
        return 5
    G = sum(_POINTS[v.level] for v in verdicts)
    S = sum(1 for v in verdicts if v.level == "severe")
    g_score = 5 if G >= 7 else 4 if G >= 4 else 3 if G >= 2 else 2 if G == 1 else 1
    s_score = 5 if S >= 3 else 4 if S == 2 else 3 if S == 1 else 1
    score = max(g_score, s_score)
    # Fehlt einer sonst guten Seite NUR das strukturierte Markup (Dim 5, heuristisch
    # gemessen), hebt das den Bedarf höchstens auf 2 (Entscheid Nils 2026-11-19).
    lacking = [v for v in verdicts if v.level != "ok"]
    if lacking and all(v.dim == 5 for v in lacking):
        score = min(score, 2)
    return score


def bewertbar(verdicts: list[DimensionVerdict]) -> bool:
    """False, wenn ein Befund die Seite als nicht bewertbar markiert (Abruf blockiert).

    Dann gibt es keine Bedarf-Note, sondern den Vermerk «nicht bewertbar»
    (Entscheid Nils 2026-11-19; Ausnahme zu AC2).
    """
    return not any(v.unbewertbar for v in verdicts)


NICHT_BEWERTBAR = "nicht bewertbar"


def clamp_score(value: int) -> int:
    """Hält einen Score hart im erlaubten Bereich 1..5 (AC2: ganzzahlig 1–5)."""
    return max(1, min(5, int(round(value))))


def bedarf_from_dim1(verdict: DimensionVerdict) -> int:
    """Provisorische Bedarf-Ableitung aus dem Dimension-1-Befund (Phase 2).

    # deprecated: superseded by bedarf(); kept for Phase-2 unit tests.

    - `dead`-Flag (keine/defekte/geparkte Website) -> 5 (Override: höchster Bedarf,
      CLAUDE.md §3). Das Flag wird in existence.analyze gesetzt — die Score-Richtung
      hängt damit NICHT am Anzeige-Text (AC3 robust gegen Text-Edits).
    - severe-nicht-tot (z.B. Social-only): Präsenz existiert, aber dünn -> 4.
    - gap / ok: spürbare Lücken bzw. solide -> provisorisch 3, bis Phase 3 die
      echte 6-Dimensionen-Aggregation liefert.
    """
    if verdict.dead:
        return clamp_score(5)
    if verdict.level == "severe":
        return clamp_score(4)
    return clamp_score(3)


def placeholder_result(record: RowRecord) -> RowResult:
    """Trivialer Phase-1-Score (konstant 3/3). Wird ab Phase 2/3 ersetzt."""
    return RowResult(
        index=record.index,
        bedarf=3,
        zahl=3,
        reason="Platzhalter (Phase 1: noch keine echte Bewertung)",
    )


def stable_sort(pairs: list[tuple[RowRecord, RowResult]]) -> list[tuple[RowRecord, RowResult]]:
    """Sortiert absteigend nach Bedarf, dann Zahlungskräftigkeit; Tie-Break = Originalindex.

    Es wird eine Kopie der Ergebnisliste sortiert (nicht die Originalzeilen), und der
    Originalindex als letzter Schlüssel macht den Sort stabil und verlustfrei (AC2).
    """
    # Nicht bewertbare Zeilen (bedarf None) stehen am Schluss, untereinander nach Zahl.
    return sorted(
        pairs,
        key=lambda p: (p[1].bedarf is None, -(p[1].bedarf or 0), -p[1].zahl, p[0].index),
    )
