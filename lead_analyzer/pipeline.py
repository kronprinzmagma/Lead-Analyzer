"""Orchestrator: Datei einlesen -> Zeilen bewerten -> sortieren -> Datei schreiben.

Phase 1 ist sequenziell und nutzt einen Platzhalter-Score. Thread-Pool, Cache und
die echten Analyzer werden in späteren Phasen hier eingehängt — die Struktur bleibt.
"""

from __future__ import annotations

from . import scoring, table_io
from .config import Config
from .models import RowRecord, RowResult


def analyze_row(record: RowRecord, url_col: str, config: Config) -> RowResult:
    """Bewertet eine einzelne Zeile. Phase 1: Platzhalter.

    Wird nie eine Exception nach aussen werfen (AC4) — ab Phase 2 mit echtem
    try/except-Boundary um die Netz-/Analyse-Logik.
    """
    return scoring.placeholder_result(record)


def run(config: Config) -> dict:
    """Führt den kompletten Lauf aus. Gibt eine kleine Zusammenfassung zurück."""
    headers, records = table_io.read_rows(config.input)
    url_col = table_io.detect_url_column(headers)  # wirft InputError bei Fehlen (AC2/AC4)

    if config.limit is not None:
        records = records[: config.limit]

    results: list[RowResult] = [analyze_row(r, url_col, config) for r in records]

    pairs = list(zip(records, results))
    ordered = scoring.stable_sort(pairs)

    # AC2-Invariante: keine Zeile verloren.
    assert len(ordered) == len(records), "Sort hat Zeilen verloren/dupliziert!"

    table_io.write_output(
        config.output,
        headers,
        ordered,
        reason_column=config.reason_column,
        write_csv=config.write_csv,
    )

    return {
        "input": config.input,
        "output": config.output,
        "url_column": url_col,
        "rows_processed": len(records),
        "headers_in": headers,
    }
