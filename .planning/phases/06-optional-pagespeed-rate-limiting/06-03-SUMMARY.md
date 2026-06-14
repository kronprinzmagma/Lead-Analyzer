---
phase: 06-optional-pagespeed-rate-limiting
plan: 03
subsystem: analyzers
tags: [dim-3, performance, pagespeed, viewport, inversion-guard]
requires: [06-01, 06-02]
provides: ["lead_analyzer.analyzers.performance.analyze (Dim-3)"]
affects: ["pipeline wiring (Plan 06-05)"]
tech-stack:
  added: []
  patterns: ["parse-once (consumes shared soup)", "worst-metric-wins band aggregation", "inversion guard (None==not-attempted, never severe)"]
key-files:
  created: ["lead_analyzer/analyzers/performance.py"]
  modified: []
decisions:
  - "ps_result is None branch placed FIRST and structurally cannot return severe (T-06-06)"
  - "Absent (None) Lighthouse metrics are excluded from the band set, never penalized (T-06-07); all-None -> ok"
  - "perf_score formatted with None-guard (\"n/a\") before f-string interpolation"
metrics:
  duration: "~6 min"
  completed: 2026-06-14
  tasks: 2
  files: 1
---

# Phase 6 Plan 3: analyzers/performance.py (Dim-3) Summary

Pure, offline Dimension-3 (Mobile & Performance) analyzer: viewport-meta baseline that ALWAYS applies, optionally refined by a Lighthouse `PsResult` using exact FEATURES.md band thresholds with worst-metric-wins — guarded so a PSI failure (`ps_result is None`) can never invert a site into "slow".

## What Was Built

- `_has_viewport_meta(soup)` — case-insensitive `<meta name="viewport">` detection requiring non-empty content; `soup=None -> False`.
- `analyze(fr, soup, ps_result=None) -> DimensionVerdict(dim=3, ...)`:
  - **None-branch FIRST (inversion guard, T-06-06):** identical for "skipped" and "error" — viewport present -> `ok`, absent -> `gap`, `source="heuristic-fallback"`, note "(PageSpeed übersprungen/Fehler)". Structurally cannot return `severe`.
  - **PsResult refinement:** `_band_from_lighthouse` collects a band per present metric (perf_score >=0.90 ok / >=0.50 gap / else severe; LCP <=2500/<=4000; CLS <=0.10/<=0.25; TBT <=200/<=600), worst wins; all-None -> `ok`. Missing viewport -> `_worse(level, "gap")`. `source="pagespeed"`, perf_score None-guarded.

## Tasks

| Task | Name | Commit |
|------|------|--------|
| 1 | viewport detection + None-fallback inversion guard | 51bf590 |
| 2 | Lighthouse band refinement (worst-metric-wins) | c4dabb0 |

## Verification

- `tests/test_performance.py`: **8/8 GREEN** (incl. golden `test_psi_error_not_scored_slow`, `test_worst_metric_band`, `test_psi_good_but_no_viewport_at_least_gap`).
- Full suite (excluding `tests/test_pagespeed_client.py`, owned by Plan 06-04 / still RED): 190 passed, 1 failed.
- The single failure (`test_pipeline_bedarf.py::test_one_client_per_run`, `assert 0 == 1`) is pre-existing and depends on pipeline/clients wiring owned by Plans 06-04/06-05 — out of scope for this plan (analyzer is not yet wired). My changes touched only `performance.py`.

## Threat Model Compliance

- **T-06-06 (score inversion):** `if ps_result is None` branch is first and returns only `ok`/`gap` — verified by `test_psi_error_not_scored_slow`.
- **T-06-07 (malformed metric DoS):** absent metrics excluded from band set (no exception); `perf_score` None-guarded in the reason string.

## Deviations from Plan

None - plan executed exactly as written.

## TDD Gate Compliance

The RED test scaffold (`tests/test_performance.py`) was authored in Plan 06-01 (Wave 0). This plan supplied the GREEN implementation; both task commits are `feat(...)` following the existing failing tests. No separate `test(...)` commit was created in this plan because the tests pre-existed.

## Self-Check: PASSED

- FOUND: lead_analyzer/analyzers/performance.py
- FOUND: commit 51bf590 (Task 1)
- FOUND: commit c4dabb0 (Task 2)
