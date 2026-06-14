---
phase: 06-optional-pagespeed-rate-limiting
verified: 2026-06-14T00:00:00Z
status: passed
score: 3/3 truths verified
overrides_applied: 0
re_verification:
  previous_status: none
gaps: []
---

# Phase 6: Optional PageSpeed (Dim 3) + Rate Limiting — Verification Report

**Phase Goal:** PageSpeed enriches Dimension 3 when available, stays fully skippable, and never stalls or aborts the run.
**Verified:** 2026-06-14
**Status:** PASSED
**Re-verification:** No — initial verification
**Requirements:** BED-03, PERF-02

## Goal Achievement

### Observable Truths

| # | Truth (ROADMAP SC) | Status | Evidence |
|---|--------------------|--------|----------|
| 1 | Dim 3 uses viewport-meta always + PSI when available; no network/key degrades to heuristic with a note (AC11) | ✓ VERIFIED | `performance.analyze` (performance.py:99-127): viewport baseline always; inversion-guard branch (`ps_result is None`) runs FIRST and returns heuristic-fallback, structurally never `severe`. Offline run: 0 reasons with real PSI (`mobile perf=`), all Dim 3 notes carry "PageSpeed übersprungen/Fehler". Golden test `test_psi_error_not_scored_slow` asserts `level != "severe"` and `== "ok"`. |
| 2 | PSI client exposes availability, batching/retry/backoff, respects Retry-After, per-run budget, `--no-pagespeed` flag (AC8) | ✓ VERIFIED | pagespeed.py: `is_available()` (key+budget), `_Budget` thread-safe per-run counter, `threading.Semaphore` concurrency cap, capped retries (3) with Retry-After-aware backoff+jitter, namespaced cache `["pagespeed-v1","mobile",url]`, injected `sleep`. `--no-pagespeed` in cli.py:42-45 → `use_pagespeed=not args.no_pagespeed`. One client per run verified by `test_one_client_per_run` (from_config called exactly once) + pipeline.py:108. |
| 3 | A PSI error/quota lowers nothing and aborts nothing — run completes with degraded but valid scores (AC8/AC4) | ✓ VERIFIED | `score()` returns `None` on every failure path (Timeout, non-200, malformed JSON, 429-after-retries, budget exhausted), never raises. `None` → inversion-guard heuristic. Pipeline gates PSI behind `fr.ok and fr.html`. Full offline run over 42 rows completed; 0 rows with invalid/empty scores; all scores integer 1-5. Tests `test_timeout_returns_none`, `test_malformed_json_none`, `test_429_retry_after_capped`, `test_budget_exhausted_skips` all green. |

**Score:** 3/3 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `lead_analyzer/analyzers/performance.py` | Dim-3 viewport baseline + PSI refinement + inversion guard | ✓ VERIFIED | 127 lines, substantive, wired in pipeline.py:73. None-branch first, never severe. |
| `lead_analyzer/clients/pagespeed.py` | Optional PSI client: budget/semaphore/backoff/cache, None-on-failure | ✓ VERIFIED | 218 lines, wired via `from_config` in pipeline.py:108. |
| `lead_analyzer/config.py` (load_dotenv) | stdlib .env loader, setdefault, no raise on missing | ✓ VERIFIED | config.py:15-44; `os.environ.setdefault` (no override), `try/except OSError`, missing file → None. Called once in cli.py:53 before Config build. |
| `lead_analyzer/cli.py` (--no-pagespeed) | Flag wired to use_pagespeed | ✓ VERIFIED | cli.py:42-45, 65. |
| `lead_analyzer/pipeline.py` (Dim 3 wiring) | One shared client, gated PSI, ps_result→analyze | ✓ VERIFIED | pipeline.py:67-73, 108, 118. |

### Key Link Verification

