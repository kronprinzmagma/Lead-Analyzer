---
phase: 06-optional-pagespeed-rate-limiting
plan: 04
subsystem: api
tags: [pagespeed, psi, lighthouse, requests, semaphore, backoff, retry-after, cache, threading]

requires:
  - phase: 06-optional-pagespeed-rate-limiting (Plan 02)
    provides: Config.use_pagespeed/pagespeed_concurrency/pagespeed_budget, PsResult dataclass
  - phase: 05 (caching)
    provides: cache.key_for / get / put (atomic, schema-versioned, thread-safe)
provides:
  - lead_analyzer/clients/ package with the optional, rate-limited PageSpeed Insights client
  - PageSpeedClient.from_config / is_available / score(url) -> PsResult | None
  - _Budget thread-safe per-run call counter, semaphore-capped concurrency, Retry-After-aware backoff
  - namespaced PSI cache (pagespeed-v1/mobile/url) — cache hit spends no network and no budget
affects: [06-05 (pipeline wiring), performance analyzer Dim-3]

tech-stack:
  added: []
  patterns:
    - "Optional network client gated by from_config (default OFF without PAGESPEED_API_KEY)"
    - "Injected sleep for fully offline, zero-wall-clock backoff tests"
    - "Semaphore wraps ONLY the network call; per-run Lock-guarded budget counter"
    - "Defensive parse: every JSON access wrapped, any failure -> None (never raise)"

key-files:
  created:
    - lead_analyzer/clients/__init__.py
    - lead_analyzer/clients/pagespeed.py
  modified: []

key-decisions:
  - "RED was supplied by the Wave-0 scaffold (Plan 01); Plan 04 implements GREEN directly"
  - "Failures are NOT cached — only successful PsResults round-trip via cache.put"
  - "_parse_retry_after supports only integer-seconds (HTTP-date falls back to exponential backoff)"
  - "read timeout raised to max(timeout_read, 30.0) because Lighthouse runs are slow (A4)"

patterns-established:
  - "Pattern: external client returns None on every failure; degradation, not crash (Pitfall 1/8)"
  - "Pattern: separate cache namespace per data type so PSI and fetch entries never collide (Pitfall 3)"

requirements-completed: [PERF-02]

duration: 9min
completed: 2026-06-14
---

# Phase 6 Plan 04: clients/pagespeed.py — optional PSI client Summary

**Optional, rate-limited PageSpeed Insights client (semaphore cap 2, per-run budget, Retry-After-aware backoff with injected sleep, namespaced cache) that returns None on every failure and never raises — making tests/test_pagespeed_client.py fully GREEN.**

## Performance

- **Duration:** ~9 min
- **Tasks:** 2
- **Files modified:** 2 (both created)

## Accomplishments
- `lead_analyzer/clients/` package created; `PageSpeedClient` with `from_config`/`is_available`/`score`.
- Thread-safe `_Budget` per-run counter + `threading.Semaphore` concurrency cap (< worker count).
- `_request` with capped retries (3), 429/5xx backoff honoring `Retry-After` plus jitter, injected sleep.
- Defensive `_parse` of `lighthouseResult` (perf/LCP/CLS/TBT) — any KeyError/TypeError/ValueError → None.
- Namespaced cache (`pagespeed-v1`/`mobile`/url): cache hit spends no network and no budget; failures not cached.
- All 8 tests in `tests/test_pagespeed_client.py` GREEN; full suite at 190 passed (up from 181).

## Task Commits

1. **Task 1: package + client skeleton (from_config, is_available, budget, cache hit)** - `d4a327e` (feat)
2. **Task 2: _request (semaphore, backoff, Retry-After) + _parse — None on every failure** - `81cfe18` (feat)

_TDD note: the RED test was provided by the Wave-0 scaffold (Plan 01); this plan delivered GREEN. The Task-1 commit makes 3 availability/budget/cache tests pass; Task-2 makes all 8 pass._

## Files Created/Modified
- `lead_analyzer/clients/__init__.py` - clients package marker (German docstring).
- `lead_analyzer/clients/pagespeed.py` - `_Budget`, `PageSpeedClient`, `_request`, `_parse`, `_backoff_delay`, `_parse_retry_after`.

## Decisions Made
- RED supplied by Wave-0 scaffold; Plan 04 implements GREEN — no separate test commit.
- Only successful `PsResult`s are cached (failures intentionally not cached, per plan).
- `Retry-After` integer-seconds honored; HTTP-date form falls back to exponential `2**attempt`.
- read timeout raised to `max(timeout_read, 30.0)` for slow Lighthouse runs (06-RESEARCH A4).

## Deviations from Plan

None - plan executed exactly as written. (Stubs for `_request`/`_parse` in Task 1 were filled in Task 2 as specified.)

## Issues Encountered
- `tests/test_pipeline_bedarf.py::test_one_client_per_run` fails (`assert 0 == 1`): it asserts that
  `pipeline.run` calls `PageSpeedClient.from_config` exactly once. That wiring lives in `pipeline.py`,
  which Plan 04 is explicitly forbidden to modify — it is Plan 06-05's responsibility ("client not yet
  wired — Plan 05"). Logged to `deferred-items.md`; no action taken. The import-error that previously
  failed this test is resolved by the new package; only the pipeline-side wiring remains.
- `tests/test_performance.py` is owned by the concurrent Plan 06-03 and was excluded from 06-04 runs
  via `--ignore` (collection ImportError until 06-03 lands its module).

## TDD Gate Compliance
RED was established by the Wave-0 scaffold commit (Plan 01) via ImportError-driven failing tests; this
plan provides the GREEN `feat(...)` commits. No `refactor` commit was needed.

## Next Phase Readiness
- Client API (`from_config`/`is_available`/`score`) is stable and ready for Plan 06-05 to wire into the
  pipeline (build one client per run, call `score()` per row inside the performance analyzer's Dim-3 path).
- No external setup required to run the offline suite; a live `PAGESPEED_API_KEY` is only needed for real
  PSI measurements (default OFF without key).

## Self-Check: PASSED
- FOUND: lead_analyzer/clients/__init__.py
- FOUND: lead_analyzer/clients/pagespeed.py (217 lines, min 80)
- FOUND commit d4a327e (Task 1)
- FOUND commit 81cfe18 (Task 2)
- tests/test_pagespeed_client.py: 8 passed; full suite 190 passed (excl. 06-03-owned test_performance.py)

---
*Phase: 06-optional-pagespeed-rate-limiting*
*Completed: 2026-06-14*
