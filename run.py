#!/usr/bin/env python3
"""Bequemer Einstiegspunkt: `python run.py data/sample_input.xlsx -o output/leads.xlsx`."""

from lead_analyzer.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