| From | To | Via | Status |
|------|----|----|--------|
| cli.main | load_dotenv | called before Config (cli.py:53) | ✓ WIRED |
| pipeline.run | PageSpeedClient.from_config | once per run (pipeline.py:108) | ✓ WIRED |
| analyze_row | ps_client.score | gated on is_available + fr.ok + fr.html (pipeline.py:68-69) | ✓ WIRED |
| analyze_row | performance.analyze | ps_result passed (pipeline.py:73) | ✓ WIRED |
| score | cache.key_for namespaced | pagespeed.py:116 | ✓ WIRED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Offline no-key full run completes | `python run.py data/sample_input.xlsx -o output/phase6_verify.xlsx` (PAGESPEED_API_KEY unset) | 42 rows processed, exit 0 | ✓ PASS |
| All scores integer 1-5, none empty | openpyxl scan | 0 invalid/empty rows | ✓ PASS |
| No real PSI offline (heuristic only) | grep reasons for `mobile perf=` | 0 | ✓ PASS |
| Output sorted desc bedarf then zahl (monotonic) | key comparison | True | ✓ PASS |
| Full test suite | `python -m pytest tests/ -q` | 200 passed | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plans | Status | Evidence |
|-------------|-------------|--------|----------|
| BED-03 | 06-01,02,03,05 | ✓ SATISFIED | Dim 3 viewport baseline + PSI refinement; inversion guard; golden test. |
| PERF-02 | 06-01,02,04,05 | ✓ SATISFIED | Budget, semaphore, backoff, Retry-After, one-client-per-run, namespaced cache, --no-pagespeed. |

### The Five BED-03 Assertion Changes — Legitimacy Audit

Each was independently confirmed against the actual fixture; none is a masked regression.

| # | Test | Change | Fixture viewport state | Verdict |
|---|------|--------|------------------------|---------|
| 1 | `test_six_verdicts_wired` | Dim3 ok→gap | default `make_fetch_result` HTML (conftest.py:82, `<head><title>Beispiel</title>`) — viewport ABSENT | LEGIT |
| 2 | `test_block_403_no_body_is_not_5_and_is_2` | bedarf ==2→==3 | `html=None` → soup None → viewport genuinely unobtainable | LEGIT (`!=5` invariant preserved) |
| 3 | `test_block_403_is_neutral_not_5` (dim1) | ==2→==3 | same 403/no-body | LEGIT |
| 4 | `_MODERN_HTML` | viewport-meta ADDED | fixture was viewport-ABSENT; a genuinely modern site HAS a viewport | LEGIT — test intent (modern→Bedarf 1) preserved; not a Dim-3 test |
| 5 | `test_social_only_high_but_not_5` (dim1) | viewport-meta ADDED | `<html><body>Profil</body></html>` viewport-ABSENT | LEGIT — isolates Dim-1 concern (social-only severe-not-dead); not a Dim-3 test |

Changes #4 and #5 ADD a viewport to fixtures. Both are defensible: the tests' load-bearing intents (modern→1; social-only→4-not-5) are Dim-1/aggregation concerns unrelated to Dim 3, and no scoring band or analyzer threshold was altered. `scoring.py` was NOT modified in Phase 6 (last touch commit 4a231db / 03-04; Phase 6 commits touch only performance.py, pagespeed.py, config.py, cli.py, pipeline.py, tests). No viewport-PRESENT fixture had its Bedarf assertion changed — which would have signalled a wiring bug.

### Transparency / Byte-Identity

- `test_offline_output_byte_identical_to_placeholder` (pipeline_bedarf.py:122-140): real offline path == Phase-5 DIM3_PLACEHOLDER baseline for viewport-present rows, identical across workers=1 and workers=8. GREEN.
- `test_one_client_per_run`: from_config called exactly once. GREEN.
- `DIM3_PLACEHOLDER` still present in scoring.py (used only as the test baseline; production now uses real analyzer).

### Anti-Patterns Found

None blocking. No TODO/FIXME/placeholder in Phase-6 source. `DIM3_PLACEHOLDER` retained intentionally as a test baseline, not in the production path.

### Human Verification Required

None. All truths verified programmatically; offline degradation, inversion guard, budget/backoff, and byte-identity are all covered by deterministic tests and a real offline run. (Live PSI behavior with a real key is out of scope for offline verification and not required by the phase's load-bearing criteria.)

### Gaps Summary

No gaps. The load-bearing guarantees hold: a PSI error/quota/timeout returns `None` (never raises), `None` is treated identically to "skipped" and structurally cannot produce `severe` (inversion guard, first branch). Offline/no-key output is byte-identical to Phase 5 for viewport-present rows and monotonic. The PSI client is built exactly once per run with shared semaphore + budget. Scoring bands are unchanged; all five test-assertion edits sit on genuinely viewport-absent fixtures (or add a viewport to a fixture whose test intent is unrelated to Dim 3).

Note: ROADMAP.md progress table lists Phase 6 as "Not started" (0/TBD) despite all 5 plans checked and complete — a stale table entry, not a functional gap. Recommend updating the table during Phase 7.

---

_Verified: 2026-06-14_
_Verifier: Claude (gsd-verifier)_
