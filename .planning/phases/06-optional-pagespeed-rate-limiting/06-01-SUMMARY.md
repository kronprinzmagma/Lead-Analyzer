---
phase: 06-optional-pagespeed-rate-limiting
plan: 01
subsystem: tests
tags: [tdd, red, pagespeed, dim-3, env-loader, degradation-contract]
requires: []
provides: [red-scaffolds, make_ps_result, inversion-guard-test, single-client-test]
affects: [tests/conftest.py, tests/test_env_loader.py, tests/test_performance.py, tests/test_pagespeed_client.py, tests/test_pipeline_bedarf.py]
tech-stack:
  added: []
  patterns: [lazy-import-in-conftest, injected-noop-sleep, monkeypatch-requests-get, semaphore-concurrency-probe]
key-files:
  created: [tests/test_env_loader.py, tests/test_performance.py, tests/test_pagespeed_client.py]
  modified: [tests/conftest.py, tests/test_pipeline_bedarf.py]
decisions:
  - "RED scaffolds use top-level imports per plan; missing-module files error at collection (verify-grep treats this as RED-OK), while the two pipeline RED tests use in-test imports so they fail at runtime and keep the file collecting."
metrics:
  duration: ~10m
  completed: 2026-06-14
---

# Phase 6 Plan 01: RED Test Scaffolds Summary

Locks the Phase-6 degradation contract as executable RED tests before any production code: the PSI-error-is-not-slow inversion guard, the stdlib .env loader behavior, the Dim-3 viewport+PSI analyzer, the offline PSI client (200/429/timeout/malformed/budget/cache/semaphore), and the single-PSI-client-per-run invariant.

## What was built

- **tests/conftest.py** — added `make_ps_result(**overrides)` mirroring `make_fetch_result`, lazy-importing `PsResult` so collection survives the RED phase.
- **tests/test_env_loader.py** (4 tests) — KEY=VALUE parse, comment/blank/quote handling, setdefault no-override, missing-file-no-raise.
- **tests/test_performance.py** (8 tests) — viewport±PSI±None matrix incl. the golden `test_psi_error_not_scored_slow` (ps_result=None ⇒ ok, asserts `!= "severe"`), worst-metric-band, dim==3.
- **tests/test_pagespeed_client.py** (8 tests) — fully offline: unavailable-without-key, 200-parsed, timeout→None, malformed-json→None, 429-retry-after-capped (injected no-op sleep), budget-exhausted-skips, cache-hit-no-network, semaphore-caps.
- **tests/test_pipeline_bedarf.py** — appended `test_no_pagespeed_flag` and `test_one_client_per_run` (PERF-02/AC8 single-client invariant).

## Deviations from Plan

None - plan executed as written. (RED files that import missing top-level modules interrupt collection; the plan's own verify-grep accepts this as RED-OK, and the existing 177 tests still pass.)

## Self-Check: PASSED

- tests/test_env_loader.py, tests/test_performance.py, tests/test_pagespeed_client.py exist (FOUND).
- Commits dcd229c, e2fdb7c, 1141d91 exist in git log (FOUND).
- All new tests RED for the right reason (missing modules); existing 177 pass.
