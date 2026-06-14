"""Score-Aggregation + stabiler Sort.

Phase 1: nur der verlustfreie Sort + ein trivialer Platzhalter-Score, damit die
End-to-End-Pipeline läuft. Die echte 6-Dimensionen-Aggregation kommt in Phase 3.
"""

from __future__ import annotations

from .models import RowRecord, RowResult


def clamp_score(value: int) -> int:
    """Hält einen Score hart im erlaubten Bereich 1..5 (AC2: ganzzahlig 1–5)."""
    return max(1, min(5, int(round(value))))


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
