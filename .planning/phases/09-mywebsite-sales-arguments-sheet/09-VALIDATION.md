---
phase: 9
slug: mywebsite-sales-arguments-sheet
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-15
---

# Phase 9 — Validation Strategy

> Per-phase validation contract. Derived from 09-RESEARCH.md "Validation Architecture".
> Fully offline/deterministic — no network, no credentials.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_mywebsite.py tests/test_phase1_io.py -x -q` |
| **Full suite command** | `.venv/bin/python -m pytest -x -q` |
| **Estimated runtime** | ~1 second |

## Sampling Rate
- **After every task commit:** quick command
- **After every plan wave:** full suite (currently 219 tests — must stay green)
- **Before completion:** full suite green

## Per-Task Verification Map

| Req | Behavior | Test | Exists |
|-----|----------|------|--------|
| DIFF-04 | each dimension's gap/severe verdict → its mapped Funktion+Nutzen | `tests/test_mywebsite.py::test_each_dimension_maps` | ❌ W0 |
| DIFF-04 | empty verdicts + bedarf 5 → dim-1 "no website" argument | `tests/test_mywebsite.py::test_empty_verdicts_no_website` | ❌ W0 |
| DIFF-04 | all-ok (Bedarf 1) → "keine akuten Defizite" note, no invented deficit | `tests/test_mywebsite.py::test_no_deficit_note` | ❌ W0 |
| DIFF-04 | Kundenname fallback (no name column → URL/row index) | `tests/test_mywebsite.py::test_name_fallback` | ❌ W0 |
| DIFF-04 | output xlsx has 2 sheets; sheet 2 "myWEBSITE-Argumente" = 3 headers + one row per company in sorted order | `tests/test_table_io.py::test_second_sheet_structure` | ❌ W0 |
| DIFF-04 | "Leads" sheet unchanged (all original cols + 2 scores + order) | existing `tests/test_phase1_io.py` assertions still pass | ✅ |
| NACH-01 | sheet deficits == non-ok/dead verdict drivers (same as reasons.build) | `tests/test_mywebsite.py::test_deficits_match_reason_drivers` | ❌ W0 |

## Wave 0 Requirements
- [ ] `tests/test_mywebsite.py` — mapping + builder unit tests (RED first)
- [ ] second-sheet structure test (`tests/test_table_io.py` or extend `test_phase1_io.py`)

## Manual-Only Verifications
| Behavior | Why Manual | Instructions |
|----------|------------|--------------|
| Sales-readability of the argument cells | subjective wording quality | Open `output/leads.xlsx`, sheet "myWEBSITE-Argumente"; confirm each company's arguments read as positive sales talking points, not deficit lists |

---
*Phase: 09-mywebsite-sales-arguments-sheet — validation derived 2026-06-15 from 09-RESEARCH.md*
