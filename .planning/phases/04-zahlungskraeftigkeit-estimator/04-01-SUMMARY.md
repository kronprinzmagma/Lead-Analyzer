---
phase: 04-zahlungskraeftigkeit-estimator
plan: 01
subsystem: scoring
tags: [tdd-red, zahlungskraeftigkeit, models]
requires: []
provides: [PaymentEstimate, test_payment.py]
affects: [lead_analyzer/models.py]
tech-stack:
  added: []
  patterns: [dataclass-data-carrier, red-test-matrix]
key-files:
  created: [tests/test_payment.py]
  modified: [lead_analyzer/models.py]
decisions:
  - "PaymentEstimate is a pure data carrier; logic lives in payment.py (Plan 02)"
  - "resolved-predicate pinned: a SOLE ['Branche unbekannt'] note is NOT resolution"
metrics:
  duration: ~5min
  completed: 2026-06-14
---

# Phase 4 Plan 01: Zahlungskräftigkeit RED Matrix Summary

RED phase: added the `PaymentEstimate` data carrier to models.py and wrote the full
failing test matrix (`tests/test_payment.py`, 13 tests) pinning groups A/B/C, combine map,
conservative default, Pitfall-16 legal-form misfires, direction and range — before any
implementation.

## What was built

- `PaymentEstimate(zahl, reason, signals=[])` dataclass in models.py (German docstring, CITED).
- `tests/test_payment.py`: 13 test functions covering ZK-01 (A/B/C + combine), ZK-02 (reason
  labelled + conservative default incl. unknown-branche guard + all four Pitfall-16 misfires
  Magazin/Sagi/Casa/Sava + Marco "& Co" guard), ZK-03 (direction monotone), AC2 (range).

## Verification

- `python -m pytest tests/test_payment.py` → RED (ImportError, payment.py absent) as expected.
- `python -c "from lead_analyzer.models import PaymentEstimate"` → succeeds.
- 135 prior tests unaffected by the models.py edit.
- grep gates: 13 test_ funcs (≥12), 8 misfire matches (≥4), 4 Raumfahrt (≥1).

## Deviations from Plan

None - plan executed exactly as written. Module written as one file (RED collection error
is the intended signal).

## Self-Check: PASSED
- tests/test_payment.py exists; PaymentEstimate importable; commits present.
