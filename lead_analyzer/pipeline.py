"""Orchestrator: Datei einlesen -> Zeilen bewerten -> sortieren -> Datei schreiben.

Bewertung pro Zeile (analyze_row): URL normalisieren -> fetch (wirft nie) -> HTML
GENAU EINMAL parsen (parse-once) -> die geteilte soup an alle HTML-Dimensionen
reichen (Dim 1 existence, Dim 4 seo, Dim 5 ai_readiness, Dim 6 content); Dim 2
technical misst aus dem FetchResult (auch ohne Body); Dim 3 ist der PageSpeed-
Platzhalter (Phase 6). Die sechs Verdicts -> scoring.bedarf (dead -> 5, sonst
G/S-Bänder) und reasons.build (Begründungsspalte/NACH-01). `zahl` ist ab Phase 4
die echte Zahlungskräftigkeit-Schätzung (payment.estimate) auf ALLEN drei Pfaden —
normal, leere-URL, Exception-Boundary. Alles in einer Per-Row-Boundary: eine
kaputte Zeile killt den Lauf nicht (AC4/ROB-03).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup

from . import fetch, reasons, scoring, table_io
from .analyzers import ai_readiness, content, existence, payment, seo, technical
from .config import Config
from .models import RowRecord, RowResult


def analyze_row(record: RowRecord, url_col: str, config: Config) -> RowResult:
    """Bewertet eine Zeile über alle sechs Dimensionen — netz-robust, wirft nie.

    Ablauf: URL normalisieren -> leer? Bedarf 5 'keine Website' OHNE Netz; sonst
    fetch (wirft nie) -> HTML EINMAL parsen -> die geteilte soup an Dim 1/4/5/6,
    Dim 2 aus dem FetchResult, Dim 3 Platzhalter. Die sechs Verdicts -> scoring.bedarf
    (dead -> 5, sonst G/S-Bänder) und reasons.build (Begründung). `zahl` ist die echte
    payment.estimate-Schätzung — auch auf dem leere-URL- und dem Exception-Pfad
    (aus Name/Branche, netzlos). Die Bedarf-Logik ist UNVERÄNDERT. Alles in einer
    Per-Row-Boundary (AC4/ROB-03): eine kaputte Zeile killt den Lauf nicht.
    """
    try:
        raw = record.cells.get(url_col)
        candidates = fetch.normalize(raw)
        if candidates is None:                       # leere URL -> KEIN Netz
            # zahl trotzdem echt schätzen (Name/Branche brauchen kein Netz); die
            # Begründung trägt 'keine Website' (Bedarf) plus die zahl-Schätzung.
            est = payment.estimate(record, None, None, config)
            return RowResult(
                record.index, bedarf=5, zahl=est.zahl,
                reason=f"keine Website | {est.reason}",
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
        est = payment.estimate(record, fr, soup, config)   # echte Zahlungskräftigkeit
        return RowResult(
            record.index, bedarf=bedarf, zahl=est.zahl,
            reason=reasons.build(verdicts, payment=est), verdicts=verdicts,
        )
    except Exception as e:                            # AC4-Boundary — der Lauf geht weiter
        # zahl defensiv schätzen — darf INNERHALB der Boundary NIE re-raisen.
        try:
            est = payment.estimate(record, None, None, config)
            zahl, zreason = est.zahl, est.reason
        except Exception:
            zahl, zreason = 2, "Zahl (Schätzung): nicht ermittelbar"   # konservativ, AC4
        return RowResult(
            record.index, bedarf=5, zahl=zahl,
            reason=f"Fehler: {type(e).__name__} | {zreason}",
        )


def run(config: Config) -> dict:
    """Führt den kompletten Lauf aus. Gibt eine kleine Zusammenfassung zurück."""
    headers, records = table_io.read_rows(config.input)
    url_col = table_io.detect_url_column(headers)  # wirft InputError bei Fehlen (AC2/AC4)

    if config.limit is not None:
        records = records[: config.limit]

    # PERF-03: I/O-bound fan-out über Threads. Jeder Future schreibt GENAU einen
    # festen Index (futs[fut]) -> keine geteilte mutable Stelle (T-05-05). analyze_row
    # wirft NIE (eigene Boundary), darum kann fut.result() nicht re-raisen (T-05-06).
    # Der stabile Sort (Tiebreaker index) macht das Output unabhängig von der
    # Completion-Reihenfolge -> workers=1 und workers=8 liefern identische Zeilen (AC1).
    results: list[RowResult | None] = [None] * len(records)
    workers = max(1, getattr(config, "workers", 8))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(analyze_row, r, url_col, config): i
                for i, r in enumerate(records)}
        for fut in as_completed(futs):
            i = futs[fut]
            results[i] = fut.result()
    # Echte Checks (kein assert — würde unter `python -O` verschwinden und die
    # AC1/AC2-Garantie "keine Zeile verloren" still aushebeln, Review M1).
    if any(r is None for r in results):
        raise RuntimeError("Pool hat eine Zeile verloren!")

    pairs = list(zip(records, results))
    ordered = scoring.stable_sort(pairs)

    # AC2-Invariante: keine Zeile verloren.
    if len(ordered) != len(records):
        raise RuntimeError("Sort hat Zeilen verloren/dupliziert!")

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
