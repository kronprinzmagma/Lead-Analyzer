---
phase: 03-real-website-bedarf-score
plan: 03
subsystem: scoring
tags: [scoring, aggregation, traceability, tdd]
requires: [DimensionVerdict model]
provides: [scoring.bedarf, DIM3_PLACEHOLDER, reasons.build]
affects: [03-04 pipeline wiring]
tech-stack:
  added: []
  patterns: [table-driven tests, single-source-of-truth (reason delegates score to scoring.bedarf), monotonic max(g_score,s_score) tie-break]
key-files:
  created:
    - lead_analyzer/reasons.py
    - tests/test_scoring_bedarf.py
    - tests/test_reasons.py
  modified:
    - lead_analyzer/scoring.py
decisions:
  - "Aggregation uses max(G-band, S-band) tie-break to guarantee monotonicity (AC3/BED-08)"
  - "DIM3_PLACEHOLDER is a neutral ok-verdict so Phase 6 swaps performance in one line"
  - "reasons.build computes the displayed Bedarf via scoring.bedarf so text/score never diverge (T-03-07)"
metrics:
  tasks-completed: 4
  tests-added: 21
  completed: 2026-06-14
---

# Phase 3 Plan 03: Website-Bedarf 6-Dim Aggregation + Reasons Summary

Deterministic, monotonic 6-dimension `scoring.bedarf(verdicts)` (BED-07/BED-08) plus a single-source-of-truth `reasons.build(verdicts)` (NACH-01) — both consume only DimensionVerdicts, so this plan ran fully parallel to 03-01/03-02.

## What was built

- **`scoring.bedarf(verdicts) -> int`** (BED-07/BED-08): dead-override → 5 (highest priority, non-bypassable); else gap-points G (ok=0/gap=1/severe=2) and severe-count S mapped to bands via `max(g_score, s_score)`. The max tie-break makes the score provably monotonic — adding any gap can only raise or hold it. Bands match `docs/scoring_website_bedarf.md` exactly.
- **`DIM3_PLACEHOLDER`**: a named neutral `DimensionVerdict(3, "ok", ..., "heuristic-fallback")` constant. Phase 6 (PageSpeed) swaps this one line; level "ok" = 0 gap-points so it is harmless to aggregation now.
- **`reasons.py / build(verdicts) -> str`** (NACH-01/AC6): compact German string listing only the non-ok (or dead) dimensions with level + driving reason, then appends a Bedarf note computed via `scoring.bedarf` on the same verdicts (cannot diverge from the score — T-03-07). Capped at ~200 chars with graceful truncation.

## Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | test_scoring_bedarf.py | 2d05... (test 03-03) | tests/test_scoring_bedarf.py |
| 2 (GREEN) | scoring.bedarf + DIM3_PLACEHOLDER | feat 03-03 scoring | lead_analyzer/scoring.py |
| 3 (RED) | test_reasons.py | 2d058ec | tests/test_reasons.py |
| 4 (GREEN) | reasons.build | 9416c3c | lead_analyzer/reasons.py |

## Verification

- `tests/test_scoring_bedarf.py`: 16 passed (every band + boundaries, S-overrides, dead-override on first and non-first dim, monotonic worsening gradient all-ok→1 / non-decreasing / all-severe→5, always int in 1..5).
- `tests/test_reasons.py`: 5 passed (all-ok wording, mixed lists only driving dims + reason notes, dead→Bedarf 5, length ≤210, Bedarf number == scoring.bedarf for two distinct cases).
- My tests + the 4 pre-existing baseline files: **85 passed** (21 new + 64 existing). `bedarf_from_dim1` and all Phase-1/2 helpers untouched.

## Deviations from Plan

None — plan executed exactly as written (band logic, tie-break, placeholder, and reason format implemented verbatim from the plan's pinned spec).

## Notes / Out of scope

The full `pytest tests/` run currently fails at *collection* on `tests/test_technical.py`, `tests/test_seo.py`, `tests/test_content.py`. These belong to **parallel plans 03-01/03-02** (Dim 2/4/6 analyzers) that were being written concurrently during this execution and reference not-yet-implemented `lead_analyzer.analyzers` symbols. They are NOT introduced by this plan and are out of scope (this plan imports no analyzers). My scope (scoring/reasons + the 4 baseline files) is fully green. Logged for the 03-04 wiring plan / phase verifier.

## Self-Check: PASSED

- FOUND: tests/test_scoring_bedarf.py, lead_analyzer/scoring.py, tests/test_reasons.py, lead_analyzer/reasons.py
- Commits present in git log (interleaved with parallel-plan commits).
