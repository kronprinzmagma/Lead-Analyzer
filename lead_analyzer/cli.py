"""CLI-Einstiegspunkt: eine Eingabedatei rein -> eine Ausgabedatei raus (AC9)."""

from __future__ import annotations

import argparse
import sys

from .config import Config
from .pipeline import run
from .table_io import InputError


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="lead-analyzer",
        description="MyWEBSITE Lead-Analyzer: Excel/CSV rein, dieselbe Tabelle + "
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
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = Config(
        input=args.input,
        output=args.output,
        limit=args.limit,
        write_csv=args.csv,
        reason_column=not args.no_reason,
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
