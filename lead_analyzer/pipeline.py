"""Orchestrator: Datei einlesen -> Zeilen bewerten -> sortieren -> Datei schreiben.

Phase 1 ist sequenziell und nutzt einen Platzhalter-Score. Thread-Pool, Cache und
die echten Analyzer werden in späteren Phasen hier eingehängt — die Struktur bleibt.
"""

from __future__ import annotations

from . import fetch, scoring, table_io
from .analyzers import existence
from .config import Config
from .models import RowRecord, RowResult


def _zahl_placeholder(record: RowRecord) -> int:
    """Zahlungskräftigkeit bleibt in Phase 2 auf dem Phase-1-Platzhalter (Phase 4 ersetzt)."""
    return scoring.placeholder_result(record).zahl


def analyze_row(record: RowRecord, url_col: str, config: Config) -> RowResult:
    """Bewertet eine Zeile via Dimension 1 — netz-robust, wirft nie (AC4/ROB-03).

    Ablauf: URL normalisieren -> leer? Bedarf 5 'keine Website' OHNE Netz; sonst
    fetch (wirft nie) -> existence.analyze (rein) -> dead-Ursachen überschreiben
    Bedarf auf 5, sonst provisorischer Score. `zahl` bleibt Platzhalter. Alles in
    einer Per-Row-Boundary: eine kaputte Zeile killt den Lauf nicht (Pitfall 1).
    """
    try:
        raw = record.cells.get(url_col)
        candidates = fetch.normalize(raw)
        if candidates is None:                       # leere URL -> KEIN Netz
            return RowResult(
                record.index, bedarf=5, zahl=_zahl_placeholder(record),
                reason="keine Website",
            )
        fr = fetch.fetch(candidates, config)         # wirft nie
        verdict = existence.analyze(fr)              # rein
        bedarf = scoring.bedarf_from_dim1(verdict)   # dead -> 5, sonst provisorisch
        return RowResult(
            record.index, bedarf=bedarf, zahl=_zahl_placeholder(record),
            reason=verdict.reason, verdicts=[verdict],
        )
    except Exception as e:                            # AC4-Boundary — der Lauf geht weiter
        return RowResult(
            record.index, bedarf=5, zahl=_zahl_placeholder(record),
            reason=f"Fehler: {type(e).__name__}",
        )


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
