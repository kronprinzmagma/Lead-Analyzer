"""Orchestrator: Datei einlesen -> Zeilen bewerten -> sortieren -> Datei schreiben.

Bewertung pro Zeile (analyze_row): URL normalisieren -> fetch (wirft nie) -> HTML
GENAU EINMAL parsen (parse-once) -> die geteilte soup an alle HTML-Dimensionen
reichen (Dim 1 existence, Dim 4 seo, Dim 5 ai_readiness, Dim 6 content); Dim 2
technical misst aus dem FetchResult (auch ohne Body); Dim 3 ist der PageSpeed-
Platzhalter (Phase 6). Die sechs Verdicts -> scoring.bedarf (dead -> 5, sonst
G/S-Bänder) und reasons.build (Begründungsspalte/NACH-01). `zahl` bleibt auf dem
Phase-1-Platzhalter (Phase 4 ersetzt). Alles in einer Per-Row-Boundary: eine
kaputte Zeile killt den Lauf nicht (AC4/ROB-03).
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from . import fetch, reasons, scoring, table_io
from .analyzers import ai_readiness, content, existence, seo, technical
from .config import Config
from .models import RowRecord, RowResult


def _zahl_placeholder(record: RowRecord) -> int:
    """Zahlungskräftigkeit bleibt in Phase 2 auf dem Phase-1-Platzhalter (Phase 4 ersetzt)."""
    return scoring.placeholder_result(record).zahl


def analyze_row(record: RowRecord, url_col: str, config: Config) -> RowResult:
    """Bewertet eine Zeile über alle sechs Dimensionen — netz-robust, wirft nie.

    Ablauf: URL normalisieren -> leer? Bedarf 5 'keine Website' OHNE Netz; sonst
    fetch (wirft nie) -> HTML EINMAL parsen -> die geteilte soup an Dim 1/4/5/6,
    Dim 2 aus dem FetchResult, Dim 3 Platzhalter. Die sechs Verdicts -> scoring.bedarf
    (dead -> 5, sonst G/S-Bänder) und reasons.build (Begründung). `zahl` bleibt
    Platzhalter. Alles in einer Per-Row-Boundary (AC4/ROB-03): eine kaputte Zeile
    killt den Lauf nicht.
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
        # parse-once: eine soup pro Zeile, geteilt von allen HTML-Dimensionen.
        # Bei unlesbarem Body (None) bleiben Dim 4/5/6 neutral (0 Gap-Punkte) ->
        # ein 403/Block kippt NICHT auf Bedarf 5 (Invariante by construction).
        soup = BeautifulSoup(fr.html, "html.parser") if fr.html else None
        verdicts = [
            existence.analyze(fr, soup),             # Dim 1 (kann dead setzen)
            technical.analyze(fr),                   # Dim 2 (auch ohne Body messbar)
            scoring.DIM3_PLACEHOLDER,                # Dim 3 (fix ok, Phase 6)
            seo.analyze(fr, soup),                   # Dim 4 (neutral wenn soup None)
            ai_readiness.analyze(soup),              # Dim 5 (neutral wenn soup None)
            content.analyze(fr, soup),               # Dim 6 (neutral wenn soup None)
        ]
        bedarf = scoring.bedarf(verdicts)            # dead -> 5, sonst G/S-Bänder
        return RowResult(
            record.index, bedarf=bedarf, zahl=_zahl_placeholder(record),
            reason=reasons.build(verdicts), verdicts=verdicts,
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
