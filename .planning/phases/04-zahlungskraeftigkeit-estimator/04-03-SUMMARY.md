---
phase: 04-zahlungskraeftigkeit-estimator
plan: 03
subsystem: pipeline
tags: [tdd-green, wire, zahlungskraeftigkeit, reasons]
requires: [payment.estimate, PaymentEstimate]
provides: [analyze_row-wired-zahl, reasons.build-payment-section]
affects: [lead_analyzer/pipeline.py, lead_analyzer/reasons.py]
tech-stack:
  added: []
  patterns: [per-section-cap, defensive-estimate-in-ac4-boundary, single-source-of-truth-reason]
key-files:
  created: []
  modified:
    - lead_analyzer/reasons.py
    - lead_analyzer/pipeline.py
    - tests/test_reasons.py
    - tests/test_pipeline_bedarf.py
    - tests/test_pipeline_dim1.py
decisions:
  - "reasons.build(verdicts, payment=None) back-compatible; per-section cap (160) so zahl reason never truncated"
  - "payment.estimate wired on all three paths: normal, empty-URL, exception-boundary (defensively wrapped)"
  - "_zahl_placeholder removed; scoring.placeholder_result kept for Phase-1 callers"
  - "empty-URL reason = 'keine Website | {est.reason}' (bypasses cap by design; est.reason already short)"
metrics:
  duration: ~6min
  completed: 2026-06-14
---

# Phase 4 Plan 03: Wire Zahlungskräftigkeit through Pipeline Summary

Threaded the Zahlungskräftigkeit estimate through `reasons.build` and `pipeline.analyze_row`,
replacing the `_zahl_placeholder` on every code path. The tool now ranks ideal leads for real:
sort by (bedarf, zahl) distinguishes AG firms from Einzelfirmen, and the Begründung column
carries both rationales (NACH-01/AC6).

## What was built

- `reasons.build(verdicts, payment=None)`: optional payment section, per-section cap (`_MAX_LEN=160`)
  via a `_cap` helper so neither the Bedarf summary nor the "Zahl (Schätzung):" prefix is truncated.
- `pipeline.analyze_row`: `payment.estimate` called on all three paths — normal (with fr+soup),
  empty-URL early return (`f"keine Website | {est.reason}"`), and the AC4 exception boundary
  (estimate wrapped in try/except → conservative 2, never re-raises). bedarf logic unchanged.
- Tests: 3 new reasons tests; new test_pipeline_bedarf tests (real-estimate normal, thin,
  empty-URL name-based zahl, exception-boundary zahl); reconciled the three stale
  `res.reason == "keine Website"` exact-asserts to substring; reconciled both
  test_pipeline_dim1 placeholder assertions + test_pipeline_bedarf to the real estimate;
  test_reason_is_reasons_build pinned to exact payment-aware equality.

## Verification

- `python -m pytest -q` → 154 passed (full suite green).
- grep gates: 0 stale `zahl == scoring.placeholder_result` asserts; dim1 payment.estimate×2 (≥2);
  pipeline payment.estimate×5 (≥3); pipeline _zahl_placeholder×0; reasons payment=None×1 (≥1).
- Live integration: `python run.py data/sample_input.xlsx -o output/phase4_check.xlsx` → 42 rows,
  every zahl int∈[1,5], AGs (zahl 5) outrank Einzelfirmen, edge rows carry real name/branch zahl.

## Sample evidence (live run)

| Kunde | Bedarf | Zahl | Begründung (gekürzt) |
|-------|--------|------|----------------------|
| Lippuner Immobilien & Verwaltungen AG | 4 | 5 | … \| Zahl (Schätzung): Rechtsform AG aus Firmenname angenommen |
| KMU Treuhandexperte GmbH | 4 | 5 | … \| Zahl (Schätzung): Rechtsform GmbH … |
| Oerlikon Zahnarzt | 4 | 4 | … \| Zahl (Schätzung): Branchen-Tier (Annahme): Zahnarzt → hoch |
| Nähatelier Sutter (broken URL) | 5 | 2 | … \| Zahl (Schätzung): Branchen-Tier (Annahme): Handwerk → mittel |
| Kiosk am Lindenplatz (empty URL) | 5 | 1 | keine Website \| Zahl (Schätzung): Branchen-Tier (Annahme): Detailhandel → tief |

Edge rows carry a real name/branch zahl (1, 2), not the old placeholder 3.

## Threat Mitigations Applied

- T-04-04 (run abort): estimate inside the AC4 boundary wrapped in try/except → conservative 2.
- T-04-05 (info disclosure): reason carries only labelled "Zahl (Schätzung)" notes + error type.

## Deviations from Plan

**1. [Rule 1 - reconciliation] Three stale `res.reason == "keine Website"` exact asserts**
- **Found during:** Task 2 (after wiring the empty-URL reason to carry the zahl section).
- **Issue:** The plan changes the empty-URL reason to `"keine Website | {est.reason}"`, but three
  pre-existing tests (test_pipeline_dim1 test_empty_url_no_network + test_empty_string_url_no_network,
  test_pipeline_bedarf test_empty_url_is_5_no_network) asserted exact equality with "keine Website".
- **Fix:** Repointed all three to substring (`"keine Website" in res.reason`), consistent with the
  plan's reconciliation intent (the zahl rationale must stay visible on the empty-URL path).
- **Files modified:** tests/test_pipeline_dim1.py, tests/test_pipeline_bedarf.py
- **Commit:** wired in the Task-2 commit.

## Self-Check: PASSED
- reasons.py/pipeline.py edits present; full suite green (154); live run produced output/phase4_check.xlsx.
