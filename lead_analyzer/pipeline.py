"""Orchestrator: Datei einlesen -> Zeilen bewerten -> sortieren -> Datei schreiben.

Bewertung pro Zeile (analyze_row): URL normalisieren -> fetch (wirft nie) -> HTML
GENAU EINMAL parsen (parse-once) -> die geteilte soup an alle HTML-Dimensionen
reichen (Dim 1 existence, Dim 4 seo, Dim 5 ai_readiness, Dim 6 content); Dim 2
technical misst aus dem FetchResult (auch ohne Body); Dim 3 ist ab Phase 6 der
echte Performance-Analyzer (performance.analyze: viewport-Heuristik + optionale
PageSpeed-Insights-Verfeinerung), kein Platzhalter mehr. Die sechs Verdicts -> scoring.bedarf (dead -> 5, sonst
G/S-Bänder) und reasons.build (Begründungsspalte/NACH-01). `zahl` ist ab Phase 4
die echte Zahlungskräftigkeit-Schätzung (payment.estimate) auf ALLEN drei Pfaden —
normal, leere-URL, Exception-Boundary. Alles in einer Per-Row-Boundary: eine
kaputte Zeile killt den Lauf nicht (AC4/ROB-03).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup

from . import fetch, reasons, scoring, table_io
from .analyzers import ai_readiness, content, existence, payment, performance, seo, technical
from .clients.pagespeed import PageSpeedClient
from .clients.zefix import ZefixClient
from .config import Config
from .models import RowRecord, RowResult


def analyze_row(
    record: RowRecord, url_col: str, config: Config, ps_client=None, zx_client=None
) -> RowResult:
    """Bewertet eine Zeile über alle sechs Dimensionen — netz-robust, wirft nie.

    Ablauf: URL normalisieren -> leer? Bedarf 5 'keine Website' OHNE Netz; sonst
    fetch (wirft nie) -> HTML EINMAL parsen -> die geteilte soup an Dim 1/4/5/6,
    Dim 2 aus dem FetchResult, Dim 3 performance.analyze (viewport-Heuristik +
    optionale PageSpeed-Verfeinerung). Die sechs Verdicts -> scoring.bedarf
    (dead -> 5, sonst G/S-Bänder) und reasons.build (Begründung). `zahl` ist die echte
    payment.estimate-Schätzung — auch auf dem leere-URL- und dem Exception-Pfad
    (aus Name/Branche, netzlos). Die Bedarf-Logik ist UNVERÄNDERT. Alles in einer
    Per-Row-Boundary (AC4/ROB-03): eine kaputte Zeile killt den Lauf nicht.

    `ps_client` (Keyword, Default None) ist der pro Lauf EINMAL gebaute, geteilte
    PageSpeed-Client (oder None ohne Key/--no-pagespeed). Der Default None hält
    Direkt-Aufrufe (Tests) rückwärtskompatibel: ohne Client -> ps_result None ->
    Dim 3 fällt auf die viewport-Heuristik zurück (byte-identisch zu Phase 5).

    `zx_client` (Keyword, Default None) ist der pro Lauf EINMAL gebaute, geteilte
    ZefixClient (oder None ohne ZEFIX_USER/ZEFIX_PASSWORD -> byte-identisch zu Phase 7).
    lookup() wirft NIE (Client-Vertrag); nur auf Normal- und Leer-URL-Pfad aufgerufen.
    """
    def _zefix_facts():
        """Zefix-Lookup: None wenn kein Client, Budget erschöpft, Name zu kurz, etc."""
        if zx_client is None or not zx_client.is_available():
            return None
        raw_name = str(record.cells.get("Kundenname") or "")
        canton_hint = str(record.cells.get("Kanton") or "")   # optionale Spalte
        return zx_client.lookup(raw_name, canton_hint or None)  # wirft nie; <3 Zeichen -> None

    try:
        raw = record.cells.get(url_col)
        candidates = fetch.normalize(raw)
        if candidates is None:                       # leere URL -> KEIN Netz
            # zahl trotzdem echt schätzen (Name/Branche brauchen kein Netz); die
            # Begründung trägt 'keine Website' (Bedarf) plus die zahl-Schätzung.
            zefix_facts = _zefix_facts()
            est = payment.estimate(record, None, None, config, zefix_facts=zefix_facts)
            return RowResult(
                record.index, bedarf=5, zahl=est.zahl,
                reason=f"keine Website | {est.reason}",
                zahl_signals=est.signals,
            )
        fr = fetch.fetch(candidates, config)         # wirft nie
        # parse-once: eine soup pro Zeile, geteilt von allen HTML-Dimensionen.
        # Bei unlesbarem Body (None) bleiben Dim 4/5/6 neutral (0 Gap-Punkte) ->
        # ein 403/Block kippt NICHT auf Bedarf 5 (Invariante by construction).
        soup = BeautifulSoup(fr.html, "html.parser") if fr.html else None
        # Dim 3 (Mobile & Performance): PSI nur ANFRAGEN, wenn ein Client da ist,
        # er verfügbar ist (Key + Budget) UND der Fetch nutzbar war (T-06-12: tote/
        # blockierte Zeilen treiben kein Budget). Sonst ps_result None -> Heuristik.
        # score() wirft NIE (Client-Vertrag) -> kein extra try/except nötig.
        ps_result = None
        if ps_client is not None and ps_client.is_available() and fr.ok and fr.html:
            ps_result = ps_client.score(fr.final_url or fr.url)
        verdicts = [
            existence.analyze(fr, soup),             # Dim 1 (kann dead setzen)
            technical.analyze(fr),                   # Dim 2 (auch ohne Body messbar)
            performance.analyze(fr, soup, ps_result),  # Dim 3 (viewport + optional PSI)
            seo.analyze(fr, soup),                   # Dim 4 (neutral wenn soup None)
            ai_readiness.analyze(soup),              # Dim 5 (neutral wenn soup None)
            content.analyze(fr, soup),               # Dim 6 (neutral wenn soup None)
        ]
        bedarf = scoring.bedarf(verdicts)            # dead -> 5, sonst G/S-Bänder
        zefix_facts = _zefix_facts()
        est = payment.estimate(record, fr, soup, config, zefix_facts=zefix_facts)   # echte Zahlungskräftigkeit
        return RowResult(
            record.index, bedarf=bedarf, zahl=est.zahl,
            reason=reasons.build(verdicts, payment=est), verdicts=verdicts,
            zahl_signals=est.signals,
        )
    except Exception as e:                            # AC4-Boundary — der Lauf geht weiter
        # zahl defensiv schätzen — darf INNERHALB der Boundary NIE re-raisen.
        # KEIN Zefix-Lookup hier: wir sind bereits in einer Fehlergrenze (T-08-08).
        try:
            est = payment.estimate(record, None, None, config)
            zahl, zreason, zsignals = est.zahl, est.reason, est.signals
        except Exception:
            zahl, zreason, zsignals = 2, "Zahl (Schätzung): nicht ermittelbar", []   # konservativ, AC4
        return RowResult(
            record.index, bedarf=5, zahl=zahl,
            reason=f"Fehler: {type(e).__name__} | {zreason}",
            zahl_signals=zsignals,
        )


def run(config: Config) -> dict:
    """Führt den kompletten Lauf aus. Gibt eine kleine Zusammenfassung zurück."""
    headers, records = table_io.read_rows(config.input)
    url_col = table_io.detect_url_column(headers)  # wirft InputError bei Fehlen (AC2/AC4)

    if config.limit is not None:
        records = records[: config.limit]

    # SINGLE-CLIENT-INVARIANTE (PERF-02/AC8): GENAU EINEN PSI-Client pro Lauf bauen —
    # nie pro Zeile. Die eine Instanz teilt Semaphore + Budget über alle Worker-Threads.
    # from_config liefert None ohne use_pagespeed/Key -> Offline-Lauf bleibt byte-identisch.
    ps_client = PageSpeedClient.from_config(config)
    zx_client = ZefixClient.from_config(config)   # None ohne ZEFIX_USER/ZEFIX_PASSWORD -> byte-identischer Offline-Lauf

    # PERF-03: I/O-bound fan-out über Threads. Jeder Future schreibt GENAU einen
    # festen Index (futs[fut]) -> keine geteilte mutable Stelle (T-05-05). analyze_row
    # wirft NIE (eigene Boundary), darum kann fut.result() nicht re-raisen (T-05-06).
    # Der stabile Sort (Tiebreaker index) macht das Output unabhängig von der
    # Completion-Reihenfolge -> workers=1 und workers=8 liefern identische Zeilen (AC1).
    results: list[RowResult | None] = [None] * len(records)
    workers = max(1, getattr(config, "workers", 8))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(analyze_row, r, url_col, config, ps_client, zx_client): i
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
        url_col=url_col,
    )

    # Lauf-Log IMMER schreiben — der nachvollziehbare Audit-Trail (AC6) hängt nie
    # an der optionalen Begründungsspalte (Codex-Review Finding 3). Best-Effort:
    # ein Log-Schreibfehler darf den bereits geschriebenen Output nicht entwerten.
    log_path = table_io.run_log_path(config.output)
    try:
        table_io.write_run_log(log_path, url_col, ordered)
    except OSError:
        log_path = None

    return {
        "input": config.input,
        "output": config.output,
        "url_column": url_col,
        "rows_processed": len(records),
        "headers_in": headers,
        "run_log": log_path,
    }
