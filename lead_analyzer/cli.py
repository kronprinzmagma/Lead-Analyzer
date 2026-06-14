"""CLI-Einstiegspunkt: eine Eingabedatei rein -> eine Ausgabedatei raus (AC9)."""

from __future__ import annotations

import argparse
import sys

from .config import Config, load_dotenv
from .pipeline import run
from .table_io import InputError


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="lead-analyzer",
        description="Lead-Analyzer: Excel/CSV rein, dieselbe Tabelle + "
        "Website-Bedarf (1-5) und Zahlungskräftigkeit (1-5) raus.",
    )
    p.add_argument("input", help="Eingabedatei (.xlsx oder .csv) mit einer URL-Spalte")
    p.add_argument(
        "-o", "--output",
        default="output/leads_scored.xlsx",
        help="Ausgabedatei (.xlsx; .csv möglich). Default: output/leads_scored.xlsx",
    )
    p.add_argument(
        "-n", "--limit", type=int, default=None,
        help="Nur die ersten N Zeilen verarbeiten (für kleinen E2E-Demo-Lauf)",
    )
    p.add_argument("--csv", action="store_true", help="Zusätzlich/als CSV ausgeben")
    p.add_argument(
        "--no-reason", action="store_true",
        help="Begründungs-Spalte weglassen (nur die zwei Score-Spalten)",
    )
    p.add_argument(
        "--workers", type=int, default=8,
        help="Anzahl paralleler Fetch-Threads (Default: 8)",
    )
    p.add_argument(
        "--no-cache", action="store_true",
        help="Cache komplett umgehen (kein Lesen, kein Schreiben)",
    )
    p.add_argument(
        "--no-pagespeed", action="store_true",
        help="PageSpeed-Anreicherung von Dim 3 abschalten (erzwingt Heuristik)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    # .env ZUERST laden — VOR dem Config-Bau, damit from_config (Plan 04) den
    # PAGESPEED_API_KEY aus os.environ sieht. Einziger Aufrufort; setdefault ->
    # ein real exportierter Key gewinnt immer über die Datei (T-06-03).
    load_dotenv()
    args = build_parser().parse_args(argv)
    config = Config(
        input=args.input,
        output=args.output,
        limit=args.limit,
        write_csv=args.csv,
        reason_column=not args.no_reason,
        # Default workers=8 entspricht dem Config-Default (Politeness-Annahme A1).
        workers=args.workers,
        use_cache=not args.no_cache,
        # --no-pagespeed erzwingt PSI aus, unabhängig von Key-Präsenz (Degradations-Gate).
        use_pagespeed=not args.no_pagespeed,
    )
    try:
        summary = run(config)
    except InputError as e:
        print(f"FEHLER: {e}", file=sys.stderr)
        return 2
    except FileNotFoundError as e:
        print(f"FEHLER: Datei nicht gefunden: {e}", file=sys.stderr)
        return 2

    print(
        f"✓ {summary['rows_processed']} Zeilen verarbeitet "
        f"(URL-Spalte: '{summary['url_column']}').\n"
        f"  Ausgabe: {summary['output']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
