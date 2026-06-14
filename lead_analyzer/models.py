"""Datenträger-Klassen, die durch die Pipeline reisen.

Das wichtigste Detail für AC2 (keine Originalzeile verlieren) ist `index`: er reist
unverändert von Einlesen bis Schreiben mit, damit der stabile Sort nichts verliert
oder verwürfelt und die Original-Zellen 1:1 ausgegeben werden.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RowRecord:
    """Eine Eingabezeile: Originalposition + Original-Zellen in Original-Reihenfolge."""
    index: int                     # Originalposition — geht nie verloren
    cells: dict[str, object]       # geordnet: Spaltenname -> Originalwert (verbatim)


@dataclass
class DimensionVerdict:
    """Teil-Befund einer der sechs Website-Bedarf-Dimensionen (ab Phase 2/3 gefüllt)."""
    dim: int                       # 1..6
    level: str                     # "ok" | "gap" | "severe"
    reason: str                    # menschenlesbar -> Log + Begründungsspalte
    source: str = "html"           # "html" | "pagespeed" | "llm" | "heuristic-fallback"


@dataclass
class RowResult:
    """Bewertungsergebnis einer Zeile. Beide Scores sind immer 1..5 (AC2: nie leer)."""
    index: int
    bedarf: int                    # 1..5
    zahl: int                      # 1..5
    reason: str = ""               # Kurzbegründung (Begründungsspalte / Log)
    verdicts: list[DimensionVerdict] = field(default_factory=list)  # für Lauf-Log (AC6/AC11)
