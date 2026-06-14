"""Score-Aggregation + stabiler Sort.

Phase 1: nur der verlustfreie Sort + ein trivialer Platzhalter-Score, damit die
End-to-End-Pipeline läuft. Die echte 6-Dimensionen-Aggregation kommt in Phase 3.
"""

from __future__ import annotations

from .models import DimensionVerdict, RowRecord, RowResult


def clamp_score(value: int) -> int:
    """Hält einen Score hart im erlaubten Bereich 1..5 (AC2: ganzzahlig 1–5)."""
    return max(1, min(5, int(round(value))))


def bedarf_from_dim1(verdict: DimensionVerdict) -> int:
    """Provisorische Bedarf-Ableitung aus dem Dimension-1-Befund (Phase 2).

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
    return sorted(pairs, key=lambda p: (-p[1].bedarf, -p[1].zahl, p[0].index))
