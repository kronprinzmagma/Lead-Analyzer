---
phase: 09-mywebsite-sales-arguments-sheet
plan: "01"
subsystem: output
tags: [sales-enablement, xlsx, second-sheet, mapping, offline, deterministic]
dependency_graph:
  requires: [lead_analyzer/models.py, lead_analyzer/reasons.py, lead_analyzer/table_io.py]
  provides: [lead_analyzer/mywebsite.py, second-sheet myWEBSITE-Argumente, companion CSV]
  affects: [lead_analyzer/table_io.py, lead_analyzer/pipeline.py]
tech_stack:
  added: [openpyxl.styles.Alignment (wrap_text)]
  patterns: [pure-module builder, verbatim-mapping constant, TDD Wave-0 RED/GREEN]
key_files:
  created:
    - lead_analyzer/mywebsite.py
    - tests/test_mywebsite.py
    - tests/test_table_io.py
  modified:
    - lead_analyzer/table_io.py
    - lead_analyzer/pipeline.py
decisions:
  - "Mapping copied verbatim from 09-RESEARCH.md; single source of truth is the module-level _MAPPING constant"
  - "Driver predicate identical to reasons.build ([v for v in verdicts if v.level != 'ok' or v.dead]) so Begründung and argument sheet can never disagree (NACH-01)"
  - "url_col threaded via optional kwarg url_col=None to write_output → backward compatible with all existing callers"
  - "CSV companion written in _write_csv unconditionally when CSV path is used (parity with xlsx)"
  - "Empty verdicts + bedarf=5 (broken/empty URL paths) → dim-1 argument to ensure sales sheet is never blank for the worst leads"
metrics:
  duration: "~15 min"
  completed: "2026-06-15"
  tasks_completed: 3
  files_changed: 5
---

# Phase 09 Plan 01: myWEBSITE Sales Arguments Sheet — Summary

**One-liner:** Deterministic second xlsx sheet "myWEBSITE-Argumente" that reframes each company's non-ok dimension verdicts into positive myWEBSITE sales arguments via a verbatim 6-row mapping constant — no LLM, no network, fully traceable to the same verdict drivers as the Begründung column.

## What Was Built

A pure sales-enablement presentation layer on top of the existing `RowResult.verdicts` data:

1. **`lead_analyzer/mywebsite.py`** (NEW, 135 lines): Module-level `_MAPPING` constant with verbatim dim 1..6 text from 09-RESEARCH.md; `NO_DEFICIT_NOTE` constant for the honest no-deficit case; `build_arguments(record, result, url_value)` → `(kundenname, defizite_text, funktionen_text)`. Pure, exception-free, no I/O.

2. **`lead_analyzer/table_io.py`** (modified): Added `SHEET_ARGUMENTE = "myWEBSITE-Argumente"` and `ARG_HEADERS`; `write_output()` accepts new optional `url_col=None`; `_write_xlsx()` creates the second sheet after the Leads sheet (byte-unchanged); `_write_csv()` writes a companion `{stem}_argumente.csv`.

3. **`lead_analyzer/pipeline.py`** (modified, 1 line): Passes `url_col=url_col` to `write_output()` (url_col already in scope).

4. **`tests/test_mywebsite.py`** (NEW, 11 tests): Unit tests for all 6 dimensions, edge cases (empty verdicts + bedarf=5, all-ok, name fallbacks), and NACH-01 driver parity.

5. **`tests/test_table_io.py`** (NEW, 5 tests): Integration tests for second-sheet structure, sorted-order parity, Leads-sheet regression, and CSV companion.

## TDD Gate Compliance

- RED commit `83d0c13`: `test(09-01)` — both test files written before any implementation; import fails `ModuleNotFoundError`.
- GREEN commit `7ccb4cd`: `feat(09-01)` — `mywebsite.py` implemented; 11/11 unit tests pass.
- GREEN commit `b2d82ed`: `feat(09-01)` — table_io + pipeline wired; all 16 new tests pass; Leads sheet unchanged.

## Deviations from Plan

None — plan executed exactly as written.

## Test Results

| Suite | Before | After | Delta |
|-------|--------|-------|-------|
| Full suite | 219 | 235 | +16 |
| test_mywebsite.py | — | 11 | +11 |
| test_table_io.py | — | 5 | +5 |
| test_phase1_io.py | 11 | 11 | 0 (regression guard green) |

## Verification Against Success Criteria

- **DIFF-04**: Second worksheet "myWEBSITE-Argumente" confirmed — `wb.sheetnames == ['Leads', 'myWEBSITE-Argumente']` on sample run (42 rows processed).
- **NACH-01**: Driver predicate `[v for v in verdicts if v.level != 'ok' or v.dead]` copied verbatim from `reasons.py`; test `test_deficits_match_reason_drivers` enforces parity.
- **Edge case (empty verdicts + bedarf=5)**: Nähatelier Sutter and Kiosk am Lindenplatz correctly get dim-1 "Keine/defekte Website" argument.
- **No-deficit case**: All-ok companies get `NO_DEFICIT_NOTE`; no invented deficit.
- **Leads sheet unchanged**: `test_leads_sheet_unchanged` passes; existing `test_phase1_io.py` assertions all green.
- **CSV companion**: `test_csv_companion_argumente` and `test_csv_output_companion_argumente` pass.
- **Offline/deterministic**: No network calls, no LLM, pure constant mapping.

## Known Stubs

None.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries. The second sheet only restates pre-computed deficit labels plus static product-feature constants (T-09-03 accepted).

## Self-Check: PASSED

- `lead_analyzer/mywebsite.py`: FOUND
- `tests/test_mywebsite.py`: FOUND
- `tests/test_table_io.py`: FOUND
- `lead_analyzer/table_io.py`: FOUND (modified)
- `lead_analyzer/pipeline.py`: FOUND (modified)
- Commit `83d0c13` (RED): FOUND
- Commit `7ccb4cd` (GREEN mywebsite.py): FOUND
- Commit `b2d82ed` (GREEN table_io + pipeline): FOUND
- Full suite: 235 passed
